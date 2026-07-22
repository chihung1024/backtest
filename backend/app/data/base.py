from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd


@dataclass(slots=True)
class AssetHistory:
    symbol: str
    name: str
    currency: str
    total_returns: pd.Series
    price_returns: pd.Series
    dividend_returns: pd.Series
    dividends: pd.Series
    dividend_events: int = 0
    capital_gain_events: int = 0
    split_events: int = 0
    repaired_observations: int = 0
    split_corrections: int = 0

    @property
    def first_date(self) -> date:
        return self.total_returns.first_valid_index().date()

    @property
    def last_date(self) -> date:
        return self.total_returns.last_valid_index().date()


class MarketDataProvider(Protocol):
    def histories(
        self,
        symbols: list[str],
        start: date,
        end: date,
        base_currency: str,
    ) -> dict[str, AssetHistory]: ...

    def search(self, query: str, limit: int = 8) -> list[dict[str, str | None]]: ...
