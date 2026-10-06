"""Tests for scripts/build_dashboard.py.

load_partners_by_year() is tested against a small, temporary CSV file (via
pytest's built-in tmp_path fixture, which gives each test its own throwaway
folder) rather than the project's real data/processed/ files -- that way
the tests don't depend on whatever the real data happens to contain right
now, and won't break the next time scripts/fetch_at_history.py is re-run
with fresh numbers.
"""

import json

from build_dashboard import load_partners_by_year, render


def test_load_partners_by_year_groups_by_year_partner_and_category(tmp_path):
    csv_path = tmp_path / "at_bovine_exports_yearly_by_partner_product.csv"
    csv_path.write_text(
        "year,partner,product,quantity,value_eur\n"
        # DE, 2023: one row per category -- should end up summed into one
        # partner entry with both categories in byCategory (and the same
        # shape again in byCategoryValueEur).
        "2023,DE,01022110,50,40000\n"  # zuchtrinder_original
        "2023,DE,01022921,30,21000\n"  # young_slaughter
        # FR, 2023: a single category.
        "2023,FR,01022110,200,150000\n"
        # DE, 2024: a different year is a separate entry entirely.
        "2024,DE,01022110,10,9000\n"
        # TR: not an EU member, checks the isEU flag goes both ways.
        "2023,TR,01022905,5,3000\n"  # other_unclassified
    )

    partners_by_year = load_partners_by_year(tmp_path)

    assert list(partners_by_year.keys()) == ["2023", "2024"]

    by_code_2023 = {p["code"]: p for p in partners_by_year["2023"]}
    assert by_code_2023["DE"]["name"] == "Germany"
    assert by_code_2023["DE"]["isEU"] is True
    assert by_code_2023["DE"]["byCategory"] == {"zuchtrinder_original": 50, "young_slaughter": 30}
    assert by_code_2023["DE"]["byCategoryValueEur"] == {
        "zuchtrinder_original": 40000,
        "young_slaughter": 21000,
    }

    assert by_code_2023["FR"]["byCategory"] == {"zuchtrinder_original": 200}
    assert by_code_2023["FR"]["byCategoryValueEur"] == {"zuchtrinder_original": 150000}

    assert by_code_2023["TR"]["isEU"] is False
    assert by_code_2023["TR"]["byCategory"] == {"other_unclassified": 5}
    assert by_code_2023["TR"]["byCategoryValueEur"] == {"other_unclassified": 3000}

    assert partners_by_year["2024"] == [
        {
            "code": "DE",
            "name": "Germany",
            "isEU": True,
            "byCategory": {"zuchtrinder_original": 10},
            "byCategoryValueEur": {"zuchtrinder_original": 9000},
        }
    ]


def test_load_partners_by_year_falls_back_to_raw_code_for_unknown_country(tmp_path):
    csv_path = tmp_path / "at_bovine_exports_yearly_by_partner_product.csv"
    csv_path.write_text("year,partner,product,quantity,value_eur\n2023,ZZ,01022110,5,4000\n")

    partners_by_year = load_partners_by_year(tmp_path)

    assert partners_by_year["2023"][0]["name"] == "ZZ"


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "const partnersByYear = __PARTNERS_BY_YEAR_JSON__;"
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
                "byCategoryValueEur": {"zuchtrinder_original": 150000},
            }
        ],
        "2024": [],
    }
    years = ["2023", "2024"]

    html = render(template, partners_by_year, years)

    # No placeholder tokens should survive the substitution.
    assert "__" not in html

    assert "<title>2023–2024</title>" in html
    # Pulling the embedded JSON back out and re-parsing it is a stronger
    # check than a plain substring match -- it confirms the output is
    # actually valid, usable JSON, not just text that happens to look
    # right.
    start = html.index("const partnersByYear = ") + len("const partnersByYear = ")
    end = html.index(";", start)
    assert json.loads(html[start:end]) == partners_by_year

    # render_category_filter_html() output should have been inlined too --
    # spot-check for a couple of the real category keys rather than
    # re-asserting its whole structure here (that's product_categories.py's
    # own test's job).
    assert 'class="viewRadio" value="calves"' in html
    assert 'class="viewRadio" value="slaughter"' in html
