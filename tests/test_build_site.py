"""Tests for scripts/build_site.py.

Only render() is tested here -- the load_partners_by_year/
build_choropleth_geojson/load_values_by_country functions it calls are
already covered by tests/test_build_dashboard.py and tests/test_build_map.py
(build_site.py imports them rather than duplicating them, so there's
nothing new to test there).
"""

import json

from build_site import render


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "const partnersByYear = __PARTNERS_BY_YEAR_JSON__;"
        "const countriesGeoJson = __COUNTRIES_GEOJSON__;"
        "const years = __YEARS_JSON__;"
        "</script>"
        '<div id="categoryFilter">__CATEGORY_FILTER_HTML__</div>'
        '<div class="footer"></div>'
    )
    partners_by_year = {
        "2023": [
            {
                "code": "FR",
                "name": "Frankreich",
                "isEU": True,
                "byCategory": {"zuchtrinder_original": 200},
            }
        ],
        "2024": [],
    }
    geojson = {"type": "FeatureCollection", "features": []}
    years = ["2023", "2024"]

    html = render(template, partners_by_year, geojson, years)

    assert "__" not in html
    assert "<title>2023–2024</title>" in html

    for name, expected in [
        ("partnersByYear", partners_by_year),
        ("countriesGeoJson", geojson),
        ("years", years),
    ]:
        start = html.index(f"const {name} = ") + len(f"const {name} = ")
        end = html.index(";", start)
        assert json.loads(html[start:end]) == expected

    assert 'class="viewRadio" value="calves"' in html
