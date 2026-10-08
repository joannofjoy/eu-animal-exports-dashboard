"""Fetch a reporter country's *import* declarations for fresh/chilled and
frozen bovine meat (CN headings 0201 + 0202, 2015-latest full year) from
Eurostat Comext dataset DS-045409 -- the meat-trade half of the "beef vs.
cows" comparison on public/beef_vs_cows.html, which puts this next to the
reporter's existing live cattle *exports* (fetch_at_history.py, heading
0102) to show both sides of the "calves leave live, meat comes back"
question. See docs/llm_agent_handoff.md section 6.1 for the research
behind why this is an import-only, combined beef-and-veal comparison: meat
trade statistics can't distinguish veal from beef (no CN code splits on
age), and the live-exports-vs-meat-imports direction is the one that
matches the original investigative question.

Same dataset, API, and per-year request pattern as fetch_at_history.py
(one request per year, not a bulk multi-year one -- see its fetch() for
why); reuses that script's REPORTER default, AGGREGATE_PARTNERS filtering,
aggregate()/aggregate_monthly(), and validate_api_response() rather than
duplicating them. The real differences from fetch_at_history.py are: the
product list (MEAT_PRODUCTS, scripts/meat_products.py, not PRODUCTS),
flow=1 (import; this project has no reason to also track meat *exports*
for this comparison), and the quantity indicator -- meat has no per-animal
head count, so this requests QUANTITY_IN_100KG instead of
SUPPLEMENTARY_QUANTITY (confirmed live: a live-cattle-style SUPPLEMENTARY_
QUANTITY request against a meat CN8 code returns no quantity rows at all,
just VALUE_IN_EUROS; QUANTITY_IN_100KG does return real weight data).

Writes (each processed CSV has a "quantity_100kg" column -- net weight in
units of 100kg, Eurostat's own reporting unit, converted to tonnes at
build time rather than here, so the processed CSV stays a direct read of
what the API actually returned -- and a "value_eur" column, trade value in
euros):
  data/raw/comext_beef_import_<REPORTER>_<start>-<end>.csv   raw monthly rows
  data/processed/<reporter>_beef_imports_yearly_by_product.csv
                                                              year,product,quantity_100kg,value_eur
  data/processed/<reporter>_beef_imports_yearly_by_partner.csv
                                                              year,partner,quantity_100kg,value_eur
  data/processed/<reporter>_beef_imports_yearly_by_partner_product.csv
                                                              year,partner,product,quantity_100kg,value_eur

Run it from the command line, e.g.:
  python scripts/fetch_meat_imports.py --reporter AT --start-year 2015 --end-year 2026
  python scripts/fetch_meat_imports.py --reporter DE --start-year 2015 --end-year 2026
"""

import argparse
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from fetch_at_history import REPORTER, aggregate, validate_api_response
from meat_products import MEAT_PRODUCTS

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
FLOW = "1"  # import (arrivals)
INDICATORS = ["QUANTITY_IN_100KG", "VALUE_IN_EUROS"]
INDICATOR_COLUMNS = {"QUANTITY_IN_100KG": "quantity_100kg", "VALUE_IN_EUROS": "value_eur"}

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def fetch_year(year: int, reporter: str = REPORTER) -> bytes:
    """Download one year of monthly meat-import rows from the Eurostat
    API and return the raw response bytes (not yet parsed). Same shape as
    fetch_at_history.py's fetch_year(), with MEAT_PRODUCTS/FLOW/INDICATORS
    in place of the live-cattle ones.
    """
    key = f"M.{reporter}..{'+'.join(MEAT_PRODUCTS)}.{FLOW}.{'+'.join(INDICATORS)}"
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
    raw_path = RAW_DIR / f"comext_beef_import_{reporter}_{start_year}-{end_year}.csv"

    years_data = []
    for i, year in enumerate(range(start_year, end_year + 1)):
        content = fetch_year(year, reporter)
        year_df = pd.read_csv(BytesIO(content), dtype={"product": str, "partner": str})
        year_df = validate_api_response(
            year_df, year, reporter, FLOW, INDICATORS, products=MEAT_PRODUCTS
        )
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
    by_product, by_partner, by_partner_product = aggregate(df, INDICATOR_COLUMNS)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    prefix = reporter.lower()
    by_product_path = PROCESSED_DIR / f"{prefix}_beef_imports_yearly_by_product.csv"
    by_partner_path = PROCESSED_DIR / f"{prefix}_beef_imports_yearly_by_partner.csv"
    by_partner_product_path = (
        PROCESSED_DIR / f"{prefix}_beef_imports_yearly_by_partner_product.csv"
    )
    by_product.to_csv(by_product_path, index=False)
    by_partner.to_csv(by_partner_path, index=False)
    by_partner_product.to_csv(by_partner_product_path, index=False)

    print(f"Saved {by_product_path} ({len(by_product)} rows)")
    print(f"Saved {by_partner_path} ({len(by_partner)} rows)")
    print(f"Saved {by_partner_product_path} ({len(by_partner_product)} rows)")


if __name__ == "__main__":
    main()
