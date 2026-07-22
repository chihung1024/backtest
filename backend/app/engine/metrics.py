from __future__ import annotations

from datetime import date
from math import sqrt

import numpy as np
import pandas as pd

TRADING_DAYS = 252.0


def drawdown_series(return_index: pd.Series) -> pd.Series:
    running_peak = return_index.cummax()
    return return_index / running_peak - 1.0


def annual_returns(return_index: pd.Series) -> pd.Series:
    levels = return_index.resample("YE").last()
    if levels.empty:
        return pd.Series(dtype=float)
    result = levels.pct_change(fill_method=None)
    result.iloc[0] = levels.iloc[0] - 1.0
    result.index = result.index.year
    return result


def monthly_returns(return_index: pd.Series) -> pd.Series:
    levels = return_index.resample("ME").last()
    if levels.empty:
        return pd.Series(dtype=float)
    result = levels.pct_change(fill_method=None)
    result.iloc[0] = levels.iloc[0] - 1.0
    return result


def compute_real_return_metrics(
    return_index: pd.Series,
    consumer_price_index: pd.Series,
) -> dict[str, float]:
    """Deflate a time-weighted return index with a consumer-price index.

    CPI observations are monthly, while a portfolio return index is normally daily. Forward and
    backward filling assigns the nearest available monthly level to each trading day without
    altering the portfolio's nominal series.
    """
    cpi = consumer_price_index.sort_index().replace([np.inf, -np.inf], np.nan).dropna()
    if cpi.empty:
        raise ValueError("Consumer-price index contains no usable observations")
    aligned = cpi.reindex(return_index.index, method="ffill").bfill()
    if aligned.isna().any() or float(aligned.iloc[0]) <= 0:
        raise ValueError("Consumer-price index does not cover the backtest period")

    inflation_ratio = aligned / float(aligned.iloc[0])
    real_index = return_index / inflation_ratio
    elapsed_days = (return_index.index[-1] - return_index.index[0]).days
    elapsed_years = max(elapsed_days / 365.2425, 1 / 365.2425)
    return {
        "cumulative_inflation": float(inflation_ratio.iloc[-1] - 1.0),
        "real_total_return": float(real_index.iloc[-1] - 1.0),
        "real_cagr": float(real_index.iloc[-1] ** (1.0 / elapsed_years) - 1.0),
    }


def compute_metrics(
    equity: pd.Series,
    daily_returns: pd.Series,
    return_index: pd.Series,
    external_flows: pd.Series,
    initial_amount: float,
    risk_free_rate_percent: float = 0.0,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, float | int | str | None]:
    clean_returns = daily_returns.replace([np.inf, -np.inf], np.nan).dropna()
    elapsed_days = (return_index.index[-1] - return_index.index[0]).days
    elapsed_years = max(elapsed_days / 365.2425, 1 / 365.2425)
    total_return = float(return_index.iloc[-1] - 1.0)
    cagr = float(return_index.iloc[-1] ** (1.0 / elapsed_years) - 1.0)
    volatility = (
        float(clean_returns.std(ddof=1) * sqrt(TRADING_DAYS))
        if len(clean_returns) > 1
        else 0.0
    )
    annual_rf = risk_free_rate_percent / 100.0
    daily_rf = (1.0 + annual_rf) ** (1.0 / TRADING_DAYS) - 1.0
    excess = clean_returns - daily_rf
    sharpe = _safe_ratio(float(excess.mean() * TRADING_DAYS), volatility)
    downside = clean_returns[clean_returns < daily_rf] - daily_rf
    downside_deviation = (
        float(downside.std(ddof=1) * sqrt(TRADING_DAYS)) if len(downside) > 1 else 0.0
    )
    sortino = _safe_ratio(float(excess.mean() * TRADING_DAYS), downside_deviation)

    drawdowns = drawdown_series(return_index)
    max_drawdown = float(drawdowns.min())
    trough = drawdowns.idxmin()
    peak = return_index.loc[:trough].idxmax()
    recovery_candidates = return_index.loc[trough:]
    peak_value = return_index.loc[peak]
    recovered = recovery_candidates[recovery_candidates >= peak_value]
    recovery = recovered.index[0] if not recovered.empty else None
    drawdown_days = int(((recovery or return_index.index[-1]) - peak).days)

    yearly = annual_returns(return_index)
    positive_months = monthly_returns(return_index)
    var_95 = float(clean_returns.quantile(0.05)) if not clean_returns.empty else 0.0
    tail = clean_returns[clean_returns <= var_95]
    cvar_95 = float(tail.mean()) if not tail.empty else var_95
    flows_total = float(external_flows.sum())
    contributions = float(external_flows.clip(lower=0).sum())
    withdrawals = float(-external_flows.clip(upper=0).sum())

    metrics: dict[str, float | int | str | None] = {
        "initial_balance": float(initial_amount),
        "final_balance": float(equity.iloc[-1]),
        "net_contributions": flows_total,
        "contributions": contributions,
        "withdrawals": withdrawals,
        "net_profit": float(equity.iloc[-1] - initial_amount - flows_total),
        "total_return": total_return,
        "cagr": cagr,
        "money_weighted_return": xirr(
            initial_amount=initial_amount,
            final_amount=float(equity.iloc[-1]),
            flows=external_flows,
        ),
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "calmar_ratio": _safe_ratio(cagr, abs(max_drawdown)),
        "var_95_daily": var_95,
        "cvar_95_daily": cvar_95,
        "best_year": float(yearly.max()) if not yearly.empty else None,
        "worst_year": float(yearly.min()) if not yearly.empty else None,
        "positive_month_ratio": (
            float((positive_months > 0).mean()) if not positive_months.empty else None
        ),
        "max_drawdown_start": peak.date().isoformat(),
        "max_drawdown_end": trough.date().isoformat(),
        "recovery_date": recovery.date().isoformat() if recovery is not None else None,
        "drawdown_days": drawdown_days,
    }

    if benchmark_returns is not None:
        joined = pd.concat(
            [clean_returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1
        ).dropna()
        if len(joined) > 2 and joined["benchmark"].var() > 0:
            covariance = float(joined.cov().loc["portfolio", "benchmark"])
            beta = covariance / float(joined["benchmark"].var())
            alpha_daily = joined["portfolio"].mean() - daily_rf - beta * (
                joined["benchmark"].mean() - daily_rf
            )
            metrics.update(
                {
                    "beta": float(beta),
                    "alpha": float((1.0 + alpha_daily) ** TRADING_DAYS - 1.0),
                    "benchmark_correlation": float(joined.corr().loc["portfolio", "benchmark"]),
                }
            )
    return metrics


def xirr(initial_amount: float, final_amount: float, flows: pd.Series) -> float | None:
    dates: list[date] = [flows.index[0].date()]
    amounts: list[float] = [-initial_amount]
    for timestamp, amount in flows.items():
        if abs(float(amount)) < 1e-12:
            continue
        dates.append(timestamp.date())
        amounts.append(-float(amount))
    dates.append(flows.index[-1].date())
    amounts.append(final_amount)

    origin = dates[0]
    years = np.array([(value - origin).days / 365.2425 for value in dates], dtype=float)
    cash = np.array(amounts, dtype=float)

    def npv(rate: float) -> float:
        return float(np.sum(cash / np.power(1.0 + rate, years)))

    low, high = -0.9999, 1.0
    low_value = npv(low)
    high_value = npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high *= 2.0
        high_value = npv(high)
    if not np.isfinite(low_value) or not np.isfinite(high_value) or low_value * high_value > 0:
        return None
    for _ in range(160):
        middle = (low + high) / 2.0
        value = npv(middle)
        if abs(value) < 1e-9:
            return middle
        if low_value * value <= 0:
            high = middle
            high_value = value
        else:
            low = middle
            low_value = value
    return (low + high) / 2.0


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return None
    return numerator / denominator
