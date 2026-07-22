from __future__ import annotations

import pandas as pd
import pytest

from app.engine.metrics import (
    annual_returns,
    compute_real_return_metrics,
    drawdown_series,
    xirr,
)


def test_drawdown_uses_running_peak() -> None:
    index = pd.bdate_range("2020-01-01", periods=5)
    levels = pd.Series([1.0, 1.1, 0.88, 0.99, 1.21], index=index)
    result = drawdown_series(levels)
    assert result.min() == pytest.approx(-0.20)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_annual_returns_keep_first_partial_year() -> None:
    index = pd.to_datetime(["2020-01-01", "2020-12-31", "2021-12-31"])
    levels = pd.Series([1.0, 1.1, 1.32], index=index)
    result = annual_returns(levels)
    assert result.loc[2020] == pytest.approx(0.1)
    assert result.loc[2021] == pytest.approx(0.2)


def test_xirr_with_one_year_double() -> None:
    index = pd.to_datetime(["2020-01-01", "2020-12-31"])
    flows = pd.Series([0.0, 0.0], index=index)
    result = xirr(100.0, 200.0, flows)
    assert result == pytest.approx(1.0, rel=2e-3)


def test_real_return_metrics_deflate_nominal_growth() -> None:
    index = pd.to_datetime(["2020-01-01", "2021-01-01"])
    levels = pd.Series([1.0, 1.21], index=index)
    cpi = pd.Series([100.0, 110.0], index=index)

    result = compute_real_return_metrics(levels, cpi)

    assert result["cumulative_inflation"] == pytest.approx(0.10)
    assert result["real_total_return"] == pytest.approx(0.10)
    assert result["real_cagr"] == pytest.approx(0.10, rel=1e-2)
