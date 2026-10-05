"""Tests for scripts/build_map.py.

Like tests/test_build_dashboard.py, these use small temporary files
(tmp_path) rather than the real ~180-country Natural Earth file or the
project's real export data.
"""

import json

from build_map import (
    build_choropleth_geojson,
    load_values_by_country,
    load_values_eur_by_country,
    render,
)


def test_load_values_by_country_groups_by_country_year_and_category(tmp_path):
    csv_path = tmp_path / "at_bovine_exports_yearly_by_partner_product.csv"
    csv_path.write_text(
        "year,partner,product,quantity,value_eur\n"
        "2015,DE,01022110,100,80000\n"  # zuchtrinder_original
        "2015,DE,01022921,20,14000\n"  # young_slaughter
        "2016,DE,01022110,120,96000\n"
        "2015,TR,01022905,5000,3200000\n"  # other_unclassified
    )

    values = load_values_by_country(tmp_path)

    assert values == {
        "DE": {
            "2015": {"zuchtrinder_original": 100, "young_slaughter": 20},
            "2016": {"zuchtrinder_original": 120},
        },
        "TR": {"2015": {"other_unclassified": 5000}},
    }

    # Same CSV, same shape, but the euro column instead of the head
    # count -- proves _load_by_country()'s value_column switch actually
    # picks a different column rather than always returning quantity.
    values_eur = load_values_eur_by_country(tmp_path)

    assert values_eur == {
        "DE": {
            "2015": {"zuchtrinder_original": 80000, "young_slaughter": 14000},
            "2016": {"zuchtrinder_original": 96000},
        },
        "TR": {"2015": {"other_unclassified": 3200000}},
    }


def _fake_boundaries(tmp_path):
    """A 3-country stand-in for the real ~180-feature Natural Earth file:
    DE (has trade data, has a name in our own COUNTRY_NAMES, is an EU
    member), AT (the exporter itself), and a made-up "ZZ" with no
    COUNTRY_NAMES entry, no trade data, and not an EU member -- to check
    the NAME_EN fallback and the "no data" case.
    """
    path = tmp_path / "boundaries.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "properties": {
                            "ISO_A2": "DE",
                            "NAME_EN": "Germany (Natural Earth)",
                            "POP_EST": 83000000,  # a column we don't use, should be dropped
                        },
                        "geometry": {"type": "Point", "coordinates": [10, 51]},
                    },
                    {
                        "properties": {"ISO_A2": "AT", "NAME_EN": "Austria"},
                        "geometry": {"type": "Point", "coordinates": [14, 47]},
                    },
                    {
                        "properties": {"ISO_A2": "ZZ", "NAME_EN": "Nowhereland"},
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                    },
                ],
            }
        )
    )
    return path


def test_build_choropleth_geojson_joins_values_and_marks_exporter(tmp_path):
    boundaries_path = _fake_boundaries(tmp_path)
    values_by_country = {"DE": {"2015": {"zuchtrinder_original": 100}}}

    geojson = build_choropleth_geojson(values_by_country, boundaries_path)
    by_code = {f["properties"]["code"]: f["properties"] for f in geojson["features"]}

    # DE: has trade data and is in our own COUNTRY_NAMES -- should use our
    # name ("Germany"), not Natural Earth's ("Germany (Natural Earth)"),
    # should carry the values dict but no unrelated columns like POP_EST,
    # and should be flagged as an EU member.
    assert by_code["DE"]["name"] == "Germany"
    assert by_code["DE"]["values"] == {"2015": {"zuchtrinder_original": 100}}
    assert by_code["DE"]["isEU"] is True
    assert "POP_EST" not in by_code["DE"]
    assert "isExporter" not in by_code["DE"]

    # AT: the exporter itself, no trade data of its own (it never appears
    # as a "partner"), flagged separately instead.
    assert by_code["AT"]["isExporter"] is True
    assert "values" not in by_code["AT"]

    # ZZ: not in our own COUNTRY_NAMES, has no trade data, and is not an
    # EU member -- falls back to Natural Earth's own English name, no
    # values dict.
    assert by_code["ZZ"]["name"] == "Nowhereland"
    assert by_code["ZZ"]["isEU"] is False
    assert "values" not in by_code["ZZ"]

    # Geometry must survive untouched -- it's the whole point of the file.
    de_feature = next(f for f in geojson["features"] if f["properties"]["code"] == "DE")
    assert de_feature["geometry"] == {"type": "Point", "coordinates": [10, 51]}


def test_build_choropleth_geojson_attaches_optional_eur_values(tmp_path):
    boundaries_path = _fake_boundaries(tmp_path)
    values_by_country = {"DE": {"2015": {"zuchtrinder_original": 100}}}
    values_eur_by_country = {"DE": {"2015": {"zuchtrinder_original": 987654}}}

    geojson = build_choropleth_geojson(
        values_by_country, boundaries_path, values_eur_by_country=values_eur_by_country
    )
    by_code = {f["properties"]["code"]: f["properties"] for f in geojson["features"]}

    assert by_code["DE"]["valuesEur"] == {"2015": {"zuchtrinder_original": 987654}}
    # ZZ has neither animal-count nor euro trade data -- no key at all,
    # not an empty dict, so the frontend's own `if (!props.valuesEur)`
    # checks keep working unchanged.
    assert "valuesEur" not in by_code["ZZ"]

    # Omitting values_eur_by_country entirely (the default) must not
    # attach the key anywhere, for callers that only care about counts.
    geojson_no_eur = build_choropleth_geojson(values_by_country, boundaries_path)
    assert all("valuesEur" not in f["properties"] for f in geojson_no_eur["features"])


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "const countriesGeoJson = __COUNTRIES_GEOJSON__;"
        "const years = __YEARS_JSON__;"
        "</script>"
        '<div id="categoryFilter">__CATEGORY_FILTER_HTML__</div>'
        '<div class="footer">__PROJECT_NOTES_HTML__</div>'
    )
    geojson = {"type": "FeatureCollection", "features": []}
    years = ["2015", "2016"]

    html = render(template, geojson, years)

    assert "__" not in html
    assert "<title>2015–2016</title>" in html

    start = html.index("const countriesGeoJson = ") + len("const countriesGeoJson = ")
    end = html.index(";", start)
    assert json.loads(html[start:end]) == geojson

    assert 'class="viewRadio" value="calves"' in html
    assert '<details class="notes">' in html
