"""Tests for scripts/fetch_mirror_data.py.

Only the pure functions are tested here -- eu_partner_countries() (file
I/O, but no network) against a temporary CSV, and to_yearly()/
combine_series() (pure logic) against small hand-built DataFrames.
fetch_series() itself isn't tested: it just wraps a `requests.get()` call,
the same reasoning fetch_at_history.py's fetch_year() is left untested.
"""

import pandas as pd
from fetch_mirror_data import combine_series, eu_partner_countries, to_yearly


def test_eu_partner_countries_intersects_with_eu_members(tmp_path):
    csv_path = tmp_path / "at_bovine_exports_yearly_by_partner_product.csv"
    csv_path.write_text(
        "year,partner,product,quantity\n"
        "2023,DE,01022110,50\n"  # EU member
        "2023,TR,01022110,80\n"  # not an EU member -- should be excluded
        "2023,FR,01022110,10\n"  # EU member
    )

    countries = eu_partner_countries(csv_path)

    assert countries == ["DE", "FR"]  # sorted, TR excluded


def test_to_yearly_sums_months_into_years():
    monthly = pd.DataFrame(
        [
            {
                "reporter": "IT",
                "partner": "AT",
                "product": "01022110",
                "TIME_PERIOD": "2024-01",
                "OBS_VALUE": 10,
            },
            {
                "reporter": "IT",
                "partner": "AT",
                "product": "01022110",
                "TIME_PERIOD": "2024-02",
                "OBS_VALUE": 5,
            },
            {
                "reporter": "IT",
                "partner": "AT",
                "product": "01022110",
                "TIME_PERIOD": "2023-12",
                "OBS_VALUE": 3,
            },
        ]
    )

    yearly = to_yearly(monthly, "quantity")

    rows = {(r.year, r.quantity) for r in yearly.itertuples()}
    assert rows == {("2024", 15), ("2023", 3)}


def test_to_yearly_handles_empty_input():
    empty = pd.DataFrame(columns=["reporter", "partner", "product", "TIME_PERIOD", "OBS_VALUE"])

    yearly = to_yearly(empty, "quantity")

    assert list(yearly.columns) == ["year", "reporter", "partner", "product", "quantity"]
    assert len(yearly) == 0


def test_combine_series_outer_joins_and_fills_missing_with_zero():
    # HR: AT exported real units+kg, but HR's own mirror reported nothing
    # at all (no row in either mirror table) -- matches the Croatia 2024
    # finding this whole tool exists to generalise.
    at_export_units = pd.DataFrame(
        [{"year": "2024", "country": "HR", "product": "01022110", "at_export_units": 100}]
    )
    partner_import_units = pd.DataFrame(
        columns=["year", "country", "product", "partner_import_units"]
    )
    at_export_kg = pd.DataFrame(
        [{"year": "2024", "country": "HR", "product": "01022110", "at_export_kg": 50000}]
    )
    partner_import_kg = pd.DataFrame(columns=["year", "country", "product", "partner_import_kg"])

    combined = combine_series(
        at_export_units, partner_import_units, at_export_kg, partner_import_kg
    )

    assert len(combined) == 1
    row = combined.iloc[0]
    assert row["at_export_units"] == 100
    assert row["partner_import_units"] == 0  # filled, not NaN
    assert row["at_export_kg"] == 50000
    assert row["partner_import_kg"] == 0

    # Explicit zeros, not floats -- these get embedded as JSON later and
    # should read as whole numbers of animals/kg, not "0.0".
    for col in ["at_export_units", "partner_import_units", "at_export_kg", "partner_import_kg"]:
        assert combined[col].dtype.kind == "i"


def test_combine_series_matches_rows_by_year_country_product():
    at_export_units = pd.DataFrame(
        [
            {"year": "2024", "country": "IT", "product": "01022110", "at_export_units": 200},
            {"year": "2023", "country": "IT", "product": "01022110", "at_export_units": 150},
        ]
    )
    partner_import_units = pd.DataFrame(
        [{"year": "2024", "country": "IT", "product": "01022110", "partner_import_units": 210}]
    )
    at_export_kg = pd.DataFrame(columns=["year", "country", "product", "at_export_kg"])
    partner_import_kg = pd.DataFrame(columns=["year", "country", "product", "partner_import_kg"])

    combined = combine_series(
        at_export_units, partner_import_units, at_export_kg, partner_import_kg
    )

    by_year = {r.year: r.partner_import_units for r in combined.itertuples()}
    assert by_year == {"2024": 210, "2023": 0}
