from __future__ import annotations

import logging
import threading
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache

from app.data.base import AssetHistory

logger = logging.getLogger(__name__)


_EXCHANGE_CURRENCIES = {
    ".TW": "TWD",
    ".TWO": "TWD",
    ".L": "GBP",
    ".TO": "CAD",
    ".V": "CAD",
    ".AX": "AUD",
    ".HK": "HKD",
    ".T": "JPY",
    ".KS": "KRW",
    ".KQ": "KRW",
    ".SS": "CNY",
    ".SZ": "CNY",
    ".PA": "EUR",
    ".DE": "EUR",
    ".AS": "EUR",
}


def normalize_symbol(symbol: str) -> str:
    """Normalize common Taiwan shorthand while preserving explicit Yahoo symbols."""
    value = symbol.strip().upper()
    if value.isdigit() and 4 <= len(value) <= 6:
        return f"{value}.TW"
    return value


def infer_currency(symbol: str) -> str:
    for suffix, currency in _EXCHANGE_CURRENCIES.items():
        if symbol.endswith(suffix):
            return currency
    return "USD"


class YFinanceProvider:
    """Yahoo Finance adapter with short-lived in-process caching.

    The cache is deliberately treated as an optimization, not a source of truth. Cloud Run and
    other serverless environments may discard it at any time.
    """

    def __init__(self, ttl_seconds: int = 21_600, max_items: int = 128) -> None:
        self._cache: TTLCache[tuple[Any, ...], dict[str, AssetHistory]] = TTLCache(
            maxsize=max_items, ttl=ttl_seconds
        )
        self._lock = threading.RLock()

    def histories(
        self,
        symbols: list[str],
        start: date,
        end: date,
        base_currency: str,
    ) -> dict[str, AssetHistory]:
        normalized = tuple(sorted({normalize_symbol(symbol) for symbol in symbols}))
        cache_key = (normalized, start.isoformat(), end.isoformat(), base_currency.upper())
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return {key: _copy_history(value) for key, value in cached.items()}

        local = self._download_local(list(normalized), start, end)
        converted = self._convert_currencies(local, base_currency.upper(), start, end)

        with self._lock:
            self._cache[cache_key] = converted
        return {key: _copy_history(value) for key, value in converted.items()}

    def search(self, query: str, limit: int = 8) -> list[dict[str, str | None]]:
        value = query.strip()
        if not value:
            return []

        results: list[dict[str, str | None]] = []
        seen: set[str] = set()

        if value.isdigit() and 4 <= len(value) <= 6:
            for suffix, exchange in ((".TW", "Taiwan"), (".TWO", "Taipei Exchange")):
                symbol = f"{value}{suffix}"
                results.append(
                    {
                        "symbol": symbol,
                        "name": f"{value} ({exchange})",
                        "exchange": exchange,
                        "quote_type": "EQUITY",
                        "currency": "TWD",
                    }
                )
                seen.add(symbol)

        try:
            search = yf.Search(value, max_results=max(limit, 8), news_count=0)
            quotes = search.quotes or []
        except Exception as exc:  # Yahoo availability must not break the whole API.
            logger.warning("Ticker search failed for %s: %s", value, exc)
            quotes = []

        for quote in quotes:
            symbol = str(quote.get("symbol", "")).upper()
            if not symbol or symbol in seen:
                continue
            quote_type = str(quote.get("quoteType", "")).upper()
            if quote_type and quote_type not in {"EQUITY", "ETF", "MUTUALFUND", "INDEX"}:
                continue
            results.append(
                {
                    "symbol": symbol,
                    "name": quote.get("longname") or quote.get("shortname") or symbol,
                    "exchange": quote.get("exchDisp") or quote.get("exchange"),
                    "quote_type": quote_type or None,
                    "currency": quote.get("currency") or infer_currency(symbol),
                }
            )
            seen.add(symbol)
            if len(results) >= limit:
                break
        return results[:limit]

    def _download_local(
        self, symbols: list[str], start: date, end: date
    ) -> dict[str, AssetHistory]:
        if not symbols:
            return {}
        try:
            raw = yf.download(
                tickers=symbols,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                actions=True,
                repair=True,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=25,
            )
        except Exception as exc:
            raise RuntimeError(f"Yahoo Finance download failed: {exc}") from exc

        if raw.empty:
            raise ValueError("Yahoo Finance returned no observations for the requested assets")

        histories: dict[str, AssetHistory] = {}
        for symbol in symbols:
            frame = _ticker_frame(raw, symbol, len(symbols))
            if frame.empty or "Close" not in frame:
                continue
            frame = frame.copy()
            frame.index = pd.to_datetime(frame.index).tz_localize(None)
            close = pd.to_numeric(frame["Close"], errors="coerce").replace(0, np.nan)
            adjusted = pd.to_numeric(
                frame.get("Adj Close", frame["Close"]), errors="coerce"
            ).replace(0, np.nan)
            dividends = pd.to_numeric(
                frame.get("Dividends", pd.Series(0.0, index=frame.index)), errors="coerce"
            ).fillna(0.0)

            total_returns = adjusted.pct_change(fill_method=None)
            dividend_returns = (dividends / close.shift(1)).replace([np.inf, -np.inf], np.nan)
            dividend_returns = dividend_returns.fillna(0.0).clip(lower=0.0, upper=0.5)
            price_returns = ((1.0 + total_returns) / (1.0 + dividend_returns) - 1.0).replace(
                [np.inf, -np.inf], np.nan
            )

            valid = adjusted.notna()
            if valid.sum() < 2:
                continue
            total_returns = total_returns.loc[valid]
            price_returns = price_returns.loc[valid]
            dividend_returns = dividend_returns.loc[valid]
            dividends = dividends.loc[valid]
            first = total_returns.first_valid_index()
            if first is not None:
                total_returns.loc[first] = 0.0
                price_returns.loc[first] = 0.0

            histories[symbol] = AssetHistory(
                symbol=symbol,
                name=symbol,
                currency=infer_currency(symbol),
                total_returns=total_returns.astype(float),
                price_returns=price_returns.astype(float),
                dividend_returns=dividend_returns.astype(float),
                dividends=dividends.astype(float),
            )

        missing = sorted(set(symbols) - set(histories))
        if missing:
            raise ValueError(f"No usable Yahoo Finance history for: {', '.join(missing)}")
        return histories

    def _convert_currencies(
        self,
        histories: dict[str, AssetHistory],
        base_currency: str,
        start: date,
        end: date,
    ) -> dict[str, AssetHistory]:
        result: dict[str, AssetHistory] = {}
        fx_cache: dict[str, pd.Series] = {}

        for symbol, history in histories.items():
            if history.currency == base_currency:
                result[symbol] = history
                continue

            key = f"{history.currency}/{base_currency}"
            if key not in fx_cache:
                fx_cache[key] = self._download_fx(
                    history.currency, base_currency, start, end
                )
            fx_returns = fx_cache[key].reindex(history.total_returns.index).ffill().fillna(0.0)
            total = (1.0 + history.total_returns) * (1.0 + fx_returns) - 1.0
            price = (1.0 + history.price_returns) * (1.0 + fx_returns) - 1.0
            dividend = ((1.0 + total) / (1.0 + price) - 1.0).replace(
                [np.inf, -np.inf], np.nan
            ).fillna(0.0)
            result[symbol] = AssetHistory(
                symbol=history.symbol,
                name=history.name,
                currency=history.currency,
                total_returns=total,
                price_returns=price,
                dividend_returns=dividend,
                dividends=history.dividends,
            )
        return result

    def _download_fx(
        self, source_currency: str, target_currency: str, start: date, end: date
    ) -> pd.Series:
        candidates = _fx_candidates(source_currency, target_currency)
        for ticker, invert in candidates:
            try:
                raw = yf.download(
                    ticker,
                    start=start.isoformat(),
                    end=(end + timedelta(days=1)).isoformat(),
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                    timeout=20,
                )
                if raw.empty:
                    continue
                close = raw["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                close.index = pd.to_datetime(close.index).tz_localize(None)
                series = close.astype(float)
                if invert:
                    series = 1.0 / series
                returns = series.pct_change(fill_method=None).fillna(0.0)
                if returns.notna().sum() > 1:
                    return returns
            except Exception as exc:
                logger.warning("FX download failed for %s: %s", ticker, exc)
        raise ValueError(
            f"Unable to convert {source_currency} assets into {target_currency}; "
            "no Yahoo FX history was available"
        )


def _ticker_frame(raw: pd.DataFrame, symbol: str, symbol_count: int) -> pd.DataFrame:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw if symbol_count == 1 else pd.DataFrame()
    level_zero = set(raw.columns.get_level_values(0))
    level_one = set(raw.columns.get_level_values(1))
    if symbol in level_zero:
        return raw[symbol]
    if symbol in level_one:
        return raw.xs(symbol, axis=1, level=1)
    return pd.DataFrame()


def _fx_candidates(source: str, target: str) -> list[tuple[str, bool]]:
    if source == target:
        return []
    candidates = [(f"{source}{target}=X", False), (f"{target}{source}=X", True)]
    # Yahoo's legacy USD crosses are often shorter and more reliable.
    if source == "USD":
        candidates.insert(0, (f"{target}=X", False))
    elif target == "USD":
        candidates.insert(0, (f"{source}=X", True))
    return candidates


def _copy_history(history: AssetHistory) -> AssetHistory:
    return AssetHistory(
        symbol=history.symbol,
        name=history.name,
        currency=history.currency,
        total_returns=history.total_returns.copy(),
        price_returns=history.price_returns.copy(),
        dividend_returns=history.dividend_returns.copy(),
        dividends=history.dividends.copy(),
    )
