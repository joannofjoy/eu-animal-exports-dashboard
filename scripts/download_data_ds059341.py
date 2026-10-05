"""Attempt to download EU live bovine animal export data from Eurostat Comext
dataset DS-059341, using the same reporters/product/flow/indicator codes as
download_data.py (DS-045409).

This is expected to fail: DS-059341's product codelist only goes down to CN6
(e.g. "0102", "010221"), not CN8, so "01022110"/"01022130" are rejected; and
its indicators are QUANTITY_KG / VALUE_EUR / VALUE_NAC only, with no
SUPPLEMENTARY_QUANTITY (head count). Kept as-is so the actual API error is
visible below rather than silently switching datasets. (Re-verified live on
2026-07-20: still fails with the same INVALID_QUERY_DIMENSION_VALUE error.)

This script is a standalone diagnostic, not part of the data pipeline the
dashboard depends on -- nothing else in this project imports it. It's kept
for the record because it's what originally proved DS-059341 doesn't work
for this project; see docs/eurostat_comext_api.md for the full comparison.

Run it directly to reproduce the failure:
  python scripts/download_data_ds059341.py
"""

from pathlib import Path

import requests

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-059341"

REPORTERS = ["AT", "DE", "HU", "IT", "SK", "SI", "CZ", "HR"]
PRODUCTS = ["01022110", "01022130"]  # live bovine animals, CN8
FLOW = "2"  # export
INDICATOR = "SUPPLEMENTARY_QUANTITY"  # head count

# __file__ is this script's own path; .resolve() makes it absolute, and
# .parent.parent walks up from scripts/ to the project root, so RAW_DIR is
# correct no matter which folder you run the script from.
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"


def fetch(year: int) -> requests.Response:
    """Make the API request and return the raw response object (not just
    the data) -- main() below needs to inspect the status code and error
    body even when the request "fails" (a 400 response), so this can't
    just call raise_for_status() and return parsed data like the working
    download_data.py does.
    """
    key = f"M.{'+'.join(REPORTERS)}..{'+'.join(PRODUCTS)}.{FLOW}.{INDICATOR}"
    params = {
        "startPeriod": f"{year}-01",
        "endPeriod": f"{year}-12",
        "format": "SDMX-CSV",
    }
    return requests.get(f"{BASE_URL}/{key}", params=params, timeout=60)


def main() -> None:
    response = fetch(2023)
    print(f"URL: {response.url}")
    print(f"HTTP status: {response.status_code}")
    print(f"Body: {response.text}")

    # Only save a file if the request actually succeeded (HTTP 200) --
    # for the expected-failure case (400), there's nothing useful to save,
    # the printed error body above is the point.
    if response.status_code == 200:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / "comext_bovine_export_2023_ds059341.csv"
        raw_path.write_bytes(response.content)
        print(f"Saved {raw_path}")


# __name__ is only "__main__" when this file is run directly, not when
# something else imports it -- not that anything currently does.
if __name__ == "__main__":
    main()
