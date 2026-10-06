"""Build the combined tabbed dashboard page (public/dashboard.html) --
both dashboard 1 (yearly totals + top partners) and dashboard 2 (map) on
one page, switchable via tabs, for anyone who wants both without
navigating between the two standalone pages.

Reuses the same data-loading functions as build_dashboard.py and
build_map.py (imported, not duplicated) -- this script's only new job is
filling in a template that has both dashboards' markup/JS side by side
with a tab switcher on top. The standalone pages (index.html / map.html)
still get built separately too; nothing here changes them.

Run it after fetch_at_history.py and fetch_world_boundaries.py, any time
the underlying data changes:

    python scripts/build_site.py
"""

from __future__ import annotations

import json
from pathlib import Path

from build_dashboard import load_partners_by_year
from build_map import build_choropleth_geojson, load_values_by_country
from product_categories import VIEWS, render_category_filter_html
from site_nav import render_site_tabs_html

ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "public"
TEMPLATE_PATH = PUBLIC_DIR / "dashboard.template.html"
OUTPUT_PATH = PUBLIC_DIR / "dashboard.html"


def render(
    template: str,
    partners_by_year: dict[str, list[dict]],
    geojson: dict,
    years: list[str],
) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with the real data
    and return the finished HTML as a string. Pure function, no file I/O --
    same reasoning as the render() functions in build_dashboard.py /
    build_map.py.
    """
    replacements = {
        "__YEAR_RANGE__": f"{years[0]}–{years[-1]}",
        "__PARTNERS_BY_YEAR_JSON__": json.dumps(partners_by_year, ensure_ascii=False),
        "__COUNTRIES_GEOJSON__": json.dumps(geojson, ensure_ascii=False),
        "__YEARS_JSON__": json.dumps(years, ensure_ascii=False),
        "__CATEGORY_FILTER_HTML__": render_category_filter_html(),
        "__VIEWS_JSON__": json.dumps(VIEWS, ensure_ascii=False),
        "__SITE_TABS_HTML__": render_site_tabs_html("dashboard.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def main() -> None:
    partners_by_year = load_partners_by_year()
    values_by_country = load_values_by_country()
    geojson = build_choropleth_geojson(values_by_country)

    # partners_by_year is already sorted ascending by year (see
    # load_partners_by_year's docstring), so its keys are already in the
    # right order -- both tabs end up agreeing on which years exist.
    years = list(partners_by_year.keys())

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, partners_by_year, geojson, years)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(years)} years, {len(geojson['features'])} countries)")


if __name__ == "__main__":
    main()
