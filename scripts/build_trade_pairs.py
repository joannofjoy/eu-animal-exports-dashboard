"""Build the "paired countries" dashboard (public/trade_pairs.html) --
for a chosen partner country, shows Austria's own exports to it next to
Austria's own imports from it, per year. Both numbers come from Austria's
own declarations only (see fetch_at_imports.py's docstring for why that's
a deliberately different, simpler question than the mirror-comparison
tool in public/mirror.html, which needs a second country's data).

Same "bake it once, ship a static file" approach as the other
build_*.py scripts.

Run it after fetch_at_history.py and fetch_at_imports.py, any time either
underlying dataset changes:

    python scripts/build_trade_pairs.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from build_map import BOUNDARIES_PATH, load_country_boundary_features
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
TEMPLATE_PATH = PUBLIC_DIR / "trade_pairs.template.html"
OUTPUT_PATH = PUBLIC_DIR / "trade_pairs.html"
# Where each non-default reporter's data gets written as its own small JS
# file instead of being baked into trade_pairs.html.
REPORTER_DATA_DIR = PUBLIC_DIR / "data" / "trade_pairs"


def _load_by_category(path: Path, direction_key: str) -> pd.DataFrame:
    """Read one of the two partner-product CSVs (exports or imports) and
    collapse it from per-CN8-code rows to per-category rows, tagged with
    which direction ("atExport"/"atImport") this data represents -- so
    the two can be concatenated into one long table and pivoted together
    in load_trade_pairs_by_country(). Keeps both the quantity and
    value_eur columns (summed per category), not just quantity.
    """
    df = pd.read_csv(path, dtype={"year": str, "partner": str, "product": str})
    validate_product_codes(df["product"])
    df["category"] = df["product"].map(CODE_TO_CATEGORY)
    by_category = (
        df.groupby(["year", "partner", "category"])[["quantity", "value_eur"]].sum().reset_index()
    )
    by_category["direction"] = direction_key
    return by_category


def load_trade_pairs_by_country(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, dict[str, dict]]:
    """Combine one reporter's export and import data into one entry per
    partner country, each holding every year's quantities broken down by
    category, separately for each direction.

    processed_dir defaults to the real data/processed folder, but can be
    overridden -- lets tests point it at a temporary folder with fake
    CSVs instead of touching the real data. reporter defaults to Austria
    but works for any reporter fetch_at_history.py/fetch_at_imports.py
    have both been run for.

    Returns a dict like:
        {"CZ": {
            "2024": {
                "atExport": {"young_slaughter": 120, ...},
                "atImport": {"young_slaughter": 36819, ...},
                "atExportValueEur": {"young_slaughter": 98000, ...},
                "atImportValueEur": {"young_slaughter": 29000000, ...},
            },
            ...
        }, ...}
    A missing direction or category key means zero -- the page treats it
    the same way build_mirror.py's page does. The two *ValueEur keys sit
    alongside atExport/atImport (same category keys, same shape) rather
    than nesting quantity and value_eur together, matching the same
    additive pattern used in build_dashboard.py/build_map.py. The key
    names ("atExport"/"atImport") stay as-is regardless of reporter --
    they're a fixed vocabulary the page's JS reads, not literally "AT."
    """
    prefix = reporter.lower()
    exports = _load_by_category(
        processed_dir / f"{prefix}_bovine_exports_yearly_by_partner_product.csv", "atExport"
    )
    imports = _load_by_category(
        processed_dir / f"{prefix}_bovine_imports_yearly_by_partner_product.csv", "atImport"
    )
    combined = pd.concat([exports, imports], ignore_index=True)

    result: dict[str, dict[str, dict]] = {}
    for country, country_group in combined.groupby("partner"):
        by_year: dict[str, dict] = {}
        for year, year_group in country_group.groupby("year"):
            directions: dict[str, dict] = {
                "atExport": {},
                "atImport": {},
                "atExportValueEur": {},
                "atImportValueEur": {},
            }
            for direction, direction_group in year_group.groupby("direction"):
                by_cat = direction_group.groupby("category")["quantity"].sum().astype(int).to_dict()
                directions[direction] = {k: v for k, v in by_cat.items() if v != 0}

                by_cat_value = (
                    direction_group.groupby("category")["value_eur"].sum().astype(int).to_dict()
                )
                directions[f"{direction}ValueEur"] = {
                    k: v for k, v in by_cat_value.items() if v != 0
                }
            by_year[year] = directions
        result[country] = dict(sorted(by_year.items()))

    return dict(sorted(result.items()))


def build_partner_map_geojson(
    countries: list[dict], boundaries_path: Path = BOUNDARIES_PATH
) -> dict:
    """Country boundaries for the clickable partner-picker map, tagged
    with just enough to style them: whether Austria trades with this
    country at all ("hasData"), on top of the code/name/isEU/isExporter
    properties every map on this site already gets from
    load_country_boundary_features(). Unlike build_map.py's choropleth
    maps, this page doesn't shade countries by volume -- it only needs to
    know which ones are worth clicking, so it doesn't need the full
    per-year, per-category values dict.

    boundaries_path defaults to the real cached Natural Earth file, but
    can be overridden -- lets tests use a small hand-built GeoJSON instead
    of the real ~180-country file.
    """
    codes_with_data = {c["code"] for c in countries}
    features = load_country_boundary_features(boundaries_path)
    for feature in features:
        feature["properties"]["hasData"] = feature["properties"]["code"] in codes_with_data

    return {"type": "FeatureCollection", "features": features}


def render(
    template: str,
    trade_pairs_by_country: dict,
    countries: list[dict],
    years: list[str],
    countries_geojson: dict,
    reporters: list[tuple[str, str]] = REPORTERS,
) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with the real data
    and return the finished HTML as a string. Pure function, no file I/O --
    same reasoning as the render() functions in the other build_*.py
    scripts.

    trade_pairs_by_country/countries/years/countries_geojson are always
    Austria's own data, baked directly into the page like before --
    reporters is just the {code, name} list for the picker dropdown;
    every other reporter's data lives in its own REPORTER_DATA_DIR file
    instead (see main()).
    """
    replacements = {
        "__YEAR_RANGE__": f"{years[0]}–{years[-1]}",
        "__TRADE_PAIRS_BY_COUNTRY_JSON__": json.dumps(trade_pairs_by_country, ensure_ascii=False),
        "__COUNTRIES_JSON__": json.dumps(countries, ensure_ascii=False),
        "__YEARS_JSON__": json.dumps(years, ensure_ascii=False),
        "__COUNTRIES_GEOJSON__": json.dumps(countries_geojson, ensure_ascii=False),
        "__REPORTERS_JSON__": json.dumps(
            [{"code": code, "name": name} for code, name in reporters], ensure_ascii=False
        ),
        "__CATEGORY_FILTER_HTML__": render_category_filter_html(),
        "__VIEWS_JSON__": json.dumps(VIEWS, ensure_ascii=False),
        "__SITE_TABS_HTML__": render_site_tabs_html("trade_pairs.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def _load_reporter_bundle(reporter: str) -> tuple[dict, list[dict], list[str], dict]:
    """Loads everything one reporter needs for this page. Raises
    FileNotFoundError (uncaught here, the caller decides what to do) if
    that reporter hasn't been fetched yet (export or import side).
    """
    trade_pairs_by_country = load_trade_pairs_by_country(reporter=reporter)

    countries = [
        {"code": code, "name": COUNTRY_NAMES.get(code, code), "isEU": code in EU_MEMBERS}
        for code in trade_pairs_by_country
    ]
    countries.sort(key=lambda c: c["name"])

    years = sorted({year for by_year in trade_pairs_by_country.values() for year in by_year})
    countries_geojson = build_partner_map_geojson(countries)

    return trade_pairs_by_country, countries, years, countries_geojson


def main() -> None:
    # Austria is always baked directly into the page, same reasoning as
    # build_dashboard.py's main().
    trade_pairs_by_country, countries, years, countries_geojson = _load_reporter_bundle("AT")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, trade_pairs_by_country, countries, years, countries_geojson)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH} ({len(countries)} countries, {len(years)} years, "
        f"{len(countries_geojson['features'])} map features)"
    )

    # Every other reporter gets its own bundle written as a small JS file,
    # loaded via a dynamically-injected <script src> tag rather than
    # fetch() -- see build_dashboard.py's main() for the full reasoning.
    REPORTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for code, name in REPORTERS:
        if code == "AT":
            continue
        try:
            other_pairs, other_countries, other_years, other_geojson = _load_reporter_bundle(code)
        except FileNotFoundError:
            print(
                f"Skipping {name} ({code}): no processed data yet -- "
                f"run fetch_at_history.py/fetch_at_imports.py --reporter {code}"
            )
            continue
        data_path = REPORTER_DATA_DIR / f"{code.lower()}.js"
        payload = json.dumps(
            {
                "tradePairsByCountry": other_pairs,
                "countries": other_countries,
                "years": other_years,
                "geojson": other_geojson,
            },
            ensure_ascii=False,
        )
        data_path.write_text(f"window.REPORTER_DATA['{code}'] = {payload};", encoding="utf-8")
        print(f"Wrote {data_path} ({len(other_countries)} countries, {len(other_years)} years)")


if __name__ == "__main__":
    main()
