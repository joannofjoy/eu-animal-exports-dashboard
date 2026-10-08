"""Tests for scripts/fetch_at_history.py.

Only aggregate(), aggregate_monthly(), and _pivot_indicators() are tested
here -- they're the pure logic (take a table, produce summary tables)
with no network calls in them. fetch() itself isn't tested: it just wraps
a `requests.get()` call, and a test that hits the real Eurostat API would
be slow and would fail whenever that API is unreachable, for reasons
unrelated to whether our own code is correct.
"""

import pandas as pd
from fetch_at_history import aggregate, aggregate_monthly, validate_api_response


def _valid_api_rows():
    return pd.DataFrame(
        [
            {
                "freq": "M",
                "reporter": "AT",
                "partner": "DE",
                "product": "01022110",
                "flow": "2",
                "indicators": indicator,
                "TIME_PERIOD": "2023-01",
                "OBS_VALUE": value,
            }
            for indicator, value in [
                ("SUPPLEMENTARY_QUANTITY", 10),
                ("VALUE_IN_EUROS", 15000),
            ]
        ]
    )


def test_validate_api_response_accepts_requested_complete_observations():
    clean = validate_api_response(_valid_api_rows(), 2023, "AT", "2")

    assert clean["OBS_VALUE"].sum() == 15010


def test_validate_api_response_rejects_missing_measure_instead_of_zero_filling():
    rows = _valid_api_rows().iloc[:1]

    try:
        validate_api_response(rows, 2023, "AT", "2")
    except ValueError as error:
        assert "exactly the requested indicators" in str(error)
    else:
        raise AssertionError("incomplete indicators should be rejected")


def test_validate_api_response_rejects_a_measure_missing_for_one_observation_key():
    rows = pd.concat(
        [
            _valid_api_rows(),
            _valid_api_rows().iloc[[0]].assign(partner="FR"),
        ],
        ignore_index=True,
    )

    try:
        validate_api_response(rows, 2023, "AT", "2")
    except ValueError as error:
        assert "missing a requested indicator" in str(error)
    else:
        raise AssertionError("each observation key should contain both measures")


def test_validate_api_response_rejects_null_observation_values():
    rows = _valid_api_rows()
    rows.loc[0, "OBS_VALUE"] = None

    try:
        validate_api_response(rows, 2023, "AT", "2")
    except ValueError as error:
        assert "missing or non-numeric" in str(error)
    else:
        raise AssertionError("missing observation values should be rejected")


def test_validate_api_response_rejects_product_outside_custom_products_list():
    # fetch_meat_imports.py passes its own MEAT_PRODUCTS list here instead
    # of relying on the live-cattle PRODUCTS default -- confirms that
    # override actually takes effect rather than always checking against
    # the module-level default.
    try:
        validate_api_response(_valid_api_rows(), 2023, "AT", "2", products=["02013000"])
    except ValueError as error:
        assert "unrequested products" in str(error)
    else:
        raise AssertionError("a product outside the custom list should be rejected")


def test_validate_api_response_accepts_product_within_custom_products_list():
    clean = validate_api_response(
        _valid_api_rows(), 2023, "AT", "2", products=["01022110", "02013000"]
    )

    assert clean["OBS_VALUE"].sum() == 15010


def test_aggregate_sums_by_year_and_excludes_aggregate_partners():
    # A small, hand-built stand-in for what fetch() would normally
    # download: a few real rows, plus one "WORLD" row that must be
    # dropped (see AGGREGATE_PARTNERS in fetch_at_history.py) so it
    # doesn't get double-counted alongside the real countries. Every row
    # needs an "indicators" value now -- the real API tags each row with
    # which indicator (head count vs. euro value) it is, and aggregate()
    # groups by that column before summing so the two never get added
    # together by mistake.
    raw = pd.DataFrame(
        [
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 10,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-02",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 5,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022130",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 3,
            },
            {
                "partner": "FR",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 7,
            },
            {
                "partner": "WORLD",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 999,
            },
        ]
    )

    by_product, by_partner, by_partner_product = aggregate(raw)

    # by_product: DE's two 01022110 rows (10 + 5) plus FR's (7) = 22;
    # WORLD's 999 must NOT be included.
    product_totals = dict(zip(by_product["product"], by_product["quantity"]))
    assert product_totals == {"01022110": 22, "01022130": 3}

    # by_partner: DE's total across both products (10 + 5 + 3 = 18), FR's
    # total (7), and WORLD excluded entirely.
    partner_totals = dict(zip(by_partner["partner"], by_partner["quantity"]))
    assert partner_totals == {"DE": 18, "FR": 7}

    # by_partner is sorted with the biggest exporter first within a year --
    # DE (18) should come before FR (7).
    assert list(by_partner["partner"]) == ["DE", "FR"]

    # by_partner_product: neither dimension summed away -- DE's two
    # products stay as two separate rows (15 for 01022110, 3 for
    # 01022130), and WORLD is still excluded.
    partner_product_totals = {
        (row.partner, row.product): row.quantity for row in by_partner_product.itertuples()
    }
    assert partner_product_totals == {
        ("DE", "01022110"): 15,
        ("DE", "01022130"): 3,
        ("FR", "01022110"): 7,
    }

    # None of the rows in this fixture have a VALUE_IN_EUROS row at all --
    # every value_eur should come back as 0, not NaN/missing, since a
    # (year, product) group missing one of the two indicators entirely is
    # treated the same as "no value reported" everywhere else in this
    # codebase.
    assert (by_product["value_eur"] == 0).all()


def test_aggregate_keeps_years_separate():
    raw = pd.DataFrame(
        [
            {
                "partner": "DE",
                "TIME_PERIOD": "2022-12",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 4,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 6,
            },
        ]
    )

    by_product, _, _ = aggregate(raw)

    years = dict(zip(by_product["year"], by_product["quantity"]))
    assert years == {"2022": 4, "2023": 6}


def test_aggregate_pivots_head_count_and_euro_value_onto_the_same_row():
    # This is the real shape the Eurostat API returns now that
    # fetch_year() asks for SUPPLEMENTARY_QUANTITY+VALUE_IN_EUROS in one
    # query: two separate rows for the same (year, partner, product), one
    # per indicator. aggregate() must turn that into ONE output row with
    # both a "quantity" and a "value_eur" column -- not two rows, and not
    # a single row with the two numbers wrongly added together.
    raw = pd.DataFrame(
        [
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 10,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "VALUE_IN_EUROS",
                "OBS_VALUE": 15000,
            },
            # A second month for the same partner/product, so summing
            # across TIME_PERIOD within the year is also exercised for
            # both indicators at once.
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-02",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 5,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-02",
                "product": "01022110",
                "indicators": "VALUE_IN_EUROS",
                "OBS_VALUE": 7000,
            },
        ]
    )

    by_product, by_partner, by_partner_product = aggregate(raw)

    assert len(by_product) == 1
    row = by_product.iloc[0]
    assert row["quantity"] == 15  # 10 + 5
    assert row["value_eur"] == 22000  # 15000 + 7000

    # Same check on the other two tables, since all three go through the
    # same _pivot_indicators() helper.
    assert by_partner.iloc[0]["quantity"] == 15
    assert by_partner.iloc[0]["value_eur"] == 22000
    assert by_partner_product.iloc[0]["quantity"] == 15
    assert by_partner_product.iloc[0]["value_eur"] == 22000


def test_aggregate_with_custom_indicator_columns_for_meat_quantity():
    # fetch_meat_imports.py passes {"QUANTITY_IN_100KG": "quantity_100kg",
    # "VALUE_IN_EUROS": "value_eur"} instead of the live-cattle default,
    # since meat has no per-animal head count -- confirms the output
    # column actually takes that custom name rather than always being
    # "quantity".
    raw = pd.DataFrame(
        [
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "02013000",
                "indicators": "QUANTITY_IN_100KG",
                "OBS_VALUE": 549.04,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "02013000",
                "indicators": "VALUE_IN_EUROS",
                "OBS_VALUE": 1254947,
            },
        ]
    )

    columns = {"QUANTITY_IN_100KG": "quantity_100kg", "VALUE_IN_EUROS": "value_eur"}
    by_product, _, _ = aggregate(raw, indicator_columns=columns)

    assert "quantity" not in by_product.columns
    row = by_product.iloc[0]
    assert row["quantity_100kg"] == 549.04
    assert row["value_eur"] == 1254947


def test_aggregate_monthly_keeps_month_granularity_and_excludes_aggregate_partners():
    raw = pd.DataFrame(
        [
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 10,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "VALUE_IN_EUROS",
                "OBS_VALUE": 15000,
            },
            {
                "partner": "DE",
                "TIME_PERIOD": "2023-02",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 5,
            },
            {
                "partner": "FR",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 7,
            },
            {
                "partner": "WORLD",
                "TIME_PERIOD": "2023-01",
                "product": "01022110",
                "indicators": "SUPPLEMENTARY_QUANTITY",
                "OBS_VALUE": 999,
            },
        ]
    )

    monthly = aggregate_monthly(raw)

    # Unlike aggregate()'s tables, January and February 2023 stay as two
    # separate rows instead of being summed into one "2023" total.
    totals = {(row.month, row.partner): row.quantity for row in monthly.itertuples()}
    assert totals == {
        ("2023-01", "DE"): 10,
        ("2023-02", "DE"): 5,
        ("2023-01", "FR"): 7,
    }

    # January's DE row also carries its euro value; February's DE row has
    # no VALUE_IN_EUROS entry in this fixture at all, so it should be 0,
    # not NaN.
    value_by_month = {
        row.month: row.value_eur for row in monthly.itertuples() if row.partner == "DE"
    }
    assert value_by_month == {"2023-01": 15000, "2023-02": 0}
