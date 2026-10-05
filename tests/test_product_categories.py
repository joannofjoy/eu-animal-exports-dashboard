"""Tests for scripts/product_categories.py.

Coverage matters here for two reasons: every product code
fetch_at_history.py asks Eurostat for must end up in exactly one leaf
category (CODE_TO_CATEGORY), or the dashboards' category filter would
silently drop some trade or double-count it -- and every VIEW's
"categories" list must only reference real leaf categories, with the
"all" view covering every one of them, or a reader selecting "All" would
see a total that's quietly missing some trade.
"""

from fetch_at_history import PRODUCTS
from product_categories import CATEGORIES, CODE_TO_CATEGORY, VIEWS


def test_every_product_is_categorized_exactly_once():
    assert set(CODE_TO_CATEGORY.keys()) == set(PRODUCTS)


def test_no_code_appears_in_more_than_one_category():
    all_codes = [code for info in CATEGORIES.values() for code in info["codes"]]
    assert len(all_codes) == len(set(all_codes))


def test_views_reference_only_real_categories():
    for view in VIEWS:
        for category in view["categories"]:
            assert category in CATEGORIES


def test_view_keys_are_unique():
    keys = [view["key"] for view in VIEWS]
    assert len(keys) == len(set(keys))


def test_all_view_covers_every_category():
    all_view = next(view for view in VIEWS if view["key"] == "all")
    assert sorted(all_view["categories"]) == sorted(CATEGORIES.keys())
