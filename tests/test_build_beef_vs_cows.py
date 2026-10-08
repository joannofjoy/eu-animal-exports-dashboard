"""Tests for scripts/build_beef_vs_cows.py.

Same approach as test_build_dashboard.py: small, temporary CSVs (via
pytest's tmp_path fixture) rather than the project's real data/processed/
files, so these tests don't depend on -- or break from -- whatever the
real data happens to contain right now.
"""

import json

from build_beef_vs_cows import load_live_exports_by_year, load_meat_imports_by_year, render


def test_load_live_exports_by_year_sums_across_products(tmp_path):
    csv_path = tmp_path / "at_bovine_exports_yearly_by_product.csv"
    csv_path.write_text(
        "year,product,quantity,value_eur\n"
        "2023,01022110,100,80000\n"
        "2023,01022921,50,30000\n"
        "2024,01022110,10,9000\n"
    )

    result = load_live_exports_by_year(tmp_path)

    assert result == {
        "2023": {"quantity": 150, "valueEur": 110000},
        "2024": {"quantity": 10, "valueEur": 9000},
    }


def test_load_meat_imports_by_year_converts_100kg_to_tonnes(tmp_path):
    csv_path = tmp_path / "at_beef_imports_yearly_by_product.csv"
    csv_path.write_text(
        "year,product,quantity_100kg,value_eur\n"
        # 549.04 (hundreds of kg) + 330.73 -> 879.77 -> /10 = 87.977 tonnes
        "2023,02013000,549.04,500000\n"
        "2023,02021000,330.73,300000\n"
    )

    result = load_meat_imports_by_year(tmp_path)

    assert result == {"2023": {"quantityTonnes": 88.0, "valueEur": 800000}}


def test_render_substitutes_all_placeholders():
    template = (
        "<title>__YEAR_RANGE__</title>"
        "<script>"
        "let liveExportsByYear = __LIVE_EXPORTS_BY_YEAR_JSON__;"
        "let meatImportsByYear = __MEAT_IMPORTS_BY_YEAR_JSON__;"
        "const REPORTERS = __REPORTERS_JSON__;"
        "</script>"
        '<div class="siteTabs">__SITE_TABS_HTML__</div>'
    )
    live = {"2023": {"quantity": 150, "valueEur": 110000}}
    meat = {"2023": {"quantityTonnes": 88.0, "valueEur": 800000}}

    html = render(template, live, meat, reporters=[("AT", "Austria")])

    assert "__" not in html
    assert "<title>2023–2023</title>" in html

    start = html.index("let liveExportsByYear = ") + len("let liveExportsByYear = ")
    end = html.index(";", start)
    assert json.loads(html[start:end]) == live

    start = html.index("let meatImportsByYear = ") + len("let meatImportsByYear = ")
    end = html.index(";", start)
    assert json.loads(html[start:end]) == meat


def test_render_handles_no_data_at_all():
    template = "<title>__YEAR_RANGE__</title>"

    html = render(template, {}, {}, reporters=[("AT", "Austria")])

    assert "<title>no data yet</title>" in html
