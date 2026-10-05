"""Build the static map dashboard page (public/map.html) -- a Leaflet
choropleth of AT's export destinations, colored by export volume, with a
year slider.

Same "bake it once, ship a static file" approach as build_dashboard.py:
this script joins Austria's per-year, per-country export totals onto real
country boundary shapes (from data/raw/ne_110m_admin_0_countries.geojson,
see scripts/fetch_world_boundaries.py) and embeds the result directly into
the page. No server, no API calls at view time -- just like dashboard 1.

Run it after fetch_at_history.py and fetch_world_boundaries.py, any time
the underlying data changes:

    python scripts/build_map.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from countries import COUNTRY_NAMES, EU_MEMBERS, REPORTERS
from product_categories import CODE_TO_CATEGORY, VIEWS, render_category_filter_html
from project_notes import render_project_notes_html
from site_nav import render_site_tabs_html

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PUBLIC_DIR = ROOT_DIR / "public"
BOUNDARIES_PATH = RAW_DIR / "ne_110m_admin_0_countries.geojson"
TEMPLATE_PATH = PUBLIC_DIR / "map.template.html"
OUTPUT_PATH = PUBLIC_DIR / "map.html"
# Where each non-default reporter's full geojson gets written as its own
# small(ish) JS file instead of being baked into map.html -- see main()'s
# "other reporters" loop and the reporter-picker JS in map.template.html.
REPORTER_DATA_DIR = PUBLIC_DIR / "data" / "map"

# Austria is the exporter, not a destination -- it never appears as a
# "partner" row in the data, but the map highlights it separately so it's
# clear where the exports are coming from.
EXPORTER_ISO2 = "AT"


def load_values_by_country(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, dict[str, dict[str, int]]]:
    """Read <reporter>_bovine_exports_yearly_by_partner_product.csv (the
    file that keeps both the partner-country and product-code breakdowns)
    and reshape it into one entry per country, each holding every year's
    quantity broken down by category (not collapsed to one number) -- the
    same category-level granularity build_dashboard.py uses, needed here
    so the map's category filter can recompute which countries have data
    for whatever categories are currently selected.

    processed_dir defaults to the real data/processed folder, but can be
    overridden -- lets tests point it at a temporary folder with fake CSVs
    instead of touching the real data. reporter defaults to Austria but
    works for any reporter fetch_at_history.py has been run for.

    Returns a dict like:
        {"TR": {"2015": {"zuchtrinder_original": 500, "young_slaughter": 10000, ...}, ...}, ...}
    """
    return _load_by_country(processed_dir, "quantity", reporter)


def load_values_eur_by_country(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, dict[str, dict[str, int]]]:
    """Same shape and reasoning as load_values_by_country() above, but
    the trade value in euros instead of the animal head count -- kept as
    a separate function (rather than folding both numbers into one nested
    dict) so a page that only ever shows head counts, like the choropleth
    map currently does, can keep calling load_values_by_country() alone
    and never has to know this one exists.
    """
    return _load_by_country(processed_dir, "value_eur", reporter)


def _load_by_country(
    processed_dir: Path, value_column: str, reporter: str = "AT"
) -> dict[str, dict[str, dict[str, int]]]:
    """Shared logic behind load_values_by_country() and
    load_values_eur_by_country() -- value_column picks which of the two
    numeric columns (quantity or value_eur) gets summed per category.
    """
    path = processed_dir / f"{reporter.lower()}_bovine_exports_yearly_by_partner_product.csv"
    df = pd.read_csv(path, dtype={"year": str, "partner": str, "product": str})
    df[value_column] = df[value_column].round().astype(int)
    df["category"] = df["product"].map(CODE_TO_CATEGORY)

    by_country: dict[str, dict[str, dict[str, int]]] = {}
    for code, country_group in df.groupby("partner"):
        by_year: dict[str, dict[str, int]] = {}
        for year, year_group in country_group.groupby("year"):
            by_category = year_group.groupby("category")[value_column].sum().to_dict()
            by_year[year] = {k: int(v) for k, v in by_category.items()}
        by_country[code] = by_year

    return by_country


def build_choropleth_geojson(
    values_by_country: dict[str, dict[str, dict[str, int]]],
    boundaries_path: Path = BOUNDARIES_PATH,
    values_eur_by_country: dict[str, dict[str, dict[str, int]]] | None = None,
) -> dict:
    """Load the Natural Earth world boundaries and attach our export data
    to each matching country feature.

    The source file has ~40 columns per country (population, GDP, names
    in a dozen languages, ...) that this project has no use for -- keeping
    all of that would roughly double the size of a file that's about to
    get embedded directly into a webpage. This rebuilds each feature with
    only the properties the map actually uses: its ISO2 code, a display
    name, EU membership, and (if we have trade data for it) that per-year,
    per-category values dict.

    values_eur_by_country is optional and, when given, gets attached
    alongside values as "valuesEur" (same shape, same reasoning as
    build_dashboard.py's byCategoryValueEur sitting next to byCategory) --
    lets the map's unit toggle switch between animal counts and trade
    value without a second GeoJSON. Optional so callers that only ever
    cared about head counts (tests, mainly) don't have to pass it.

    boundaries_path defaults to the real cached Natural Earth file, but
    can be overridden -- lets tests use a small hand-built GeoJSON instead
    of the real ~180-country file.
    """
    features = load_country_boundary_features(boundaries_path)
    for feature in features:
        code = feature["properties"]["code"]
        if code in values_by_country:
            feature["properties"]["values"] = values_by_country[code]
        if values_eur_by_country and code in values_eur_by_country:
            feature["properties"]["valuesEur"] = values_eur_by_country[code]

    return {"type": "FeatureCollection", "features": features}


def load_country_boundary_features(boundaries_path: Path = BOUNDARIES_PATH) -> list[dict]:
    """Load the Natural Earth world boundaries with just the properties
    every map-driven page needs regardless of what data it's showing:
    a corrected ISO2 code, a display name, EU membership, and whether
    this is Austria (the exporter). Callers attach their own per-page
    data on top -- build_choropleth_geojson() above attaches per-year
    export values; build_trade_pairs.py attaches a simpler "does Austria
    trade with this country at all" flag instead, since its map doesn't
    need a full value breakdown.
    """
    raw = json.loads(boundaries_path.read_text(encoding="utf-8"))

    features = []
    for feature in raw["features"]:
        # Natural Earth's ISO_A2 field has a long-documented bug: France,
        # Norway, Kosovo, Northern Cyprus, and Somaliland all get the
        # placeholder "-99" instead of a real code, which made all five
        # collide as one "country" on this map -- selecting/coloring one
        # selected/colored all of them, and both France and Norway's real
        # export data silently never attached to their map feature since
        # neither is ever keyed "-99" in our own Eurostat-sourced data.
        # ISO_A2_EH ("expanded") is Natural Earth's own fix for this and
        # resolves correctly for France/Norway/Kosovo; Northern Cyprus and
        # Somaliland still fall back to "-99" (still collide with each
        # other), but neither is ever a distinct Eurostat trade partner in
        # this dataset, so that residual collision has no visible effect.
        code = feature["properties"].get("ISO_A2_EH")
        if not code or code == "-99":
            code = feature["properties"]["ISO_A2"]
        # Prefer our own English name (matches dashboard 1's labels exactly
        # for every country that actually has trade data); fall back to
        # Natural Earth's own English name for the rest of the world, which
        # only ever shows up as "no data" background on this map.
        name = COUNTRY_NAMES.get(code) or feature["properties"].get("NAME_EN") or code

        properties = {"code": code, "name": name, "isEU": code in EU_MEMBERS}
        if code == EXPORTER_ISO2:
            properties["isExporter"] = True

        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": feature["geometry"],
            }
        )

    return features


def render(
    template: str,
    geojson: dict,
    years: list[str],
    reporters: list[tuple[str, str]] = REPORTERS,
) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with the real data
    and return the finished HTML as a string. Pure function, no file I/O,
    same reasoning as build_dashboard.py's render() -- see there for why.

    geojson/years are always Austria's own data, baked directly into the
    page like before -- reporters is just the {code, name} list for the
    picker dropdown; every other reporter's full geojson lives in its own
    REPORTER_DATA_DIR file instead (see main()).
    """
    replacements = {
        "__YEAR_RANGE__": f"{years[0]}–{years[-1]}",
        "__COUNTRIES_GEOJSON__": json.dumps(geojson, ensure_ascii=False),
        "__YEARS_JSON__": json.dumps(years, ensure_ascii=False),
        "__REPORTERS_JSON__": json.dumps(
            [{"code": code, "name": name} for code, name in reporters], ensure_ascii=False
        ),
        "__CATEGORY_FILTER_HTML__": render_category_filter_html(),
        "__VIEWS_JSON__": json.dumps(VIEWS, ensure_ascii=False),
        "__PROJECT_NOTES_HTML__": render_project_notes_html(),
        "__SITE_TABS_HTML__": render_site_tabs_html("map.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def main() -> None:
    # Austria is always baked directly into the page, same reasoning as
    # build_dashboard.py's main().
    values_by_country = load_values_by_country(reporter="AT")
    values_eur_by_country = load_values_eur_by_country(reporter="AT")
    geojson = build_choropleth_geojson(
        values_by_country, values_eur_by_country=values_eur_by_country
    )

    # Years come from the same processed data dashboard 1 uses, so both
    # pages always agree on which years exist.
    years = sorted({year for values in values_by_country.values() for year in values})

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, geojson, years)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(geojson['features'])} countries, {len(years)} years)")

    # Every other reporter gets its own full geojson written as a small JS
    # file (window.REPORTER_DATA[code] = {...}), loaded via a
    # dynamically-injected <script src> tag rather than fetch() -- see
    # build_dashboard.py's main() for the full reasoning (fetch() of a
    # local file is blocked under file://, confirmed live; a <script src>
    # tag isn't).
    REPORTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for code, name in REPORTERS:
        if code == "AT":
            continue
        try:
            other_values = load_values_by_country(reporter=code)
            other_values_eur = load_values_eur_by_country(reporter=code)
        except FileNotFoundError:
            print(
                f"Skipping {name} ({code}): no processed data yet -- "
                f"run fetch_at_history.py --reporter {code}"
            )
            continue
        other_geojson = build_choropleth_geojson(
            other_values, values_eur_by_country=other_values_eur
        )
        other_years = sorted({year for values in other_values.values() for year in values})
        data_path = REPORTER_DATA_DIR / f"{code.lower()}.js"
        payload = json.dumps(
            {"geojson": other_geojson, "years": other_years}, ensure_ascii=False
        )
        data_path.write_text(f"window.REPORTER_DATA['{code}'] = {payload};", encoding="utf-8")
        print(
            f"Wrote {data_path} ({len(other_geojson['features'])} countries, "
            f"{len(other_years)} years)"
        )


if __name__ == "__main__":
    main()
