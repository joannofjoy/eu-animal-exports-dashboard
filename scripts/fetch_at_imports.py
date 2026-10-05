"""Fetch Austria's own *import* declarations for live cattle (2015-latest
full year) from Eurostat Comext dataset DS-045409 -- the mirror-image of
fetch_at_history.py, which covers Austria's exports.

This is for the "paired countries" dashboard (public/trade_pairs.html):
for a chosen partner country, show Austria's exports to it next to
Austria's imports from it, both numbers self-reported by Austria alone.
That's a deliberately different question from the mirror-comparison tool
(public/mirror.html), which compares Austria's export declaration against
the *partner's own* import declaration for the same trade -- see the
conversation notes in docs/mirror_tool_explained.md for why those two
comparisons need different data and shouldn't be confused with each other.

Same product scope, reporter, and aggregation logic as
fetch_at_history.py (PRODUCTS, AGGREGATE_PARTNERS, and the aggregate()
function itself are imported from there rather than duplicated -- the
only real difference between the two scripts is the flow code: "1"
(arrivals/imports) here vs. "2" (dispatches/exports) there). Same
per-year request loop too, for the same reason: a full 2015-2025,
all-partners, 35-product request is large enough that Eurostat's API
queues it asynchronously instead of answering directly (confirmed by
testing this script's own query the same way fetch_at_history.py's was
tested), so this fetches one year at a time to keep each request small
enough for a synchronous reply.

Writes (each processed CSV has both a "quantity" column, head count, and
a "value_eur" column, trade value in euros -- see fetch_at_history.py's
aggregate()/_pivot_indicators() for how that shape is produced). Like
fetch_at_history.py, the reporter code (lowercased) prefixes every
filename, defaulting to "at" so Austria's own files keep their original
names:
  data/raw/comext_bovine_import_<REPORTER>_<start>-<end>.csv   raw monthly rows
  data/processed/<reporter>_bovine_imports_yearly_by_product.csv
                                                                year,product,quantity,value_eur
  data/processed/<reporter>_bovine_imports_yearly_by_partner.csv
                                                                year,partner,quantity,value_eur
  data/processed/<reporter>_bovine_imports_yearly_by_partner_product.csv
                                                                year,partner,product,quantity,value_eur

Run it from the command line, e.g.:
  python scripts/fetch_at_imports.py --reporter AT --start-year 2015 --end-year 2025
  python scripts/fetch_at_imports.py --reporter DE --start-year 2015 --end-year 2025
"""

import argparse
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from fetch_at_history import PRODUCTS, REPORTER, aggregate

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
FLOW = "1"  # import (arrivals)
# Head count and trade value together -- see fetch_at_history.py's
# INDICATORS for why this is one request per year, not two.
INDICATORS = ["SUPPLEMENTARY_QUANTITY", "VALUE_IN_EUROS"]

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def fetch_year(year: int, reporter: str = REPORTER) -> bytes:
    """Download one year of monthly import rows from the Eurostat API and
    return the raw response bytes (not yet parsed). Same shape as
    fetch_at_history.py's fetch_year(), just flow=1 instead of flow=2.
    """
    key = f"M.{reporter}..{'+'.join(PRODUCTS)}.{FLOW}.{'+'.join(INDICATORS)}"
    params = {
        "startPeriod": f"{year}-01",
        "endPeriod": f"{year}-12",
        "format": "SDMX-CSV",
    }
    response = requests.get(f"{BASE_URL}/{key}", params=params, timeout=60)
    response.raise_for_status()
    return response.content


def fetch(start_year: int, end_year: int, reporter: str = REPORTER) -> pd.DataFrame:
    """Download every year from start_year to end_year and return them
    combined as one DataFrame -- see fetch_at_history.py's fetch() for why
    this loops one year at a time instead of requesting the whole range
    at once.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"comext_bovine_import_{reporter}_{start_year}-{end_year}.csv"

    years_data = []
    for i, year in enumerate(range(start_year, end_year + 1)):
        content = fetch_year(year, reporter)
        year_df = pd.read_csv(BytesIO(content), dtype={"product": str, "partner": str})
        years_data.append(year_df)

        mode = "wb" if i == 0 else "ab"
        with open(raw_path, mode) as f:
            if i == 0:
                f.write(content)
            else:
                f.write(content.split(b"\n", 1)[1])

    return pd.concat(years_data, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reporter",
        default=REPORTER,
        help="Comext reporter country code, e.g. AT, DE, IE, ES, FR, NL (default: AT)",
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    reporter = args.reporter.upper()

    df = fetch(args.start_year, args.end_year, reporter)
    by_product, by_partner, by_partner_product = aggregate(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    prefix = reporter.lower()
    by_product_path = PROCESSED_DIR / f"{prefix}_bovine_imports_yearly_by_product.csv"
    by_partner_path = PROCESSED_DIR / f"{prefix}_bovine_imports_yearly_by_partner.csv"
    by_partner_product_path = (
        PROCESSED_DIR / f"{prefix}_bovine_imports_yearly_by_partner_product.csv"
    )
    by_product.to_csv(by_product_path, index=False)
    by_partner.to_csv(by_partner_path, index=False)
    by_partner_product.to_csv(by_partner_product_path, index=False)

    print(f"Saved {by_product_path} ({len(by_product)} rows)")
    print(f"Saved {by_partner_path} ({len(by_partner)} rows)")
    print(f"Saved {by_partner_product_path} ({len(by_partner_product)} rows)")


if __name__ == "__main__":
    main()
