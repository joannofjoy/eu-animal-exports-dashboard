"""Build the static dashboard page (public/index.html) from the processed
Eurostat data.

This replaces what a small PHP script used to do at *request* time (read
the CSVs, compute totals, embed them as JSON into the page whenever someone
visited it). Since the numbers only change when we re-fetch data -- not on
every page view -- there's no need for a server to redo that work on every
request. Instead, this script does it once, "baking" the results into a
plain .html file that can be opened directly in a browser or hosted
anywhere that serves static files (e.g. GitHub Pages), no PHP required.

Run it after scripts/fetch_at_history.py, any time the processed CSVs
change:

    python scripts/build_dashboard.py
"""

# Lets type hints like `dict[str, int]` work on older Python versions too
# (normally that syntax needs Python 3.9+); harmless to keep even on newer
# versions, and matches the style used elsewhere in this project.
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from countries import COUNTRY_NAMES, EU_MEMBERS, REPORTERS
from product_categories import (
    CODE_TO_CATEGORY,
    VIEWS,
    render_category_filter_html,
    validate_product_codes,
)
from site_nav import render_site_tabs_html

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PUBLIC_DIR = ROOT_DIR / "public"
TEMPLATE_PATH = PUBLIC_DIR / "index.template.html"
OUTPUT_PATH = PUBLIC_DIR / "index.html"
# Where each non-default reporter's data gets written as its own small
# JSON file instead of being baked into index.html -- see main()'s
# "other reporters" loop and the reporter-picker JS in index.template.html,
# which fetch()es one of these the moment a different country is picked.
REPORTER_DATA_DIR = PUBLIC_DIR / "data" / "index"


def load_partners_by_year(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, list[dict]]:
    """Read <reporter>_bovine_exports_yearly_by_partner_product.csv (the
    file that keeps *both* the partner-country and product-code
    breakdowns, not collapsing either) and reshape it into one entry per
    partner per year, with quantity split out by category rather than by
    the raw CN8 code -- that's the granularity the dashboard's filters
    actually need: "how much did country X send, in category Y, in year Z."

    processed_dir defaults to the real data/processed folder, but can be
    overridden -- lets tests point it at a temporary folder with fake CSVs
    instead of touching the real data. reporter defaults to Austria (the
    file this project started with) but works for any reporter that's
    been fetched with fetch_at_history.py --reporter <code>.

    Returns a dict like:
        {"2015": [
            {"code": "TR", "name": "Türkei", "isEU": False,
             "byCategory": {"zuchtrinder_original": 1234, "young_slaughter": 0, ...},
             "byCategoryValueEur": {"zuchtrinder_original": 987654, "young_slaughter": 0, ...}},
            ...
        ], ...}

    byCategoryValueEur sits alongside byCategory (same category keys, same
    shape) rather than nesting the two numbers together, so every page
    that only ever cared about head counts keeps working unchanged -- it's
    only the new unit-toggle UI that reads byCategoryValueEur at all.
    """
    prefix = reporter.lower()
    path = processed_dir / f"{prefix}_bovine_exports_yearly_by_partner_product.csv"
    df = pd.read_csv(path, dtype={"year": str, "partner": str, "product": str})
    df["quantity"] = df["quantity"].round().astype(int)
    df["value_eur"] = df["value_eur"].round().astype(int)

    validate_product_codes(df["product"])
    # Turn each row's raw CN8 product code into one of the four category
    # keys from product_categories.py (e.g. "01022110" -> "zuchtrinder_original").
    df["category"] = df["product"].map(CODE_TO_CATEGORY)

    result: dict[str, list[dict]] = {}
    for year, year_group in df.groupby("year"):
        partners = []
        for code, partner_group in year_group.groupby("partner"):
            # Sum quantity within each category for this partner/year --
            # a partner might have several rows (one per product code) that
            # map to the same category, e.g. two different weight classes
            # both under "young_slaughter". Same idea for value_eur.
            by_category = partner_group.groupby("category")["quantity"].sum().to_dict()
            by_category_value = partner_group.groupby("category")["value_eur"].sum().to_dict()
            partners.append(
                {
                    "code": code,
                    "name": COUNTRY_NAMES.get(code, code),
                    "isEU": code in EU_MEMBERS,
                    "byCategory": {k: int(v) for k, v in by_category.items()},
                    "byCategoryValueEur": {k: int(v) for k, v in by_category_value.items()},
                }
            )
        result[year] = partners

    return dict(sorted(result.items()))


def render(
    template: str,
    partners_by_year: dict[str, list[dict]],
    years: list[str],
    reporters: list[tuple[str, str]] = REPORTERS,
) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with the real data,
    and return the finished HTML as a string.

    Takes the template's contents as plain text (rather than reading
    index.template.html itself) so this function has no file I/O of its
    own -- it's pure input-in, output-out, which is what makes it easy to
    test without needing a template file on disk.

    This uses plain str.replace() rather than a templating library
    (Jinja2 etc.) -- there's only a handful of placeholders and no loops
    or conditionals needed in the HTML itself, so a full template engine
    would be more machinery than the job requires.

    partners_by_year/years are always Austria's own data, baked directly
    into the page like before -- reporters is just the list of {code,
    name} options for the picker dropdown; picking any reporter other than
    Austria fetches that country's data from REPORTER_DATA_DIR at view
    time instead (see main()), so this function never needs the other
    reporters' actual numbers.
    """
    year_range = f"{years[0]}–{years[-1]}"

    # json.dumps turns a Python dict/list into a JSON string. ensure_ascii=False
    # keeps non-ASCII characters (e.g. the ü in Türkiye) as-is instead of
    # escaping them to \uXXXX.
    replacements = {
        "__YEAR_RANGE__": year_range,
        "__PARTNERS_BY_YEAR_JSON__": json.dumps(partners_by_year, ensure_ascii=False),
        "__YEARS_JSON__": json.dumps(years, ensure_ascii=False),
        "__REPORTERS_JSON__": json.dumps(
            [{"code": code, "name": name} for code, name in reporters], ensure_ascii=False
        ),
        "__CATEGORY_FILTER_HTML__": render_category_filter_html(),
        "__VIEWS_JSON__": json.dumps(VIEWS, ensure_ascii=False),
        "__SITE_TABS_HTML__": render_site_tabs_html("index.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def main() -> None:
    # Austria is always baked directly into the page -- it's the default
    # view and the country this project started with, so there's no
    # reason to make every visitor's first load wait on an extra fetch()
    # just to see it.
    partners_by_year = load_partners_by_year(reporter="AT")
    years = list(partners_by_year.keys())

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, partners_by_year, years)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    partner_rows = sum(len(v) for v in partners_by_year.values())
    print(f"Wrote {OUTPUT_PATH} ({len(years)} years, {partner_rows} partner rows)")

    # Every other reporter in REPORTERS gets its own small *.js* file
    # instead of being baked into the page -- NOT *.json*, and loaded via
    # a dynamically-injected <script src="..."> tag rather than fetch().
    # This matters because these pages are designed to be opened directly
    # as local files (double-click, or shared as plain files with no
    # server -- see how this site is distributed), and a plain fetch() of
    # a relative path is blocked by the browser under file:// ("Failed to
    # fetch", confirmed live in a headless-browser test) -- CORS treats
    # file:// as an opaque origin. A <script src> tag isn't subject to
    # that restriction, so each file below just assigns its data onto a
    # shared REPORTER_DATA object instead of being parsed as JSON --
    # loading it is exactly like loading any other local .js file.
    #
    # Wrapped in try/except per reporter (not one big try around the
    # loop) so one reporter that hasn't been fetched yet doesn't stop the
    # others that have from being written.
    REPORTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for code, name in REPORTERS:
        if code == "AT":
            continue
        try:
            other_partners_by_year = load_partners_by_year(reporter=code)
        except FileNotFoundError:
            print(
                f"Skipping {name} ({code}): no processed data yet -- "
                f"run fetch_at_history.py --reporter {code}"
            )
            continue
        other_years = list(other_partners_by_year.keys())
        data_path = REPORTER_DATA_DIR / f"{code.lower()}.js"
        payload = json.dumps(
            {"partnersByYear": other_partners_by_year, "years": other_years},
            ensure_ascii=False,
        )
        data_path.write_text(f"window.REPORTER_DATA['{code}'] = {payload};", encoding="utf-8")
        other_rows = sum(len(v) for v in other_partners_by_year.values())
        print(f"Wrote {data_path} ({len(other_years)} years, {other_rows} partner rows)")


# __name__ is only "__main__" when this file is run directly (`python
# scripts/build_dashboard.py`), not when a test imports its functions --
# so importing this module elsewhere won't accidentally rebuild the page.
if __name__ == "__main__":
    main()
