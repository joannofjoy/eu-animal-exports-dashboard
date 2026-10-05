"""Build the month-by-month dashboard page (public/monthly.html) --
adds the one thing the other pages can't show: a within-year monthly time
series, next to the same per-partner bar chart and map the other pages
already use for a selected year. Still Austria-only, still just live
cattle -- see fetch_at_history.py's aggregate_monthly() for where the
month-level data comes from.

Same "bake it once, ship a static file" approach as the other build_*.py
scripts. Reuses load_partners_by_year() and the map-building functions
from build_dashboard.py/build_map.py rather than duplicating them -- only
the monthly breakdown is genuinely new here.

Run it after fetch_at_history.py and fetch_world_boundaries.py, any time
the underlying data changes:

    python scripts/build_monthly.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from build_dashboard import load_partners_by_year
from build_map import (
    build_choropleth_geojson,
    load_values_by_country,
    load_values_eur_by_country,
)
from countries import COUNTRY_NAMES, EU_MEMBERS, REPORTERS
from product_categories import CODE_TO_CATEGORY, VIEWS, render_category_filter_html
from project_notes import render_project_notes_html
from site_nav import render_site_tabs_html

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PUBLIC_DIR = ROOT_DIR / "public"
TEMPLATE_PATH = PUBLIC_DIR / "monthly.template.html"
OUTPUT_PATH = PUBLIC_DIR / "monthly.html"
# Where each non-default reporter's data gets written as its own small JS
# file instead of being baked into monthly.html -- see main()'s "other
# reporters" loop and the reporter-picker JS in monthly.template.html.
REPORTER_DATA_DIR = PUBLIC_DIR / "data" / "monthly"


def load_monthly_by_year(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, dict[str, list[dict]]]:
    """Read <reporter>_bovine_exports_monthly_by_partner_product.csv and
    reshape it into one entry per year, each holding every month's
    partners with a category breakdown -- the same per-partner shape
    build_dashboard.py's load_partners_by_year() uses, just with an extra
    "month" level in between, so the page's category *and* geography
    filters both work exactly the same way they already do everywhere
    else in this project.

    processed_dir defaults to the real data/processed folder, but can be
    overridden -- lets tests point it at a temporary folder with a fake
    CSV instead of touching the real data. reporter defaults to Austria
    but works for any reporter fetch_at_history.py has been run for.

    Returns a dict like:
        {"2024": {
            "2024-01": [
                {"code": "CZ", "name": "Czechia", "isEU": True,
                 "byCategory": {"young_slaughter": 2800, ...},
                 "byCategoryValueEur": {"young_slaughter": 1904000, ...}},
                ...
            ],
            ...
        }, ...}

    byCategoryValueEur sits alongside byCategory, same reasoning as
    build_dashboard.py's load_partners_by_year().
    """
    prefix = reporter.lower()
    path = processed_dir / f"{prefix}_bovine_exports_monthly_by_partner_product.csv"
    df = pd.read_csv(path, dtype={"month": str, "partner": str, "product": str})
    df["quantity"] = df["quantity"].round().astype(int)
    df["value_eur"] = df["value_eur"].round().astype(int)
    df["category"] = df["product"].map(CODE_TO_CATEGORY)
    df["year"] = df["month"].str.slice(0, 4)

    result: dict[str, dict[str, list[dict]]] = {}
    for year, year_group in df.groupby("year"):
        by_month: dict[str, list[dict]] = {}
        for month, month_group in year_group.groupby("month"):
            partners = []
            for code, partner_group in month_group.groupby("partner"):
                by_category = partner_group.groupby("category")["quantity"].sum().to_dict()
                by_category_value = (
                    partner_group.groupby("category")["value_eur"].sum().to_dict()
                )
                partners.append(
                    {
                        "code": code,
                        "name": COUNTRY_NAMES.get(code, code),
                        "isEU": code in EU_MEMBERS,
                        "byCategory": {k: int(v) for k, v in by_category.items()},
                        "byCategoryValueEur": {
                            k: int(v) for k, v in by_category_value.items()
                        },
                    }
                )
            by_month[month] = partners
        result[year] = dict(sorted(by_month.items()))

    return dict(sorted(result.items()))


def render(
    template: str,
    partners_by_year: dict[str, list[dict]],
    monthly_by_year: dict[str, dict[str, list[dict]]],
    geojson: dict,
    years: list[str],
    reporters: list[tuple[str, str]] = REPORTERS,
) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with the real data
    and return the finished HTML as a string. Pure function, no file I/O --
    same reasoning as the render() functions in the other build_*.py
    scripts.

    partners_by_year/monthly_by_year/geojson/years are always Austria's
    own data, baked directly into the page like before -- reporters is
    just the {code, name} list for the picker dropdown; every other
    reporter's data lives in its own REPORTER_DATA_DIR file instead (see
    main()).
    """
    replacements = {
        "__YEAR_RANGE__": f"{years[0]}–{years[-1]}",
        "__PARTNERS_BY_YEAR_JSON__": json.dumps(partners_by_year, ensure_ascii=False),
        "__MONTHLY_BY_YEAR_JSON__": json.dumps(monthly_by_year, ensure_ascii=False),
        "__COUNTRIES_GEOJSON__": json.dumps(geojson, ensure_ascii=False),
        "__YEARS_JSON__": json.dumps(years, ensure_ascii=False),
        "__REPORTERS_JSON__": json.dumps(
            [{"code": code, "name": name} for code, name in reporters], ensure_ascii=False
        ),
        "__CATEGORY_FILTER_HTML__": render_category_filter_html(),
        "__VIEWS_JSON__": json.dumps(VIEWS, ensure_ascii=False),
        "__PROJECT_NOTES_HTML__": render_project_notes_html(),
        "__SITE_TABS_HTML__": render_site_tabs_html("monthly.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def _load_reporter_bundle(reporter: str) -> tuple[dict, dict, dict, list[str]]:
    """Loads everything one reporter needs for this page -- the three
    data shapes main() bakes for Austria and writes as a JS file for
    every other reporter. Raises FileNotFoundError (uncaught here, the
    caller decides what to do) if that reporter hasn't been fetched yet.
    """
    partners_by_year = load_partners_by_year(reporter=reporter)
    monthly_by_year = load_monthly_by_year(reporter=reporter)
    values_by_country = load_values_by_country(reporter=reporter)
    values_eur_by_country = load_values_eur_by_country(reporter=reporter)
    geojson = build_choropleth_geojson(
        values_by_country, values_eur_by_country=values_eur_by_country
    )
    years = list(partners_by_year.keys())
    return partners_by_year, monthly_by_year, geojson, years


def main() -> None:
    # Austria is always baked directly into the page, same reasoning as
    # build_dashboard.py's main().
    partners_by_year, monthly_by_year, geojson, years = _load_reporter_bundle("AT")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, partners_by_year, monthly_by_year, geojson, years)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(years)} years, {len(geojson['features'])} countries)")

    # Every other reporter gets its own bundle written as a small JS file,
    # loaded via a dynamically-injected <script src> tag rather than
    # fetch() -- see build_dashboard.py's main() for the full reasoning.
    REPORTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for code, name in REPORTERS:
        if code == "AT":
            continue
        try:
            other_partners, other_monthly, other_geojson, other_years = _load_reporter_bundle(
                code
            )
        except FileNotFoundError:
            print(
                f"Skipping {name} ({code}): no processed data yet -- "
                f"run fetch_at_history.py --reporter {code}"
            )
            continue
        data_path = REPORTER_DATA_DIR / f"{code.lower()}.js"
        payload = json.dumps(
            {
                "partnersByYear": other_partners,
                "monthlyByYear": other_monthly,
                "geojson": other_geojson,
                "years": other_years,
            },
            ensure_ascii=False,
        )
        data_path.write_text(f"window.REPORTER_DATA['{code}'] = {payload};", encoding="utf-8")
        print(
            f"Wrote {data_path} ({len(other_years)} years, "
            f"{len(other_geojson['features'])} countries)"
        )


if __name__ == "__main__":
    main()
