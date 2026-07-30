from __future__ import annotations

import pandas as pd
import pytest

from app.data.price_quality import reconcile_ohlc_levels


def test_close_outside_daily_bar_is_reconstructed_from_surrounding_levels() -> None:
    index = pd.DatetimeIndex(["2011-10-24", "2011-10-25", "2011-10-26"])
    frame = pd.DataFrame(
        {
            "Open": [0.3022, 0.3007, 0.3009],
            "High": [0.3022, 0.3008, 0.3013],
            "Low": [0.29387, 0.29387, 0.2940],
            "Close": [0.29254, 0.018015, 0.3011],
        },
        index=index,
    )

    result = reconcile_ohlc_levels(frame)
    replacement = result.levels.loc[pd.Timestamp("2011-10-25")]

    assert result.corrected.loc[pd.Timestamp("2011-10-25")]
    assert 0.29387 <= replacement <= 0.3008
    gross = result.levels.pct_change(fill_method=None)
    assert gross.abs().max() < 0.10


def test_second_impossible_close_is_repaired_without_symbol_or_date_rules() -> None:
    index = pd.DatetimeIndex(["2014-12-30", "2014-12-31", "2015-01-01"])
    frame = pd.DataFrame(
        {
            "Open": [31.049, 30.922, 31.605],
            "High": [31.049, 31.584, 31.618],
            "Low": [30.935, 30.847, 30.987],
            "Close": [30.958, 3.67, 31.625],
        },
        index=index,
    )

    result = reconcile_ohlc_levels(frame)
    replacement = result.levels.loc[pd.Timestamp("2014-12-31")]

    assert result.corrected.loc[pd.Timestamp("2014-12-31")]
    assert 30.847 <= replacement <= 31.584
    assert result.levels.pct_change(fill_method=None).abs().max() < 0.10


def test_genuine_large_market_move_inside_ohlc_bar_is_preserved() -> None:
    index = pd.DatetimeIndex(["2020-03-13", "2020-03-16", "2020-03-17"])
    frame = pd.DataFrame(
        {
            "Open": [101.0, 28.0, 24.0],
            "High": [102.0, 30.0, 27.0],
            "Low": [98.0, 20.0, 21.0],
            "Close": [100.0, 23.0, 25.0],
        },
        index=index,
    )

    result = reconcile_ohlc_levels(frame)

    assert result.levels.equals(frame["Close"].astype(float))
    assert not result.corrected.any()
    assert result.levels.pct_change(fill_method=None).iloc[1] == pytest.approx(-0.77)


def test_inverse_quote_swaps_high_and_low_before_validation() -> None:
    index = pd.DatetimeIndex(["2014-12-30", "2014-12-31", "2015-01-01"])
    frame = pd.DataFrame(
        {
            "Open": [1 / 31.049, 1 / 30.922, 1 / 31.605],
            "High": [1 / 30.935, 1 / 30.847, 1 / 30.987],
            "Low": [1 / 31.049, 1 / 31.584, 1 / 31.618],
            "Close": [1 / 30.958, 1 / 3.67, 1 / 31.625],
        },
        index=index,
    )

    result = reconcile_ohlc_levels(frame, invert=True)
    replacement = result.levels.loc[pd.Timestamp("2014-12-31")]

    assert result.corrected.loc[pd.Timestamp("2014-12-31")]
    assert 30.847 <= replacement <= 31.584


def test_close_only_feed_remains_usable_without_inventing_bar_evidence() -> None:
    index = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"])
    frame = pd.DataFrame({"Close": [30.0, 30.2, 30.1]}, index=index)

    result = reconcile_ohlc_levels(frame)

    assert result.levels.equals(frame["Close"].astype(float))
    assert not result.corrected.any()
    assert not result.unresolved.any()
