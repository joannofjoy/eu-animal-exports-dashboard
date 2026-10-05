"""Tests for scripts/build_mirror.py.

Like tests/test_build_dashboard.py, these use a small temporary CSV
(tmp_path) rather than the project's real processed data.
"""

import json

from build_mirror import load_mirror_by_country, render


def test_load_mirror_by_country_groups_by_country_year_and_category(tmp_path):
    csv_path = tmp_path / "mirror_comparison.csv"
    csv_path.write_text(
        "year,country,product,at_export_units,partner_import_units,at_export_kg,partner_import_kg\n"
        # HR 2024: AT exported real numbers, HR's own mirror reported
        # nothing at all -- the Croatia 2024 finding this tool generalises.
        "2024,HR,01022110,4813,0,640298,0\n"
        # DE 2024: both sides have some data, split across two categories
        # (zuchtrinder_original and young_slaughter) to check the category
        # grouping sums correctly within one country/year.
        "2024,DE,01022110,2000,10,1000000,3000\n"
        "2024,DE,01022921,499,3,300000,1000\n"
    )

    mirror_by_country = load_mirror_by_country(tmp_path)

    assert set(mirror_by_country.keys()) == {"HR", "DE"}

    hr_2024 = mirror_by_country["HR"]["2024"]
    assert hr_2024["atExportUnits"] == {"zuchtrinder_original": 4813}
    # A measure that's entirely zero for this country/year shouldn't show
    # up at all, not even as an empty category key.
    assert hr_2024["partnerImportUnits"] == {}
    assert hr_2024["atExportKg"] == {"zuchtrinder_original": 640298}
    assert hr_2024["partnerImportKg"] == {}

    de_2024 = mirror_by_country["DE"]["2024"]
    assert de_2024["atExportUnits"] == {"zuchtrinder_original": 2000, "young_slaughter": 499}
    assert de_2024["partnerImportUnits"] == {"zuchtrinder_original": 10, "young_slaughter": 3}


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "const mirrorByCountry = __MIRROR_BY_COUNTRY_JSON__;"
        "const countries = __COUNTRIES_JSON__;"
        "const years = __YEARS_JSON__;"
        "</script>"
        '<div id="categoryFilter">__CATEGORY_FILTER_HTML__</div>'
        '<div class="footer">__PROJECT_NOTES_HTML__</div>'
    )
    mirror_by_country = {
        "HR": {"2024": {"atExportUnits": {"zuchtrinder_original": 4813}, "partnerImportUnits": {}}}
    }
    countries = [{"code": "HR", "name": "Kroatien"}]
    years = ["2023", "2024"]

    html = render(template, mirror_by_country, countries, years)

    assert "__" not in html
    assert "<title>2023–2024</title>" in html

    for name, expected in [
        ("mirrorByCountry", mirror_by_country),
        ("countries", countries),
        ("years", years),
    ]:
        start = html.index(f"const {name} = ") + len(f"const {name} = ")
        end = html.index(";", start)
        assert json.loads(html[start:end]) == expected

    assert 'class="viewRadio" value="calves"' in html
    assert '<details class="notes">' in html
