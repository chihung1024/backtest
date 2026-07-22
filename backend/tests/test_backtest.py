from __future__ import annotations

import pandas as pd
import pytest
from conftest import history

from app.engine.backtest import align_histories, simulate_portfolio, to_portfolio_result
from app.models import BacktestRequest


def test_zero_returns_preserve_capital(base_request: BacktestRequest) -> None:
    histories = {
        "AAA": history("AAA", [0.0] * 20),
        "BBB": history("BBB", [0.0] * 20),
    }
    aligned = align_histories(histories, ["AAA", "BBB"])
    simulation = simulate_portfolio(base_request.portfolios[0], aligned, base_request)
    result = to_portfolio_result(simulation, base_request)
    assert simulation.equity.iloc[-1] == pytest.approx(10_000)
    assert result.metrics["total_return"] == pytest.approx(0.0)
    assert result.metrics["cagr"] == pytest.approx(0.0)
    assert result.target_allocation == {"AAA": pytest.approx(0.6), "BBB": pytest.approx(0.4)}
    assert result.display_name == "Balanced · AAA 60% · BBB 40%"


def test_result_label_lists_only_three_largest_target_allocations() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Diversified",
                    "assets": [
                        {"symbol": "SMALL", "weight": 10},
                        {"symbol": "CORE", "weight": 40},
                        {"symbol": "BOND", "weight": 30},
                        {"symbol": "GOLD", "weight": 20},
                    ],
                }
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        }
    )
    histories = {symbol: history(symbol, [0.0, 0.0]) for symbol in request.symbols}
    aligned = align_histories(histories, request.symbols)

    result = to_portfolio_result(
        simulate_portfolio(request.portfolios[0], aligned, request),
        request,
    )

    assert result.display_name == "Diversified · CORE 40% · BOND 30% · GOLD 20%"
    assert result.target_allocation == {
        "SMALL": pytest.approx(0.1),
        "CORE": pytest.approx(0.4),
        "BOND": pytest.approx(0.3),
        "GOLD": pytest.approx(0.2),
    }


def test_daily_returns_compound() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Growth", "assets": [{"symbol": "AAA", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "initial_amount": 1_000,
            "rebalancing": {"frequency": "none"},
        }
    )
    values = [0.0, 0.01, 0.01, -0.005]
    aligned = align_histories({"AAA": history("AAA", values)}, ["AAA"])
    simulation = simulate_portfolio(request.portfolios[0], aligned, request)
    expected = 1_000 * 1.01 * 1.01 * 0.995
    assert simulation.equity.iloc[-1] == pytest.approx(expected)
    assert simulation.return_index.iloc[-1] == pytest.approx(expected / 1_000)


def test_default_result_preserves_each_daily_drawdown_point() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Daily", "assets": [{"symbol": "AAA", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "initial_amount": 1_000,
            "rebalancing": {"frequency": "none"},
        }
    )
    aligned = align_histories(
        {"AAA": history("AAA", [0.0, 0.10, -0.20, 0.25])}, ["AAA"]
    )

    result = to_portfolio_result(
        simulate_portfolio(request.portfolios[0], aligned, request), request
    )

    assert len(result.series) == 4
    assert result.series[2].drawdown == pytest.approx(-0.20)
    assert result.metrics["max_drawdown"] == pytest.approx(-0.20)


def test_cashflows_change_balance_not_time_weighted_return() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Saver", "assets": [{"symbol": "AAA", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "initial_amount": 1_000,
            "cashflow": {
                "type": "fixed",
                "amount": 100,
                "frequency": "monthly",
                "timing": "beginning",
            },
            "rebalancing": {"frequency": "none"},
        }
    )
    aligned = align_histories({"AAA": history("AAA", [0.0] * 65)}, ["AAA"])
    simulation = simulate_portfolio(request.portfolios[0], aligned, request)
    assert simulation.flows.sum() > 0
    assert simulation.equity.iloc[-1] == pytest.approx(1_000 + simulation.flows.sum())
    assert simulation.return_index.iloc[-1] == pytest.approx(1.0)


def test_two_times_leverage_doubles_first_day_return() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Leveraged", "assets": [{"symbol": "AAA", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "initial_amount": 1_000,
            "leverage": {"type": "fixed_ratio", "ratio": 2.0},
            "rebalancing": {"frequency": "none"},
        }
    )
    aligned = align_histories({"AAA": history("AAA", [0.0, 0.01])}, ["AAA"])
    simulation = simulate_portfolio(request.portfolios[0], aligned, request)
    assert simulation.equity.iloc[-1] == pytest.approx(1_020)
    assert simulation.daily_returns.iloc[-1] == pytest.approx(0.02)


def test_dividends_can_be_held_as_cash() -> None:
    histories = {
        "AAA": history(
            "AAA",
            [0.0, 0.01, 0.10],
            price_returns=[0.0, 0.0, 0.10],
            dividend_returns=[0.0, 0.01, 0.0],
        )
    }
    base = {
        "portfolios": [
            {"name": "Income", "assets": [{"symbol": "AAA", "weight": 100}]}
        ],
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "initial_amount": 1_000,
        "rebalancing": {"frequency": "none"},
    }
    reinvest = BacktestRequest.model_validate({**base, "reinvest_dividends": True})
    hold = BacktestRequest.model_validate({**base, "reinvest_dividends": False})
    aligned = align_histories(histories, ["AAA"])
    reinvested = simulate_portfolio(reinvest.portfolios[0], aligned, reinvest)
    held = simulate_portfolio(hold.portfolios[0], aligned, hold)
    assert reinvested.equity.iloc[-1] == pytest.approx(1_111)
    assert held.equity.iloc[-1] == pytest.approx(1_110)
    assert held.income.iloc[-1] == pytest.approx(10)

    hidden_request = hold.model_copy(update={"display_income": False})
    hidden_result = to_portfolio_result(held, hidden_request)
    assert hidden_result.income_by_year == {}
    assert all(point.cumulative_income == 0 for point in hidden_result.series)


def test_reinvested_and_cash_distribution_match_on_event_day() -> None:
    histories = {
        "AAA": history(
            "AAA",
            [0.0, 0.01],
            price_returns=[0.0, -0.01],
            dividend_returns=[0.0, 0.02],
        )
    }
    base = {
        "portfolios": [
            {"name": "Distribution", "assets": [{"symbol": "AAA", "weight": 100}]}
        ],
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "initial_amount": 1_000,
        "rebalancing": {"frequency": "none"},
    }
    reinvest = BacktestRequest.model_validate({**base, "reinvest_dividends": True})
    cash = BacktestRequest.model_validate({**base, "reinvest_dividends": False})
    aligned = align_histories(histories, ["AAA"])

    reinvested = simulate_portfolio(reinvest.portfolios[0], aligned, reinvest)
    held = simulate_portfolio(cash.portfolios[0], aligned, cash)

    assert reinvested.equity.iloc[-1] == pytest.approx(1_010)
    assert held.equity.iloc[-1] == pytest.approx(1_010)
    assert held.income.iloc[-1] == pytest.approx(20)


def test_rebalance_restores_target_weights(base_request: BacktestRequest) -> None:
    index = pd.bdate_range("2020-01-01", "2021-01-04")
    a = [0.0] * len(index)
    b = [0.0] * len(index)
    a[10] = 1.0
    histories = {
        "AAA": history("AAA", a),
        "BBB": history("BBB", b),
    }
    aligned = align_histories(histories, ["AAA", "BBB"])
    simulation = simulate_portfolio(base_request.portfolios[0], aligned, base_request)
    assert simulation.final_allocation["AAA"] == pytest.approx(0.6)
    assert simulation.final_allocation["BBB"] == pytest.approx(0.4)


def test_rebalance_costs_are_aggregated_as_metrics() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Costed",
                    "assets": [
                        {"symbol": "AAA", "weight": 50},
                        {"symbol": "BBB", "weight": 50},
                    ],
                }
            ],
            "start_date": "2020-01-01",
            "end_date": "2021-01-04",
            "initial_amount": 10_000,
            "transaction_cost_bps": 10,
            "rebalancing": {"frequency": "annual"},
        }
    )
    index = pd.bdate_range("2020-01-01", "2021-01-04")
    first = [0.0] * len(index)
    first[10] = 0.5
    aligned = align_histories(
        {
            "AAA": history("AAA", first),
            "BBB": history("BBB", [0.0] * len(index)),
        },
        ["AAA", "BBB"],
    )

    simulation = simulate_portfolio(request.portfolios[0], aligned, request)
    result = to_portfolio_result(simulation, request)

    assert simulation.transaction_costs > 0
    assert simulation.rebalance_count == 1
    assert result.metrics["transaction_costs"] == pytest.approx(
        simulation.transaction_costs
    )
    assert not any("rebalance cost" in warning for warning in simulation.warnings)


def test_threshold_rebalancing_works_without_calendar_frequency() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Threshold only",
                    "assets": [
                        {"symbol": "AAA", "weight": 50},
                        {"symbol": "BBB", "weight": 50},
                    ],
                }
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "rebalancing": {"frequency": "none", "threshold_percent": 5},
        }
    )
    aligned = align_histories(
        {
            "AAA": history("AAA", [0.0, 0.5]),
            "BBB": history("BBB", [0.0, 0.0]),
        },
        ["AAA", "BBB"],
    )

    simulation = simulate_portfolio(request.portfolios[0], aligned, request)

    assert simulation.rebalance_count == 1
    assert simulation.final_allocation["AAA"] == pytest.approx(0.5)
    assert simulation.final_allocation["BBB"] == pytest.approx(0.5)


def test_withdrawal_is_capped_at_available_equity() -> None:
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Withdraw", "assets": [{"symbol": "AAA", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "initial_amount": 1_000,
            "cashflow": {
                "type": "fixed",
                "amount": -10_000,
                "frequency": "monthly",
                "timing": "beginning",
            },
            "rebalancing": {"frequency": "none"},
        }
    )
    aligned = align_histories({"AAA": history("AAA", [0.0] * 30)}, ["AAA"])

    simulation = simulate_portfolio(request.portfolios[0], aligned, request)

    assert simulation.flows.sum() == pytest.approx(-1_000)
    assert simulation.equity.iloc[-1] == pytest.approx(0)
    assert any("capped" in warning for warning in simulation.warnings)


def test_alignment_uses_common_window() -> None:
    early = history("AAA", [0.0] * 10, start="2020-01-01")
    late = history("BBB", [0.0] * 10, start="2020-01-06")
    aligned = align_histories({"AAA": early, "BBB": late}, ["AAA", "BBB"])
    assert aligned.start == pd.Timestamp("2020-01-06").date()
    assert aligned.total_returns.isna().sum().sum() == 0
