from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.data.base import AssetHistory
from app.data.factors import FrenchFactorProvider
from app.data.fred import FredProvider
from app.engine.backtest import Simulation
from app.models import RegimeType

STYLE_PROXIES = {
    "large_value": "IWD",
    "large_growth": "IWF",
    "mid_value": "IWS",
    "mid_growth": "IWP",
    "small_value": "IWN",
    "small_growth": "IWO",
}


def factor_regression(
    simulation: Simulation,
    provider: FrenchFactorProvider,
) -> dict[str, Any]:
    factors = provider.monthly_factors()
    portfolio = _monthly_compounded(simulation.daily_returns).rename("portfolio")
    joined = factors.join(portfolio, how="inner").dropna()
    factor_columns = [
        column
        for column in ("MKT_RF", "SMB", "HML", "RMW", "CMA", "MOM")
        if column in joined.columns
    ]
    if len(joined) < max(24, len(factor_columns) * 3):
        raise ValueError("At least 24 overlapping monthly observations are required")
    risk_free = joined.get("RF", 0.0)
    y = joined["portfolio"].to_numpy(dtype=float) - np.asarray(risk_free, dtype=float)
    x = joined[factor_columns].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coefficients
    residual = y - predicted
    denominator = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum(residual**2) / denominator) if denominator else 0.0
    alpha_monthly = float(coefficients[0])
    return {
        "model": "Fama-French 5 Factor + Momentum",
        "observations": int(len(joined)),
        "start": joined.index[0].date().isoformat(),
        "end": joined.index[-1].date().isoformat(),
        "annualized_alpha": (1.0 + alpha_monthly) ** 12 - 1.0,
        "r_squared": r_squared,
        "betas": {
            column: float(value)
            for column, value in zip(factor_columns, coefficients[1:], strict=True)
        },
    }


def returns_based_style(
    simulation: Simulation,
    histories: dict[str, AssetHistory],
) -> dict[str, Any]:
    missing = [symbol for symbol in STYLE_PROXIES.values() if symbol not in histories]
    if missing:
        raise ValueError(f"Missing style proxy history: {', '.join(missing)}")
    portfolio = _monthly_compounded(simulation.daily_returns).rename("portfolio")
    proxies = pd.DataFrame(
        {
            name: _monthly_compounded(histories[symbol].total_returns)
            for name, symbol in STYLE_PROXIES.items()
        }
    )
    joined = proxies.join(portfolio, how="inner").dropna()
    if len(joined) < 24:
        raise ValueError("At least 24 overlapping monthly observations are required")
    x = joined[list(STYLE_PROXIES)].to_numpy(dtype=float)
    y = joined["portfolio"].to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(x, y, rcond=None)
    coefficients = np.clip(coefficients, 0.0, None)
    total = float(coefficients.sum())
    if total <= 0:
        raise ValueError("Style exposure regression did not produce positive coefficients")
    coefficients /= total
    predicted = x @ coefficients
    denominator = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum((y - predicted) ** 2) / denominator) if denominator else 0.0
    exposures = {
        name: float(value)
        for name, value in zip(STYLE_PROXIES, coefficients, strict=True)
    }
    return {
        "model": "Returns-based U.S. equity style proxy",
        "observations": int(len(joined)),
        "start": joined.index[0].date().isoformat(),
        "end": joined.index[-1].date().isoformat(),
        "r_squared": r_squared,
        "exposures": exposures,
        "note": "ETF proxy regression; this is not a holdings-based Morningstar style box.",
    }


def regime_performance(
    simulation: Simulation,
    benchmark: Simulation,
    regime_type: RegimeType,
    fred: FredProvider | None = None,
) -> dict[str, Any]:
    portfolio = _monthly_compounded(simulation.daily_returns).rename("portfolio")
    benchmark_returns = _monthly_compounded(benchmark.daily_returns).rename("benchmark")
    joined = pd.concat([portfolio, benchmark_returns], axis=1).dropna()
    if len(joined) < 12:
        raise ValueError("At least 12 monthly observations are required for regime analysis")

    if regime_type == RegimeType.MARKET:
        benchmark_index = (1.0 + joined["benchmark"]).cumprod()
        moving_average = benchmark_index.rolling(10, min_periods=6).mean()
        labels = pd.Series(index=joined.index, dtype="object")
        valid = moving_average.notna()
        labels.loc[valid] = np.where(
            benchmark_index.loc[valid] >= moving_average.loc[valid],
            "Bull market",
            "Bear market",
        )
    elif regime_type == RegimeType.VOLATILITY:
        volatility = joined["benchmark"].rolling(12, min_periods=6).std() * np.sqrt(12)
        threshold = float(volatility.dropna().median())
        labels = pd.Series(index=joined.index, dtype="object")
        valid = volatility.notna()
        labels.loc[valid] = np.where(
            volatility.loc[valid] >= threshold,
            "High volatility",
            "Low volatility",
        )
    elif regime_type in {RegimeType.INFLATION, RegimeType.BUSINESS_CYCLE}:
        if fred is None:
            raise ValueError("FRED API key is required for macroeconomic regimes")
        inflation = fred.series("CPIAUCSL").resample("ME").last().pct_change(12) * 100.0
        inflation = inflation.reindex(joined.index, method="ffill")
        if regime_type == RegimeType.INFLATION:
            direction = inflation.diff() >= 0
            labels = pd.Series(
                np.select(
                    [
                        (inflation >= 3.0) & direction,
                        (inflation >= 3.0) & ~direction,
                        (inflation < 3.0) & direction,
                    ],
                    ["High and rising", "High and falling", "Low and rising"],
                    default="Low and falling",
                ),
                index=joined.index,
            )
        else:
            growth = fred.series("GDPC1").resample("ME").ffill().pct_change(12) * 100.0
            growth = growth.reindex(joined.index, method="ffill")
            labels = pd.Series(
                np.select(
                    [
                        (growth >= 2.0) & (inflation < 3.0),
                        (growth >= 2.0) & (inflation >= 3.0),
                        (growth < 2.0) & (inflation >= 3.0),
                    ],
                    ["Goldilocks", "Reflation", "Stagflation"],
                    default="Slowdown",
                ),
                index=joined.index,
            )
    else:
        return {"type": "none", "regimes": []}

    joined["regime"] = labels
    rows: list[dict[str, Any]] = []
    for label, group in joined.dropna().groupby("regime", sort=False):
        returns = group["portfolio"]
        annualized = float((1.0 + returns).prod() ** (12.0 / len(returns)) - 1.0)
        rows.append(
            {
                "name": str(label),
                "months": int(len(group)),
                "annualized_return": annualized,
                "annualized_volatility": float(returns.std(ddof=1) * np.sqrt(12)),
                "best_month": float(returns.max()),
                "worst_month": float(returns.min()),
            }
        )
    return {"type": regime_type.value, "regimes": rows}


def _monthly_compounded(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).resample("ME").prod() - 1.0
