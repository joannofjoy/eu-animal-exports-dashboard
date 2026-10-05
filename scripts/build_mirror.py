"""Build the exploratory "AT vs. partner country" mirror-statistics page
(public/mirror.html) from data/processed/mirror_comparison.csv.

This is an internal/exploratory tool, not one of the three main
dashboards -- it exists so questions like the Croatia 2024 investigation
(docs/croatia_2024_anomaly.md) raised can be checked for *any* partner
country, interactively, instead of by hand each time. Same "bake it once,
ship a static file" approach as the other build_*.py scripts.

Run it after fetch_mirror_data.py, any time that data changes:

    python scripts/build_mirror.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from countries import COUNTRY_NAMES
from product_categories import CODE_TO_CATEGORY, VIEWS, render_category_filter_html
from project_notes import render_project_notes_html
from site_nav import render_site_tabs_html

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PUBLIC_DIR = ROOT_DIR / "public"
TEMPLATE_PATH = PUBLIC_DIR / "mirror.template.html"
OUTPUT_PATH = PUBLIC_DIR / "mirror.html"

# The four numeric columns in mirror_comparison.csv, and the key each one
# should be embedded under in the page's JSON -- one dict entry per
# measure, so a single row expands into
# {"atExportUnits": ..., "partnerImportUnits": ..., "atExportKg": ...,
#  "partnerImportKg": ...} instead of four separate top-level structures
# the page's JS would have to keep in sync with each other.
MEASURE_COLUMNS = {
    "at_export_units": "atExportUnits",
    "partner_import_units": "partnerImportUnits",
    "at_export_kg": "atExportKg",
    "partner_import_kg": "partnerImportKg",
}


def load_mirror_by_country(processed_dir: Path = PROCESSED_DIR) -> dict[str, dict[str, dict]]:
    """Read mirror_comparison.csv and reshape it into one entry per
    country, each holding every year's data broken down by category (not
    the raw CN8 code) for all four measures at once -- the granularity the
    page's category filter and unit/kg tabs both need.

    processed_dir defaults to the real data/processed folder, but can be
    overridden -- lets tests point it at a temporary folder with a fake
    CSV instead of touching the real data.

    Returns a dict like:
        {"HR": {
            "2024": {
                "atExportUnits": {"zuchtrinder_original": 4813, ...},
                "partnerImportUnits": {},
                "atExportKg": {"zuchtrinder_original": 640298, ...},
                "partnerImportKg": {},
            },
            ...
        }, ...}
    Categories with zero quantity across all their codes simply don't
    appear in a given measure's dict -- the page treats a missing key the
    same as zero (see MEASURE_COLUMNS' JS usage in mirror.template.html).
    """
    path = processed_dir / "mirror_comparison.csv"
    df = pd.read_csv(path, dtype={"year": str, "country": str, "product": str})
    df["category"] = df["product"].map(CODE_TO_CATEGORY)

    result: dict[str, dict[str, dict]] = {}
    for country, country_group in df.groupby("country"):
        by_year: dict[str, dict] = {}
        for year, year_group in country_group.groupby("year"):
            measures = {}
            for column, json_key in MEASURE_COLUMNS.items():
                by_category = year_group.groupby("category")[column].sum().astype(int).to_dict()
                # Drop categories that sum to zero -- a category with no
                # trade in either direction is noise in the embedded JSON,
                # not information (there are 4 categories x 4 measures x
                # 11 years x 21 countries of these to keep small).
                measures[json_key] = {k: v for k, v in by_category.items() if v != 0}
            by_year[year] = measures
        result[country] = dict(sorted(by_year.items()))

    return dict(sorted(result.items()))


def render(template: str, mirror_by_country: dict, countries: list[dict], years: list[str]) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with the real data
    and return the finished HTML as a string. Pure function, no file I/O --
    same reasoning as the render() functions in build_dashboard.py /
    build_map.py.
    """
    replacements = {
        "__YEAR_RANGE__": f"{years[0]}–{years[-1]}",
        "__MIRROR_BY_COUNTRY_JSON__": json.dumps(mirror_by_country, ensure_ascii=False),
        "__COUNTRIES_JSON__": json.dumps(countries, ensure_ascii=False),
        "__YEARS_JSON__": json.dumps(years, ensure_ascii=False),
        "__CATEGORY_FILTER_HTML__": render_category_filter_html(),
        "__VIEWS_JSON__": json.dumps(VIEWS, ensure_ascii=False),
        "__PROJECT_NOTES_HTML__": render_project_notes_html(),
        "__SITE_TABS_HTML__": render_site_tabs_html("mirror.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def main() -> None:
    mirror_by_country = load_mirror_by_country()

    countries = [
        {"code": code, "name": COUNTRY_NAMES.get(code, code)} for code in mirror_by_country
    ]
    countries.sort(key=lambda c: c["name"])

    years = sorted({year for by_year in mirror_by_country.values() for year in by_year})

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, mirror_by_country, countries, years)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(countries)} countries, {len(years)} years)")


if __name__ == "__main__":
    main()
