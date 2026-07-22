from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.data.base import AssetHistory
from app.models import BacktestRequest


def history(
    symbol: str,
    total_returns: list[float],
    *,
    price_returns: list[float] | None = None,
    dividend_returns: list[float] | None = None,
    start: str = "2020-01-01",
    currency: str = "USD",
) -> AssetHistory:
    index = pd.bdate_range(start, periods=len(total_returns))
    total = pd.Series(total_returns, index=index, dtype=float)
    dividends = pd.Series(dividend_returns or [0.0] * len(index), index=index, dtype=float)
    price = pd.Series(
        price_returns if price_returns is not None else total_returns,
        index=index,
        dtype=float,
    )
    return AssetHistory(
        symbol=symbol,
        name=symbol,
        currency=currency,
        total_returns=total,
        price_returns=price,
        dividend_returns=dividends,
        dividends=pd.Series(0.0, index=index),
    )


@pytest.fixture
def base_request() -> BacktestRequest:
    return BacktestRequest.model_validate(
        {
            "portfolios": [
                {
                    "name": "Balanced",
                    "assets": [
                        {"symbol": "AAA", "weight": 60},
                        {"symbol": "BBB", "weight": 40},
                    ],
                }
            ],
            "benchmark": "AAA",
            "start_date": date(2020, 1, 1),
            "end_date": date(2020, 12, 31),
            "initial_amount": 10_000,
            "base_currency": "TWD",
            "rebalancing": {"frequency": "annual"},
        }
    )
