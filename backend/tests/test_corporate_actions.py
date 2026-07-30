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
    assert result.corrections.iloc[1]


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
