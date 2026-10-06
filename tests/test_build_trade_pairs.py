"""Tests for scripts/build_trade_pairs.py.

Like tests/test_build_mirror.py, these use small temporary CSVs
(tmp_path) rather than the project's real processed data.
"""

import json

from build_trade_pairs import build_partner_map_geojson, load_trade_pairs_by_country, render


def test_load_trade_pairs_by_country_combines_exports_and_imports(tmp_path):
    exports_path = tmp_path / "at_bovine_exports_yearly_by_partner_product.csv"
    exports_path.write_text(
        "year,partner,product,quantity,value_eur\n"
        "2024,CZ,01022110,120,96000\n"  # zuchtrinder_original
        "2024,CZ,01022921,30,21000\n"  # young_slaughter
    )
    imports_path = tmp_path / "at_bovine_imports_yearly_by_partner_product.csv"
    imports_path.write_text(
        "year,partner,product,quantity,value_eur\n"
        # young_slaughter -- CZ is AT's biggest cattle supplier
        "2024,CZ,01022921,36819,28900000\n"
    )

    trade_pairs = load_trade_pairs_by_country(tmp_path)

    assert set(trade_pairs.keys()) == {"CZ"}
    cz_2024 = trade_pairs["CZ"]["2024"]
    assert cz_2024["atExport"] == {"zuchtrinder_original": 120, "young_slaughter": 30}
    assert cz_2024["atImport"] == {"young_slaughter": 36819}
    assert cz_2024["atExportValueEur"] == {"zuchtrinder_original": 96000, "young_slaughter": 21000}
    assert cz_2024["atImportValueEur"] == {"young_slaughter": 28900000}


def test_load_trade_pairs_by_country_handles_export_only_partner(tmp_path):
    # A country AT exports to but has never imported from (or vice versa)
    # should still show up, with the missing direction as an empty dict
    # rather than crashing or being dropped entirely.
    exports_path = tmp_path / "at_bovine_exports_yearly_by_partner_product.csv"
    exports_path.write_text(
        "year,partner,product,quantity,value_eur\n2024,HR,01022110,4813,3800000\n"
    )
    imports_path = tmp_path / "at_bovine_imports_yearly_by_partner_product.csv"
    imports_path.write_text("year,partner,product,quantity,value_eur\n")

    trade_pairs = load_trade_pairs_by_country(tmp_path)

    hr_2024 = trade_pairs["HR"]["2024"]
    assert hr_2024["atExport"] == {"zuchtrinder_original": 4813}
    assert hr_2024["atImport"] == {}
    assert hr_2024["atExportValueEur"] == {"zuchtrinder_original": 3800000}
    assert hr_2024["atImportValueEur"] == {}


def _fake_boundaries(tmp_path):
    """A 3-country stand-in for the real Natural Earth file -- DE (a
    trade partner), AT (the exporter), and ZZ (a country Austria has
    never traded cattle with), to check the hasData flag both ways.
    """
    path = tmp_path / "boundaries.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "properties": {"ISO_A2": "DE", "NAME_EN": "Germany"},
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


def test_build_partner_map_geojson_flags_countries_with_trade_data(tmp_path):
    boundaries_path = _fake_boundaries(tmp_path)
    countries = [{"code": "DE", "name": "Germany", "isEU": True}]

    geojson = build_partner_map_geojson(countries, boundaries_path)
    by_code = {f["properties"]["code"]: f["properties"] for f in geojson["features"]}

    assert by_code["DE"]["hasData"] is True
    assert by_code["ZZ"]["hasData"] is False
    # AT is the exporter, not a "partner" -- it never has trade data of
    # its own in this dataset, but it's still flagged as the exporter so
    # the page can style it distinctly from an ordinary no-data country.
    assert by_code["AT"]["hasData"] is False
    assert by_code["AT"]["isExporter"] is True


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "const tradePairsByCountry = __TRADE_PAIRS_BY_COUNTRY_JSON__;"
        "const countries = __COUNTRIES_JSON__;"
        "const years = __YEARS_JSON__;"
        "const countriesGeoJson = __COUNTRIES_GEOJSON__;"
        "</script>"
        '<div id="categoryFilter">__CATEGORY_FILTER_HTML__</div>'
        '<div class="footer"></div>'
    )
    trade_pairs_by_country = {
        "CZ": {"2024": {"atExport": {"schlachtrinder": 30}, "atImport": {"schlachtrinder": 36819}}}
    }
    countries = [{"code": "CZ", "name": "Tschechien", "isEU": True}]
    years = ["2023", "2024"]
    countries_geojson = {"type": "FeatureCollection", "features": []}

    html = render(template, trade_pairs_by_country, countries, years, countries_geojson)

    assert "__" not in html
    assert "<title>2023–2024</title>" in html

    for name, expected in [
        ("tradePairsByCountry", trade_pairs_by_country),
        ("countries", countries),
        ("years", years),
        ("countriesGeoJson", countries_geojson),
    ]:
        start = html.index(f"const {name} = ") + len(f"const {name} = ")
        end = html.index(";", start)
        assert json.loads(html[start:end]) == expected

    assert 'class="viewRadio" value="calves"' in html
