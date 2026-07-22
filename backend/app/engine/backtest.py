from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.data.base import AssetHistory
from app.engine.metrics import (
    annual_returns,
    compute_metrics,
    compute_real_return_metrics,
    drawdown_series,
    monthly_returns,
)
from app.models import (
    BacktestRequest,
    CashflowType,
    LeverageConfig,
    LeverageType,
    OutputFrequency,
    PortfolioDefinition,
    PortfolioResult,
    RebalanceFrequency,
)


@dataclass(slots=True)
class AlignedHistories:
    total_returns: pd.DataFrame
    price_returns: pd.DataFrame
    dividend_returns: pd.DataFrame
    start: date
    end: date


@dataclass(slots=True)
class Simulation:
    name: str
    equity: pd.Series
    return_index: pd.Series
    daily_returns: pd.Series
    flows: pd.Series
    income: pd.Series
    final_allocation: dict[str, float]
    target_allocation: dict[str, float] = field(default_factory=dict)
    transaction_costs: float = 0.0
    borrowing_costs: float = 0.0
    rebalance_count: int = 0
    warnings: list[str] = field(default_factory=list)


def align_histories(
    histories: dict[str, AssetHistory], symbols: Iterable[str]
) -> AlignedHistories:
    selected = [histories[symbol] for symbol in symbols]
    if not selected:
        raise ValueError("At least one asset history is required")
    start = max(history.total_returns.first_valid_index() for history in selected)
    end = min(history.total_returns.last_valid_index() for history in selected)
    if start >= end:
        raise ValueError("The selected assets do not have an overlapping history")

    index = selected[0].total_returns.loc[start:end].index
    for history in selected[1:]:
        index = index.union(history.total_returns.loc[start:end].index)
    index = pd.DatetimeIndex(index).sort_values().unique()

    def frame_for(attribute: str) -> pd.DataFrame:
        values = {
            history.symbol: getattr(history, attribute).loc[start:end].reindex(index).fillna(0.0)
            for history in selected
        }
        frame = pd.DataFrame(values, index=index).astype(float)
        frame.iloc[0] = 0.0
        return frame

    return AlignedHistories(
        total_returns=frame_for("total_returns"),
        price_returns=frame_for("price_returns"),
        dividend_returns=frame_for("dividend_returns"),
        start=start.date(),
        end=end.date(),
    )


def simulate_portfolio(
    portfolio: PortfolioDefinition,
    aligned: AlignedHistories,
    request: BacktestRequest,
) -> Simulation:
    symbols = [asset.symbol for asset in portfolio.assets]
    weights = np.array([asset.weight / 100.0 for asset in portfolio.assets], dtype=float)
    total_returns = aligned.total_returns[symbols]
    price_returns = aligned.price_returns[symbols]
    dividend_returns = aligned.dividend_returns[symbols]
    index = total_returns.index

    asset_values, debt = _initial_exposure(request.initial_amount, weights, request.leverage)
    cash = 0.0
    cumulative_income = 0.0
    transaction_costs = 0.0
    borrowing_costs = 0.0
    rebalance_count = 0
    capped_withdrawals = 0
    liquidated = False
    warnings: list[str] = []

    equity_values = pd.Series(index=index, dtype=float)
    strategy_returns = pd.Series(0.0, index=index, dtype=float)
    external_flows = pd.Series(0.0, index=index, dtype=float)
    income_values = pd.Series(0.0, index=index, dtype=float)
    return_levels = pd.Series(1.0, index=index, dtype=float)

    equity_values.iloc[0] = request.initial_amount
    income_values.iloc[0] = 0.0
    cashflow_mask = _event_mask(index, request.cashflow.frequency.value, request.cashflow.timing)
    rebalance_mask = _event_mask(index, request.rebalancing.frequency.value, "beginning")

    for position in range(1, len(index)):
        timestamp = index[position]
        previous_equity = float(equity_values.iloc[position - 1])
        if liquidated or previous_equity <= 0:
            equity_values.iloc[position] = max(previous_equity, 0.0)
            return_levels.iloc[position] = return_levels.iloc[position - 1]
            income_values.iloc[position] = cumulative_income
            continue

        previous_assets = asset_values.copy()
        day_income = float(np.dot(previous_assets, dividend_returns.iloc[position].to_numpy()))
        cumulative_income += max(day_income, 0.0)

        chosen_returns = (
            total_returns.iloc[position].to_numpy()
            if request.reinvest_dividends
            else price_returns.iloc[position].to_numpy()
        )
        asset_values *= 1.0 + np.nan_to_num(chosen_returns, nan=0.0)
        if not request.reinvest_dividends:
            cash += day_income

        interest = debt * (request.leverage.annual_interest_rate / 100.0) / 365.2425
        cash -= interest
        borrowing_costs += interest

        pre_flow_equity = float(asset_values.sum() + cash - debt)
        flow = 0.0
        if cashflow_mask[position] and request.cashflow.type != CashflowType.NONE:
            flow = _cashflow_amount(request, timestamp, pre_flow_equity, index[0])
            if flow < -max(pre_flow_equity, 0.0):
                flow = -max(pre_flow_equity, 0.0)
                capped_withdrawals += 1
            asset_values, debt, cash = _apply_external_flow(
                asset_values, debt, cash, flow, weights, request.leverage
            )
            external_flows.iloc[position] = flow

        should_rebalance = bool(rebalance_mask[position])
        if request.rebalancing.threshold_percent is not None:
            should_rebalance = should_rebalance or _threshold_breached(
                asset_values,
                weights,
                request.rebalancing.threshold_percent / 100.0,
            )
        if should_rebalance and (
            request.rebalancing.frequency != RebalanceFrequency.NONE
            or request.rebalancing.threshold_percent is not None
        ):
            asset_values, debt, cash, cost = _rebalance(
                asset_values,
                debt,
                cash,
                weights,
                request.leverage,
                request.transaction_cost_bps,
            )
            transaction_costs += cost
            rebalance_count += 1

        final_equity = float(asset_values.sum() + cash - debt)
        gross_exposure = float(asset_values.sum())
        margin_ratio = final_equity / gross_exposure * 100.0 if gross_exposure > 0 else 100.0
        if (
            request.leverage.type != LeverageType.NONE
            and margin_ratio < request.leverage.maintenance_margin
        ):
            warnings.append(
                f"Margin call on {timestamp.date().isoformat()} at {margin_ratio:.2f}% equity"
            )
            final_equity = max(final_equity, 0.0)
            asset_values = np.zeros_like(asset_values)
            debt = 0.0
            cash = final_equity
            liquidated = True

        daily_return = (
            (final_equity - flow) / previous_equity - 1.0 if previous_equity > 0 else 0.0
        )
        if not np.isfinite(daily_return):
            daily_return = 0.0
        strategy_returns.iloc[position] = daily_return
        return_levels.iloc[position] = max(
            return_levels.iloc[position - 1] * (1.0 + daily_return), 0.0
        )
        equity_values.iloc[position] = final_equity
        income_values.iloc[position] = cumulative_income

    gross = float(asset_values.sum())
    if capped_withdrawals:
        warnings.append(
            f"{capped_withdrawals} withdrawal(s) were capped at available portfolio equity"
        )
    final_allocation = {
        symbol: (float(value / gross) if gross > 0 else 0.0)
        for symbol, value in zip(symbols, asset_values, strict=True)
    }
    return Simulation(
        name=portfolio.name,
        equity=equity_values,
        return_index=return_levels,
        daily_returns=strategy_returns,
        flows=external_flows,
        income=income_values,
        final_allocation=final_allocation,
        target_allocation={
            asset.symbol: float(asset.weight / 100.0) for asset in portfolio.assets
        },
        transaction_costs=transaction_costs,
        borrowing_costs=borrowing_costs,
        rebalance_count=rebalance_count,
        warnings=_deduplicate(warnings),
    )


def to_portfolio_result(
    simulation: Simulation,
    request: BacktestRequest,
    benchmark_returns: pd.Series | None = None,
    factor_analysis: dict[str, object] | None = None,
    style_analysis: dict[str, object] | None = None,
    regime_analysis: dict[str, object] | None = None,
    inflation_index: pd.Series | None = None,
    is_benchmark: bool = False,
) -> PortfolioResult:
    metrics = compute_metrics(
        equity=simulation.equity,
        daily_returns=simulation.daily_returns,
        return_index=simulation.return_index,
        external_flows=simulation.flows,
        initial_amount=request.initial_amount,
        risk_free_rate_percent=request.analytics.risk_free_rate,
        benchmark_returns=benchmark_returns,
    )
    metrics.update(
        {
            "transaction_costs": simulation.transaction_costs,
            "borrowing_costs": simulation.borrowing_costs,
            "rebalance_count": simulation.rebalance_count,
        }
    )
    if inflation_index is not None:
        metrics.update(compute_real_return_metrics(simulation.return_index, inflation_index))
    drawdowns = drawdown_series(simulation.return_index)
    displayed_income = (
        simulation.income
        if request.display_income
        else pd.Series(0.0, index=simulation.income.index)
    )
    sampled = _sample_frame(
        pd.DataFrame(
            {
                "value": simulation.equity,
                "return_index": simulation.return_index,
                "drawdown": drawdowns,
                "cumulative_income": displayed_income,
            }
        ),
        request.output_frequency,
    )
    series = [
        {
            "date": timestamp.date(),
            "value": _finite(row["value"]),
            "return_index": _finite(row["return_index"]),
            "drawdown": _finite(row["drawdown"]),
            "cumulative_income": _finite(row["cumulative_income"]),
        }
        for timestamp, row in sampled.iterrows()
    ]
    yearly = annual_returns(simulation.return_index)
    monthly = monthly_returns(simulation.return_index)
    income_yearly = pd.Series(dtype=float)
    if request.display_income:
        income_yearly = simulation.income.resample("YE").last().diff()
        if not income_yearly.empty:
            income_yearly.iloc[0] = simulation.income.resample("YE").last().iloc[0]

    target_allocation = simulation.target_allocation or simulation.final_allocation
    return PortfolioResult(
        name=simulation.name,
        display_name=_portfolio_display_name(
            simulation.name,
            target_allocation,
            is_benchmark=is_benchmark,
        ),
        metrics={key: _finite(value) for key, value in metrics.items()},
        series=series,
        annual_returns={str(year): _finite(value) for year, value in yearly.items()},
        monthly_returns=[
            {"year": int(timestamp.year), "month": int(timestamp.month), "return": _finite(value)}
            for timestamp, value in monthly.items()
        ],
        income_by_year={
            str(timestamp.year): _finite(value) for timestamp, value in income_yearly.items()
        },
        target_allocation={
            key: float(value) for key, value in target_allocation.items()
        },
        final_allocation={
            key: _finite(value) for key, value in simulation.final_allocation.items()
        },
        factor_analysis=factor_analysis,
        style_analysis=style_analysis,
        regime_analysis=regime_analysis,
    )


def _portfolio_display_name(
    name: str,
    target_allocation: dict[str, float],
    *,
    is_benchmark: bool,
) -> str:
    if is_benchmark or not target_allocation:
        return name
    largest = sorted(
        target_allocation.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    holdings = [f"{symbol} {_format_target_weight(weight)}" for symbol, weight in largest]
    return " · ".join([name, *holdings])


def _format_target_weight(weight: float) -> str:
    percentage = weight * 100.0
    value = f"{percentage:.2f}".rstrip("0").rstrip(".")
    return f"{value}%"


def _initial_exposure(
    equity: float, weights: np.ndarray, leverage: LeverageConfig
) -> tuple[np.ndarray, float]:
    if leverage.type == LeverageType.FIXED_RATIO:
        debt = equity * (leverage.ratio - 1.0)
    elif leverage.type == LeverageType.FIXED_DEBT:
        debt = leverage.debt_amount
    else:
        debt = 0.0
    return weights * (equity + debt), debt


def _apply_external_flow(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    flow: float,
    weights: np.ndarray,
    leverage: LeverageConfig,
) -> tuple[np.ndarray, float, float]:
    if abs(flow) < 1e-12:
        return asset_values, debt, cash
    if flow > 0:
        if leverage.type == LeverageType.FIXED_RATIO:
            asset_values += weights * flow * leverage.ratio
            debt += flow * (leverage.ratio - 1.0)
        else:
            asset_values += weights * flow
        return asset_values, debt, cash

    withdrawal = -flow
    available_cash = max(cash, 0.0)
    from_cash = min(available_cash, withdrawal)
    cash -= from_cash
    remaining = withdrawal - from_cash
    if remaining <= 0:
        return asset_values, debt, cash

    equity = float(asset_values.sum() + cash - debt)
    if equity <= 0:
        return np.zeros_like(asset_values), 0.0, 0.0
    fraction = min(remaining / equity, 1.0)
    if leverage.type == LeverageType.FIXED_RATIO:
        asset_values *= 1.0 - fraction
        debt *= 1.0 - fraction
    else:
        gross = float(asset_values.sum())
        if gross > 0:
            asset_values *= max(1.0 - remaining / gross, 0.0)
    return asset_values, debt, cash


def _rebalance(
    asset_values: np.ndarray,
    debt: float,
    cash: float,
    weights: np.ndarray,
    leverage: LeverageConfig,
    transaction_cost_bps: float,
) -> tuple[np.ndarray, float, float, float]:
    equity = float(asset_values.sum() + cash - debt)
    if equity <= 0:
        return np.zeros_like(asset_values), 0.0, 0.0, 0.0
    target, target_debt = _initial_exposure(equity, weights, leverage)
    traded_notional = float(np.abs(target - asset_values).sum())
    cost = traded_notional * transaction_cost_bps / 10_000.0
    net_equity = max(equity - cost, 0.0)
    target, target_debt = _initial_exposure(net_equity, weights, leverage)
    return target, target_debt, 0.0, cost


def _threshold_breached(
    asset_values: np.ndarray, target_weights: np.ndarray, threshold: float
) -> bool:
    gross = float(asset_values.sum())
    if gross <= 0:
        return False
    current = asset_values / gross
    return bool(np.max(np.abs(current - target_weights)) >= threshold)


def _cashflow_amount(
    request: BacktestRequest,
    timestamp: pd.Timestamp,
    equity: float,
    start: pd.Timestamp,
) -> float:
    config = request.cashflow
    years = max(int((timestamp - start).days / 365.2425), 0)
    growth = (1.0 + config.annual_growth_rate / 100.0) ** years
    if config.type == CashflowType.PERCENT:
        return equity * config.amount / 100.0 * growth
    return config.amount * growth


def _event_mask(index: pd.DatetimeIndex, frequency: str, timing: str) -> np.ndarray:
    mask = np.zeros(len(index), dtype=bool)
    if frequency == "none" or len(index) < 2:
        return mask
    if frequency == "monthly":
        keys = index.year * 12 + index.month
    elif frequency == "quarterly":
        keys = index.year * 4 + index.quarter
    elif frequency == "semiannual":
        keys = index.year * 2 + ((index.month - 1) // 6)
    elif frequency == "annual":
        keys = index.year
    else:
        return mask
    if timing == "beginning":
        mask[1:] = keys[1:] != keys[:-1]
    else:
        mask[:-1] = keys[:-1] != keys[1:]
    return mask


def _sample_frame(frame: pd.DataFrame, frequency: OutputFrequency) -> pd.DataFrame:
    if frequency == OutputFrequency.DAILY:
        return frame
    rule = "W-FRI" if frequency == OutputFrequency.WEEKLY else "ME"
    sampled = frame.resample(rule).last().dropna(how="all")
    first = frame.iloc[[0]]
    last = frame.iloc[[-1]]
    combined = pd.concat([first, sampled, last])
    return combined.loc[lambda value: ~value.index.duplicated()].sort_index()


def _finite(value: object) -> object:
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
