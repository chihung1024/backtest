from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.data.base import AssetHistory
from app.engine.analytics import (
    STYLE_PROXIES,
    factor_regression,
    regime_performance,
    returns_based_style,
)
from app.engine.backtest import Simulation
from app.models import RegimeType


def make_simulation(name: str, values: np.ndarray) -> Simulation:
    index = pd.date_range("2020-01-31", periods=len(values), freq="ME")
    returns = pd.Series(values, index=index, dtype=float)
    levels = (1.0 + returns).cumprod()
    return Simulation(
        name=name,
        equity=levels * 10_000,
        return_index=levels,
        daily_returns=returns,
        flows=pd.Series(0.0, index=index),
        income=pd.Series(0.0, index=index),
        final_allocation={"TEST": 1.0},
    )


class FactorStub:
    def __init__(self, factors: pd.DataFrame) -> None:
        self.factors = factors

    def monthly_factors(self) -> pd.DataFrame:
        return self.factors


class FredStub:
    def __init__(self, index: pd.DatetimeIndex) -> None:
        self.index = index

    def series(self, series_id: str) -> pd.Series:
        if series_id == "CPIAUCSL":
            values = np.linspace(100.0, 115.0, len(self.index))
        else:
            values = np.linspace(20_000.0, 23_000.0, len(self.index))
        return pd.Series(values, index=self.index, name=series_id)


def test_factor_regression_recovers_known_market_beta() -> None:
    index = pd.date_range("2020-01-31", periods=48, freq="ME")
    x = np.linspace(-0.04, 0.05, len(index))
    factors = pd.DataFrame(
        {
            "MKT_RF": x,
            "SMB": np.sin(np.arange(len(index))) * 0.01,
            "HML": np.cos(np.arange(len(index)) * 0.7) * 0.008,
            "RMW": np.sin(np.arange(len(index)) * 0.3) * 0.006,
            "CMA": np.cos(np.arange(len(index)) * 0.4) * 0.005,
            "MOM": np.sin(np.arange(len(index)) * 0.9) * 0.009,
            "RF": np.full(len(index), 0.001),
        },
        index=index,
    )
    portfolio = (
        factors["RF"]
        + 0.002
        + 1.2 * factors["MKT_RF"]
        + 0.3 * factors["SMB"]
        - 0.2 * factors["HML"]
        + 0.1 * factors["MOM"]
    )

    result = factor_regression(
        make_simulation("Factors", portfolio.to_numpy()),
        FactorStub(factors),  # type: ignore[arg-type]
    )

    assert result["observations"] == 48
    assert result["betas"]["MKT_RF"] == pytest.approx(1.2, rel=1e-6)
    assert result["r_squared"] == pytest.approx(1.0)


def test_returns_based_style_outputs_nonnegative_normalized_exposures() -> None:
    index = pd.date_range("2020-01-31", periods=48, freq="ME")
    histories: dict[str, AssetHistory] = {}
    proxy_values: list[np.ndarray] = []
    for position, symbol in enumerate(STYLE_PROXIES.values(), start=1):
        values = (
            np.sin(np.arange(len(index)) * (0.13 * position)) * 0.02
            + np.cos(np.arange(len(index)) * (0.07 * (position + 1))) * 0.01
        )
        proxy_values.append(values)
        series = pd.Series(values, index=index)
        histories[symbol] = AssetHistory(
            symbol=symbol,
            name=symbol,
            currency="USD",
            total_returns=series,
            price_returns=series,
            dividend_returns=pd.Series(0.0, index=index),
            dividends=pd.Series(0.0, index=index),
        )
    portfolio = 0.6 * proxy_values[0] + 0.4 * proxy_values[-1]

    result = returns_based_style(make_simulation("Style", portfolio), histories)

    exposures = result["exposures"]
    assert sum(exposures.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in exposures.values())
    assert result["r_squared"] > 0.99


def test_regime_analysis_drops_warmup_months_and_classifies_periods() -> None:
    values = np.concatenate(
        [np.full(18, 0.01), np.tile(np.array([0.09, -0.07]), 15)]
    )
    portfolio = make_simulation("Portfolio", values * 0.8)
    benchmark = make_simulation("Benchmark", values)

    market = regime_performance(portfolio, benchmark, RegimeType.MARKET)
    volatility = regime_performance(portfolio, benchmark, RegimeType.VOLATILITY)

    assert market["type"] == "market"
    assert sum(row["months"] for row in market["regimes"]) < len(values)
    assert {row["name"] for row in volatility["regimes"]} == {
        "High volatility",
        "Low volatility",
    }


def test_inflation_regime_uses_fred_series() -> None:
    values = np.tile(np.array([0.02, -0.005, 0.01]), 16)
    simulation = make_simulation("Inflation", values)
    index = pd.date_range("2019-01-01", periods=72, freq="MS")

    result = regime_performance(
        simulation,
        simulation,
        RegimeType.INFLATION,
        FredStub(index),  # type: ignore[arg-type]
    )

    assert result["type"] == "inflation"
    assert result["regimes"]
