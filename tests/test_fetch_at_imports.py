"""Tests for scripts/fetch_at_imports.py.

This script has no new pure logic of its own -- it reuses PRODUCTS,
REPORTER, and aggregate() from fetch_at_history.py rather than
duplicating them (see that file's own tests for aggregate() coverage).
The one thing worth guarding here is the flow code itself: it's the only
real difference between this script and fetch_at_history.py, and mixing
them up would silently swap "imports" and "exports" everywhere downstream.
"""

from fetch_at_history import INDICATORS as EXPORT_INDICATORS
from fetch_at_history import PRODUCTS as EXPORT_PRODUCTS
from fetch_at_history import REPORTER as EXPORT_REPORTER
from fetch_at_imports import FLOW, INDICATORS, PRODUCTS, REPORTER


def test_flow_is_import_not_export():
    assert FLOW == "1"  # 1 = import/arrivals, 2 = export/dispatches


def test_products_and_reporter_are_shared_not_duplicated():
    # Importing the same objects (not equal-but-separate copies) from
    # fetch_at_history.py -- `is` checks object identity, so this would
    # fail if fetch_at_imports.py ever redefined its own PRODUCTS/REPORTER
    # instead of importing them, which would let the two scripts drift
    # out of sync with each other over time.
    assert PRODUCTS is EXPORT_PRODUCTS
    assert REPORTER is EXPORT_REPORTER


def test_indicators_include_both_head_count_and_euro_value():
    # INDICATORS is duplicated (not imported), since it's identical in
    # both scripts rather than one being derived from the other -- so
    # there's no object-identity check to make here, just that neither
    # script silently lost the euro indicator (which would make value_eur
    # come back as 0 for every row, since aggregate() would never see a
    # VALUE_IN_EUROS row to pivot).
    assert set(INDICATORS) == {"SUPPLEMENTARY_QUANTITY", "VALUE_IN_EUROS"}
    assert set(EXPORT_INDICATORS) == {"SUPPLEMENTARY_QUANTITY", "VALUE_IN_EUROS"}
