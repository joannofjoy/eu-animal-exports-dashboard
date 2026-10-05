"""Tests for scripts/build_monthly.py.

Like tests/test_build_dashboard.py, load_monthly_by_year() is tested
against a small temporary CSV (tmp_path) rather than the project's real
processed data. load_partners_by_year() and the map-building functions
this script reuses are already covered by their own test files.
"""

import json

from build_monthly import load_monthly_by_year, render


def test_load_monthly_by_year_keeps_months_separate_within_a_year(tmp_path):
    csv_path = tmp_path / "at_bovine_exports_monthly_by_partner_product.csv"
    csv_path.write_text(
        "month,partner,product,quantity,value_eur\n"
        # CZ, Jan 2024: two products mapping to two different categories.
        "2024-01,CZ,01022110,50,40000\n"  # zuchtrinder_original
        "2024-01,CZ,01022921,30,21000\n"  # young_slaughter
        # CZ, Feb 2024: a different month is a separate entry entirely.
        "2024-02,CZ,01022110,10,9000\n"
        # TR, Jan 2024: not an EU member, checks the isEU flag.
        "2024-01,TR,01022905,5,3000\n"  # other_unclassified
    )

    monthly_by_year = load_monthly_by_year(tmp_path)

    assert list(monthly_by_year.keys()) == ["2024"]
    assert list(monthly_by_year["2024"].keys()) == ["2024-01", "2024-02"]

    by_code_jan = {p["code"]: p for p in monthly_by_year["2024"]["2024-01"]}
    assert by_code_jan["CZ"]["name"] == "Czechia"
    assert by_code_jan["CZ"]["isEU"] is True
    assert by_code_jan["CZ"]["byCategory"] == {"zuchtrinder_original": 50, "young_slaughter": 30}
    assert by_code_jan["CZ"]["byCategoryValueEur"] == {
        "zuchtrinder_original": 40000,
        "young_slaughter": 21000,
    }
    assert by_code_jan["TR"]["isEU"] is False
    assert by_code_jan["TR"]["byCategory"] == {"other_unclassified": 5}
    assert by_code_jan["TR"]["byCategoryValueEur"] == {"other_unclassified": 3000}

    assert monthly_by_year["2024"]["2024-02"] == [
        {
            "code": "CZ",
            "name": "Czechia",
            "isEU": True,
            "byCategory": {"zuchtrinder_original": 10},
            "byCategoryValueEur": {"zuchtrinder_original": 9000},
        }
    ]


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "const partnersByYear = __PARTNERS_BY_YEAR_JSON__;"
        "const monthlyByYear = __MONTHLY_BY_YEAR_JSON__;"
        "const countriesGeoJson = __COUNTRIES_GEOJSON__;"
        "const years = __YEARS_JSON__;"
        "</script>"
        '<div id="categoryFilter">__CATEGORY_FILTER_HTML__</div>'
        '<div class="footer">__PROJECT_NOTES_HTML__</div>'
    )
    partners_by_year = {
        "2024": [
            {"code": "CZ", "name": "Czechia", "isEU": True, "byCategory": {"schlachtrinder": 30}}
        ]
    }
    monthly_by_year = {
        "2024": {
            "2024-01": [
                {
                    "code": "CZ",
                    "name": "Czechia",
                    "isEU": True,
                    "byCategory": {"schlachtrinder": 30},
                }
            ]
        }
    }
    geojson = {"type": "FeatureCollection", "features": []}
    years = ["2023", "2024"]

    html = render(template, partners_by_year, monthly_by_year, geojson, years)

    assert "__" not in html
    assert "<title>2023–2024</title>" in html

    for name, expected in [
        ("partnersByYear", partners_by_year),
        ("monthlyByYear", monthly_by_year),
        ("countriesGeoJson", geojson),
        ("years", years),
    ]:
        start = html.index(f"const {name} = ") + len(f"const {name} = ")
        end = html.index(";", start)
        assert json.loads(html[start:end]) == expected

    assert 'class="viewRadio" value="calves"' in html
    assert '<details class="notes">' in html
