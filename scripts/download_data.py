"""Download EU live bovine animal export data from the Eurostat Comext API.

Replaces the old workflow of manually downloading bulk .dat files from the
Comext bulk download service (see countries_comparison_month_2023.R).

Dataset DS-045409 ("EU trade since 2002 by HS6/CN8") is the one that actually
carries both CN8 product codes and the SUPPLEMENTARY_QUANTITY indicator (head
count for live animals, equivalent to the old SUP_QUANTITY field from the
bulk .dat files). DS-059341 was tried too but only goes down to CN6 and has
no supplementary-quantity indicator, so it can't be used for this.

This is the multi-reporter version (all eight countries in REPORTERS below,
one calendar year at a time). scripts/fetch_at_history.py is a narrower
sibling script: Austria only, but across many years at once, feeding the
public dashboard.

Run it from the command line with the year you want, e.g.:
  python scripts/download_data.py 2023
"""

import argparse
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"

REPORTERS = ["AT", "DE", "HU", "IT", "SK", "SI", "CZ", "HR"]
PRODUCTS = ["01022110", "01022130"]  # live bovine animals, CN8
FLOW = "2"  # export
INDICATOR = "SUPPLEMENTARY_QUANTITY"  # head count

# __file__ is this script's own path; .resolve() makes it absolute, and
# .parent.parent walks up from scripts/ to the project root, so ROOT_DIR is
# correct no matter which folder you run the script from.
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def fetch(year: int) -> pd.DataFrame:
    """Download one year of monthly export rows (all reporters, both
    product codes) and return them as a pandas DataFrame -- a table you
    can filter, group, and sum, similar to a spreadsheet.
    """
    # The Eurostat API key is a single dot-separated string, with each
    # dimension (reporter, partner, product, flow, indicator) in a fixed
    # order. '+'.join(...) combines multiple codes for one dimension with
    # a "+" (meaning "any of these"); leaving the partner segment empty
    # (the ".." below) means "all partner countries".
    key = f"M.{'+'.join(REPORTERS)}..{'+'.join(PRODUCTS)}.{FLOW}.{INDICATOR}"
    params = {
        "startPeriod": f"{year}-01",
        "endPeriod": f"{year}-12",
        "format": "SDMX-CSV",
    }
    # timeout=60 gives up after 60 seconds instead of hanging forever if
    # the server never responds. raise_for_status() raises an exception if
    # the HTTP status code wasn't a success, so a failed request stops the
    # script here with a clear error rather than continuing with no data.
    response = requests.get(f"{BASE_URL}/{key}", params=params, timeout=60)
    response.raise_for_status()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"comext_bovine_export_{year}.csv"
    raw_path.write_bytes(response.content)
    return pd.read_csv(raw_path)


def to_wide_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Reshape the raw "one row per reporter/partner/month" table into a
    "wide" layout with one row per reporter/partner pair and one column
    per month (quant01..quant12) -- easier to scan and to open in a
    spreadsheet than the original long format.
    """
    df = df.rename(columns={"reporter": "DECLARANT_ISO", "partner": "PARTNER_ISO"})
    # TIME_PERIOD looks like "2023-04" (year-month); slicing characters
    # 5 to 7 keeps just the month part, "04".
    df["month"] = df["TIME_PERIOD"].str.slice(5, 7)

    # groupby(...) splits the rows into groups that share the same
    # (declarant, partner, month) combination; ["OBS_VALUE"].sum() adds up
    # the export quantity within each group; reset_index() turns the
    # grouping keys back into normal columns.
    monthly = df.groupby(["DECLARANT_ISO", "PARTNER_ISO", "month"])["OBS_VALUE"].sum().reset_index()
    # .pivot(...) is what actually reshapes long -> wide: it takes the
    # "month" column's values ("01", "02", ...) and turns each one into
    # its own column, filled with the matching OBS_VALUE.
    wide = monthly.pivot(
        index=["DECLARANT_ISO", "PARTNER_ISO"], columns="month", values="OBS_VALUE"
    )
    wide.columns = [f"quant{m}" for m in wide.columns]
    # Not every reporter/partner/month combination has data; .fillna(0)
    # replaces those gaps with 0 rather than leaving them blank.
    return wide.fillna(0).reset_index()


def main() -> None:
    # argparse reads command-line arguments (the words typed after
    # "python scripts/download_data.py"). description=__doc__ reuses this
    # file's own top docstring as the help text shown by --help.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, help="Reference year, e.g. 2023")
    args = parser.parse_args()

    df = fetch(args.year)
    wide = to_wide_by_month(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / f"bovine_exports_by_month_{args.year}.csv"
    wide.to_csv(out_path, index=False)
    print(f"Saved {out_path} ({len(wide)} declarant/partner rows)")


# __name__ is only "__main__" when this file is run directly (`python
# scripts/download_data.py 2023`), not when some other script imports it
# -- so importing this module elsewhere won't accidentally trigger a
# network request.
if __name__ == "__main__":
    main()
