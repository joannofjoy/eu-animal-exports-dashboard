"""Explore what indicators dataset DS-059341 actually exposes, by requesting
every indicator at once (the trailing "." in broad_key below, with nothing
after it, means "don't filter on indicator -- give me all of them") and
scanning the response for anything that looks like a head-count field.

This is a standalone diagnostic, not part of the data pipeline the
dashboard depends on -- nothing else in this project imports it. It's what
originally confirmed DS-059341 has no SUPPLEMENTARY_QUANTITY-equivalent
indicator; see docs/eurostat_comext_api.md for the full writeup.

Run it directly:
  python scripts/inspectDS-059341.py
"""

import re
from pathlib import Path

import requests

BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1"
DATASET = "DS-059341"

# __file__ is this script's own path; .resolve() makes it absolute, and
# .parent.parent walks up from scripts/ to the project root -- so this
# always writes into <project root>/data/debug, regardless of which
# folder you happen to run the script from.
ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "data" / "debug"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Words to scan the response for -- anything matching one of these hints
# that a line might describe a quantity/indicator field worth a closer
# look, even if its exact name isn't known in advance.
SEARCH_TERMS = [
    "SUP",
    "SUPPL",
    "SUPPLEMENT",
    "HEAD",
    "HEADS",
    "NAR",
    "NUMBER",
    "ANIMAL",
    "UNIT",
    "QUANTITY",
    "KG",
    "VALUE",
    "INDICATOR",
]


def get(url: str, params: dict | None = None) -> str:
    """Make the API request, print a short preview of what came back (so
    you can see what happened without opening a separate file), and
    return the full response body as text.
    """
    r = requests.get(url, params=params, timeout=90)
    print("\nURL:", r.url)
    print("Status:", r.status_code)
    print("Content-Type:", r.headers.get("content-type"))
    print("First 500 chars:")
    print(r.text[:500])
    # Raises an exception if the HTTP status code wasn't a success, so a
    # failed request stops the script here with a clear error instead of
    # continuing to scan an empty/error response for search terms.
    r.raise_for_status()
    return r.text


def save(name: str, text: str) -> Path:
    """Write `text` to data/debug/<name> and return the path, so it can be
    re-inspected later without re-hitting the API.
    """
    path = OUT_DIR / name
    path.write_text(text, encoding="utf-8")
    print(f"Saved: {path}")
    return path


def grep_terms(text: str, label: str) -> None:
    """Print every line of `text` that contains one of SEARCH_TERMS
    (case-insensitively), prefixed with its line number -- a quick way to
    scan a CSV response for anything indicator/quantity-related without
    reading the whole thing by eye.
    """
    print(f"\n=== Matches in {label} ===")
    lines = text.splitlines()
    found = False

    for i, line in enumerate(lines, start=1):
        upper = line.upper()
        # any(...) is True as soon as one of the search terms is found in
        # the line; this checks all of them so any (case-insensitive)
        # match is enough to print the line.
        if any(term in upper for term in SEARCH_TERMS):
            found = True
            # Collapse repeated whitespace down to single spaces, purely
            # to keep the printed output readable.
            clean = re.sub(r"\s+", " ", line).strip()
            print(f"{i}: {clean[:300]}")

    if not found:
        print("No relevant terms found.")


def main() -> None:
    # Direct test: all indicators for AT exports of live bovine animals, HS6 010221
    broad_key = "M.AT..010221.2."
    data_url = f"{BASE}/data/{DATASET}/{broad_key}"

    csv_text = get(
        data_url,
        params={
            "startPeriod": "2023-01",
            "endPeriod": "2023-01",
            "format": "SDMX-CSV",
        },
    )

    save(f"{DATASET}_sample_AT_010221_export_all_indicators.csv", csv_text)

    print("\n=== CSV columns ===")
    print(csv_text.splitlines()[0])

    print("\n=== First 30 rows ===")
    for row in csv_text.splitlines()[:30]:
        print(row)

    grep_terms(csv_text, "sample CSV")


# __name__ is only "__main__" when this file is run directly, not when
# something else imports it -- not that anything currently does.
if __name__ == "__main__":
    main()
