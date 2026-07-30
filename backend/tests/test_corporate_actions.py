from __future__ import annotations

import pandas as pd
import pytest

from app.data.corporate_actions import reconcile_corporate_actions


def test_explicit_split_repairs_only_the_unadjusted_scale() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 26.0, 27.0], index=index),
        adjusted=pd.Series([100.0, 104.0, 108.0], index=index),
        splits=pd.Series([0.0, 4.0, 0.0], index=index),
    )

    assert result.close_gross.iloc[1] == pytest.approx(1.04)
    assert result.adjusted_gross.iloc[1] == pytest.approx(1.04)
    assert result.distribution_multipliers.iloc[1] == pytest.approx(4.0)
    assert result.corrections.iloc[1]


def test_already_adjusted_close_does_not_rescale_distributions() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 102.0, 104.0], index=index),
        adjusted=pd.Series([100.0, 102.0, 104.0], index=index),
        splits=pd.Series([0.0, 4.0, 0.0], index=index),
    )

    assert result.close_gross.iloc[1] == pytest.approx(1.02)
    assert result.distribution_multipliers.iloc[1] == pytest.approx(1.0)


def test_adjustment_factor_recovers_an_omitted_split_event() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 26.0, 27.0], index=index),
        adjusted=pd.Series([100.0, 104.0, 108.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.iloc[1] == pytest.approx(4.0)
    assert result.close_gross.iloc[1] == pytest.approx(1.04)
    assert result.adjusted_gross.iloc[1] == pytest.approx(1.04)
    assert result.distribution_multipliers.iloc[1] == pytest.approx(4.0)


def test_synthetic_suspension_recovers_prepositioned_scale_transition() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-11-13",
            "2025-11-14",
            "2025-11-17",
            "2025-11-18",
            "2025-11-19",
            "2025-11-20",
            "2025-11-21",
            "2025-11-24",
            "2025-11-25",
            "2025-11-26",
            "2025-11-27",
        ]
    )
    close = pd.Series(
        [254.10, 248.50, 35.57, 35.04, 35.04, 35.04, 35.04, 35.04, 35.04, 35.35, 35.68],
        index=index,
    )
    result = reconcile_corporate_actions(
        close=close,
        adjusted=close.copy(),
        splits=pd.Series(0.0, index=index),
    )

    expected = 35.57 / 248.50 * 7.0
    assert result.splits.loc[pd.Timestamp("2025-11-17")] == pytest.approx(7.0)
    assert result.close_gross.loc[pd.Timestamp("2025-11-17")] == pytest.approx(expected)
    assert result.adjusted_gross.loc[pd.Timestamp("2025-11-17")] == pytest.approx(expected)
    assert result.corrections.loc[pd.Timestamp("2025-11-17")]


def test_flat_quotes_without_a_scale_break_do_not_create_a_split() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-11-13",
            "2025-11-14",
            "2025-11-17",
            "2025-11-18",
            "2025-11-19",
            "2025-11-20",
            "2025-11-21",
            "2025-11-24",
            "2025-11-25",
            "2025-11-26",
        ]
    )
    close = pd.Series(
        [100.0, 101.0, 101.5, 101.2, 101.2, 101.2, 101.2, 101.2, 101.2, 102.0],
        index=index,
    )
    result = reconcile_corporate_actions(
        close=close,
        adjusted=close.copy(),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.eq(0.0).all()
    assert not result.corrections.any()


def test_large_return_before_non_dense_flat_rows_is_preserved() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-01-02",
            "2025-01-03",
            "2025-01-06",
            "2025-01-08",
            "2025-01-10",
            "2025-01-14",
            "2025-01-15",
        ]
    )
    close = pd.Series([100.0, 50.0, 50.0, 50.0, 50.0, 50.0, 52.0], index=index)
    result = reconcile_corporate_actions(
        close=close,
        adjusted=close.copy(),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.close_gross.iloc[1] == pytest.approx(0.5)


def test_suspension_boundary_recovers_when_both_price_series_are_unadjusted() -> None:
    index = pd.DatetimeIndex(
        ["2025-11-17", "2025-11-18", "2025-11-26", "2025-11-27"]
    )
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 102.0, 14.7, 15.0], index=index),
        adjusted=pd.Series([100.0, 102.0, 14.7, 15.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.iloc[2] == pytest.approx(7.0)
    assert result.close_gross.iloc[2] == pytest.approx(14.7 / 102.0 * 7.0)
    assert result.adjusted_gross.iloc[2] == pytest.approx(14.7 / 102.0 * 7.0)


def test_weekend_or_short_holiday_is_not_treated_as_a_suspension() -> None:
    index = pd.DatetimeIndex(["2020-01-03", "2020-01-07", "2020-01-08"])
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 50.0, 52.0], index=index),
        adjusted=pd.Series([100.0, 50.0, 52.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.close_gross.iloc[1] == pytest.approx(0.5)


def test_suspension_boundary_supports_reverse_splits() -> None:
    index = pd.DatetimeIndex(
        ["2020-01-01", "2020-01-02", "2020-01-10", "2020-01-13"]
    )
    result = reconcile_corporate_actions(
        close=pd.Series([10.0, 10.2, 82.0, 84.0], index=index),
        adjusted=pd.Series([10.0, 10.2, 82.0, 84.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.iloc[2] == pytest.approx(0.125)
    assert result.close_gross.iloc[2] == pytest.approx(82.0 / 10.2 * 0.125)


def test_genuine_large_return_on_consecutive_trading_days_is_preserved() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 50.0, 52.0], index=index),
        adjusted=pd.Series([100.0, 50.0, 52.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.close_gross.iloc[1] == pytest.approx(0.5)
    assert not result.corrections.any()


def test_cash_distribution_is_removed_before_split_factor_inference() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 40.0, 42.0], index=index),
        adjusted=pd.Series([100.0, 110.0, 115.5], index=index),
        splits=pd.Series(0.0, index=index),
        distributions=pd.Series([0.0, 70.0, 0.0], index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.adjusted_gross.iloc[1] == pytest.approx(1.10)
