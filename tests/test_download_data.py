"""Tests for scripts/download_data.py.

Only to_wide_by_month() is tested -- it's the pure reshaping logic (long
rows in, one-row-per-reporter/partner table out). fetch() itself isn't
tested since it's just a `requests.get()` wrapper; see the equivalent note
in tests/test_fetch_at_history.py for why that's not worth doing here.
"""

import pandas as pd
from download_data import to_wide_by_month


def test_to_wide_by_month_pivots_and_fills_missing_months_with_zero():
    raw = pd.DataFrame(
        [
            {"reporter": "AT", "partner": "DE", "TIME_PERIOD": "2023-01", "OBS_VALUE": 10},
            {"reporter": "AT", "partner": "DE", "TIME_PERIOD": "2023-02", "OBS_VALUE": 20},
            # FR only has a January row -- February should come out as 0,
            # not missing, once pivoted to the wide layout.
            {"reporter": "AT", "partner": "FR", "TIME_PERIOD": "2023-01", "OBS_VALUE": 5},
        ]
    )

    wide = to_wide_by_month(raw)
    wide = wide.set_index(["DECLARANT_ISO", "PARTNER_ISO"])

    assert wide.loc[("AT", "DE"), "quant01"] == 10
    assert wide.loc[("AT", "DE"), "quant02"] == 20
    assert wide.loc[("AT", "FR"), "quant01"] == 5
    assert wide.loc[("AT", "FR"), "quant02"] == 0


def test_to_wide_by_month_sums_repeated_entries_within_a_month():
    # Two rows for the same reporter/partner/month (e.g. two different
    # underlying trade movements) should be added together, not overwrite
    # one another.
    raw = pd.DataFrame(
        [
            {"reporter": "AT", "partner": "DE", "TIME_PERIOD": "2023-01", "OBS_VALUE": 10},
            {"reporter": "AT", "partner": "DE", "TIME_PERIOD": "2023-01", "OBS_VALUE": 4},
        ]
    )

    wide = to_wide_by_month(raw)

    assert wide.loc[0, "quant01"] == 14
