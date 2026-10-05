"""Fetch mirror-statistics data for the exploratory "AT vs. partner country"
comparison tool (public/mirror.html) -- for every EU member state Austria
has ever exported live cattle to, this pulls that *partner's own* reported
imports from Austria, so the two sides of the same trade can be compared
side by side. This is what the Croatia 2024 investigation
(docs/croatia_2024_anomaly.md) did by hand for one country; this script
generalises it into browsable data for all of them.

Two indicators, not just one: SUPPLEMENTARY_QUANTITY (head count, what the
rest of this project uses) and QUANTITY_IN_100KG (net mass) -- a mismatch
that shows up in both units is a stronger signal than one that only shows
up in a single unit of measure.

Unlike fetch_at_history.py, this doesn't need a per-year request loop: it
turned out that scoping a query to a small, explicit list of partner
countries (rather than "all partners") keeps the response small enough
that Eurostat answers synchronously even across the full 2015-2025 range
and all 35 product codes at once. So this script makes exactly three API
calls in total, not one per year.

AT's own export side, in head count, is *not* re-fetched here -- it's
already sitting in data/processed/at_bovine_exports_yearly_by_partner_product.csv
from fetch_at_history.py, so this script just reads and filters that file.
Only the net-mass version of AT's export side, and both versions of the
partner countries' mirror imports, are new.

Run it after fetch_at_history.py (this script reads its output):
  python scripts/fetch_mirror_data.py
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from countries import EU_MEMBERS
from fetch_at_history import PRODUCTS

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
REPORTER = "AT"
START_PERIOD = "2015-01"
END_PERIOD = "2025-12"

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
AT_EXPORT_PATH = PROCESSED_DIR / "at_bovine_exports_yearly_by_partner_product.csv"


def eu_partner_countries(at_export_path: Path = AT_EXPORT_PATH) -> list[str]:
    """The EU member states Austria has ever exported cattle to, per the
    existing AT-export data -- these are the only countries that can both
    (a) plausibly have mirror data (only EU members report into DS-045409
    as reporters) and (b) are actually relevant here (no point pulling
    mirror data for an EU country AT has never traded this category with).
    Sorted so the fetch order (and any printed progress) is deterministic.
    """
    df = pd.read_csv(at_export_path, dtype={"partner": str})
    return sorted(set(df["partner"]) & EU_MEMBERS)


def fetch_series(
    reporters: list[str], partners: list[str], flow: str, indicator: str, raw_name: str
) -> pd.DataFrame:
    """One API call, covering every year/product/reporter/partner combo at
    once. reporters and partners are each a list of ISO2 codes joined with
    "+" in the query key -- SDMX's way of saying "any of these". The raw
    response is saved to data/raw/ before parsing, matching
    fetch_at_history.py's raw-then-processed convention.
    """
    key = f"M.{'+'.join(reporters)}.{'+'.join(partners)}.{'+'.join(PRODUCTS)}.{flow}.{indicator}"
    params = {"startPeriod": START_PERIOD, "endPeriod": END_PERIOD, "format": "SDMX-CSV"}
    response = requests.get(f"{BASE_URL}/{key}", params=params, timeout=120)
    response.raise_for_status()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / raw_name).write_bytes(response.content)

    return pd.read_csv(
        BytesIO(response.content), dtype={"product": str, "partner": str, "reporter": str}
    )


def to_yearly(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Collapse monthly rows down to one row per (year, reporter, partner,
    product), the same granularity the rest of this project's processed
    data uses. Empty input (a query that matched nothing) is handled
    explicitly since groupby on an empty DataFrame with no rows still
    needs the right columns to exist for the later merge to work.
    """
    if df.empty:
        return pd.DataFrame(columns=["year", "reporter", "partner", "product", value_col])

    df = df.copy()
    df["year"] = df["TIME_PERIOD"].str.slice(0, 4)
    yearly = (
        df.groupby(["year", "reporter", "partner", "product"])["OBS_VALUE"]
        .sum()
        .reset_index()
        .rename(columns={"OBS_VALUE": value_col})
    )
    return yearly


def combine_series(
    at_export_units: pd.DataFrame,
    partner_import_units: pd.DataFrame,
    at_export_kg: pd.DataFrame,
    partner_import_kg: pd.DataFrame,
) -> pd.DataFrame:
    """Pure joining logic, kept separate from fetch_series()'s network
    calls so it can be unit-tested with small hand-built DataFrames
    instead of needing a live API connection (see
    tests/test_fetch_mirror_data.py) -- the same reasoning
    fetch_at_history.py's aggregate() function follows.

    Each input already has exactly the columns
    ["year", "country", "product", <its one value column>]. Joins them
    into one wide table: one row per (year, country, product), with all
    four measures as columns.
    """
    combined = at_export_units.merge(
        partner_import_units, on=["year", "country", "product"], how="outer"
    )
    combined = combined.merge(at_export_kg, on=["year", "country", "product"], how="outer")
    combined = combined.merge(partner_import_kg, on=["year", "country", "product"], how="outer")

    # An outer merge introduces NaN wherever one side had a row the other
    # didn't (e.g. AT exported a product AT->HR never mirrored) -- these
    # are genuine "reported nothing" cases, not missing pipeline data, so
    # they become explicit 0s rather than staying as NaN (which would
    # break JSON embedding and int formatting downstream).
    value_cols = ["at_export_units", "partner_import_units", "at_export_kg", "partner_import_kg"]
    combined[value_cols] = combined[value_cols].fillna(0).astype(int)

    return combined.sort_values(["year", "country", "product"]).reset_index(drop=True)


def build_comparison_table(countries: list[str]) -> pd.DataFrame:
    """Fetch all three new series (over the network), reshape AT's own
    already-cached export data into the same shape, and hand everything
    to combine_series() to join into one wide table. Net mass comes back
    from the API in units of 100kg (a Eurostat quirk -- QUANTITY_IN_100KG
    is the only net-mass indicator DS-045409 actually populates;
    QUANTITY_IN_KG exists in the shared codelist but isn't valid for this
    dataset) -- multiplied by 100 here so the processed file is in plain
    kilograms, not a unit only this script's author would remember to
    account for.
    """
    mirror_units = to_yearly(
        fetch_series(
            [*countries],
            [REPORTER],
            flow="1",
            indicator="SUPPLEMENTARY_QUANTITY",
            raw_name="comext_mirror_import_units_2015-2025.csv",
        ),
        "partner_import_units",
    )
    mirror_kg_raw = to_yearly(
        fetch_series(
            [*countries],
            [REPORTER],
            flow="1",
            indicator="QUANTITY_IN_100KG",
            raw_name="comext_mirror_import_kg_2015-2025.csv",
        ),
        "partner_import_100kg",
    )
    mirror_kg_raw["partner_import_kg"] = (
        (mirror_kg_raw["partner_import_100kg"] * 100).round().astype(int)
    )

    at_export_kg_raw = to_yearly(
        fetch_series(
            [REPORTER],
            [*countries],
            flow="2",
            indicator="QUANTITY_IN_100KG",
            raw_name="comext_at_export_kg_2015-2025.csv",
        ),
        "at_export_100kg",
    )
    at_export_kg_raw["at_export_kg"] = (
        (at_export_kg_raw["at_export_100kg"] * 100).round().astype(int)
    )

    at_export_units = pd.read_csv(
        AT_EXPORT_PATH, dtype={"year": str, "partner": str, "product": str}
    )
    at_export_units = at_export_units[at_export_units["partner"].isin(countries)].rename(
        columns={"partner": "country", "quantity": "at_export_units"}
    )[["year", "country", "product", "at_export_units"]]

    # Mirror data uses "reporter" for the EU country being queried (AT is
    # the fixed "partner" in that query) -- rename to "country" so every
    # table agrees on one name for "the EU country this row is about"
    # before merging them together.
    mirror_units = mirror_units.rename(columns={"reporter": "country"})[
        ["year", "country", "product", "partner_import_units"]
    ]
    mirror_kg = mirror_kg_raw.rename(columns={"reporter": "country"})[
        ["year", "country", "product", "partner_import_kg"]
    ]
    at_export_kg = at_export_kg_raw.rename(columns={"partner": "country"})[
        ["year", "country", "product", "at_export_kg"]
    ]

    return combine_series(at_export_units, mirror_units, at_export_kg, mirror_kg)


def main() -> None:
    countries = eu_partner_countries()
    print(
        f"Comparing Austria against {len(countries)} EU partner countries: {', '.join(countries)}"
    )

    comparison = build_comparison_table(countries)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / "mirror_comparison.csv"
    comparison.to_csv(output_path, index=False)
    print(f"Saved {output_path} ({len(comparison)} rows)")


if __name__ == "__main__":
    main()
