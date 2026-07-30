from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache

from app.data.base import AssetHistory
from app.data.corporate_actions import reconcile_corporate_actions

logger = logging.getLogger(__name__)


_EXCHANGE_CURRENCIES = {
    ".AT": "EUR",
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
    ".BA": "ARS",
    ".BK": "THB",
    ".BO": "INR",
    ".BR": "EUR",
    ".CA": "EGP",
    ".CO": "DKK",
    ".HE": "EUR",
    ".IC": "ISK",
    ".IR": "EUR",
    ".IS": "TRY",
    ".JK": "IDR",
    ".JO": "ZAR",
    ".KL": "MYR",
    ".LS": "EUR",
    ".MC": "EUR",
    ".MI": "EUR",
    ".MX": "MXN",
    ".NS": "INR",
    ".NZ": "NZD",
    ".OL": "NOK",
    ".PR": "CZK",
    ".QA": "QAR",
    ".RG": "EUR",
    ".RO": "RON",
    ".SA": "BRL",
    ".SI": "SGD",
    ".SN": "CLP",
    ".SR": "SAR",
    ".ST": "SEK",
    ".SW": "CHF",
    ".TA": "ILS",
    ".VI": "EUR",
    ".VS": "EUR",
    ".WA": "PLN",
}

_CURRENCY_ALIASES = {
    "GBP": "GBP",
    "GBX": "GBP",
    "ZAC": "ZAR",
    "ILA": "ILS",
}

_REPAIR_LOOKBACK_DAYS = 400
_REPAIR_LOOKAHEAD_DAYS = 8
_FX_LOOKBACK_DAYS = 10
_SPLIT_UNDERLYING_TOLERANCE = np.log(1.25)
_SPLIT_MINIMUM_IMPROVEMENT = np.log(1.10)


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


def _normalize_currency(value: object) -> str:
    currency = str(value or "").strip().upper()
    currency = _CURRENCY_ALIASES.get(currency, currency)
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError(f"Yahoo returned invalid quote currency: {value!r}")
    return currency


class YFinanceProvider:
    """Yahoo Finance adapter with short-lived in-process caching.

    The cache is deliberately treated as an optimization, not a source of truth. Cloud Run and
    other serverless environments may discard it at any time.
    """

    def __init__(self, ttl_seconds: int = 21_600, max_items: int = 128) -> None:
        self._cache: TTLCache[tuple[Any, ...], dict[str, AssetHistory]] = TTLCache(
            maxsize=max_items, ttl=ttl_seconds
        )
        self._currency_cache: dict[str, str] = {}
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
        # yfinance's repair logic uses surrounding observations to calibrate dividend and split
        # fixes. Fetching only the visible window raises false-positive risk and cannot repair a
        # split on the requested final date, so retain context and trim it after normalization.
        repair_start = start - timedelta(days=_REPAIR_LOOKBACK_DAYS)
        repair_end = end + timedelta(days=_REPAIR_LOOKAHEAD_DAYS)
        try:
            raw = yf.download(
                tickers=symbols,
                start=repair_start.isoformat(),
                end=repair_end.isoformat(),
                auto_adjust=False,
                actions=True,
                repair=True,
                keepna=True,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=25,
            )
        except Exception as exc:
            raise RuntimeError(f"Yahoo Finance download failed: {exc}") from exc

        if raw.empty:
            raise ValueError("Yahoo Finance returned no observations for the requested assets")

        currencies = self._resolve_currencies(symbols)
        histories: dict[str, AssetHistory] = {}
        for symbol in symbols:
            frame = _ticker_frame(raw, symbol, len(symbols))
            if frame.empty or "Close" not in frame:
                continue
            history = _history_from_frame(
                symbol,
                frame,
                start,
                end,
                currency=currencies[symbol],
            )
            if history is not None:
                histories[symbol] = history

        missing = sorted(set(symbols) - set(histories))
        if missing:
            raise ValueError(f"No usable Yahoo Finance history for: {', '.join(missing)}")
        return histories

    def _resolve_currencies(self, symbols: list[str]) -> dict[str, str]:
        """Resolve Yahoo's actual quote currency instead of assuming exchange currency."""
        if not symbols:
            return {}
        workers = min(len(symbols), 4)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            currencies = list(executor.map(self._resolve_currency, symbols))
        return dict(zip(symbols, currencies, strict=True))

    def _resolve_currency(self, symbol: str) -> str:
        with self._lock:
            cached = self._currency_cache.get(symbol)
        if cached is not None:
            return cached

        errors: list[str] = []
        for _ in range(2):
            try:
                value = yf.Ticker(symbol).fast_info.currency
                currency = _normalize_currency(value)
                with self._lock:
                    self._currency_cache[symbol] = currency
                return currency
            except Exception as exc:
                errors.append(str(exc))
        detail = errors[-1] if errors else "currency metadata was empty"
        raise RuntimeError(f"Unable to verify Yahoo quote currency for {symbol}: {detail}")

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
                fx_cache[key] = self._download_fx_levels(
                    history.currency, base_currency, start, end
                )
            native_index = history.total_returns.index
            fx_window = fx_cache[key].loc[native_index[0] : native_index[-1]]
            valuation_index = native_index.union(fx_window.index).sort_values().unique()
            # Retain the downloaded lookback while forward-filling so a local-market holiday
            # at the beginning of the window never borrows a future FX quote.
            fx_levels = (
                fx_cache[key]
                .reindex(fx_cache[key].index.union(valuation_index))
                .sort_index()
                .ffill()
                .reindex(valuation_index)
                .bfill()
            )
            if fx_levels.isna().any():
                raise ValueError(f"Unable to align {key} FX history with {symbol}")
            fx_returns = fx_levels.pct_change(fill_method=None).fillna(0.0)
            fx_returns.iloc[0] = 0.0
            native_total = history.total_returns.reindex(valuation_index).fillna(0.0)
            native_dividend = history.dividend_returns.reindex(valuation_index).fillna(0.0)
            total = (1.0 + native_total) * (1.0 + fx_returns) - 1.0
            # A distribution is cash, not a multiplicative return factor. Convert its value at
            # the current FX level, then preserve the exact additive identity total=price+cash.
            dividend = native_dividend * (1.0 + fx_returns)
            price = total - dividend
            result[symbol] = AssetHistory(
                symbol=history.symbol,
                name=history.name,
                currency=history.currency,
                total_returns=total,
                price_returns=price,
                dividend_returns=dividend,
                dividends=history.dividends.reindex(valuation_index).fillna(0.0),
                dividend_events=history.dividend_events,
                capital_gain_events=history.capital_gain_events,
                split_events=history.split_events,
                repaired_observations=history.repaired_observations,
                split_corrections=history.split_corrections,
            )
        return result

    def _download_fx_levels(
        self, source_currency: str, target_currency: str, start: date, end: date
    ) -> pd.Series:
        candidates = _fx_candidates(source_currency, target_currency)
        for ticker, invert in candidates:
            try:
                raw = yf.download(
                    ticker,
                    start=(start - timedelta(days=_FX_LOOKBACK_DAYS)).isoformat(),
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
                series = series.replace([np.inf, -np.inf], np.nan).dropna()
                if series.notna().sum() > 1:
                    return series
            except Exception as exc:
                logger.warning("FX download failed for %s: %s", ticker, exc)
        raise ValueError(
            f"Unable to convert {source_currency} assets into {target_currency}; "
            "no Yahoo FX history was available"
        )


def _history_from_frame(
    symbol: str,
    frame: pd.DataFrame,
    start: date,
    end: date,
    *,
    currency: str,
) -> AssetHistory | None:
    """Normalize repaired Yahoo rows into split-safe, additive return components."""
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame = frame.sort_index()
    frame = frame.loc[~frame.index.duplicated(keep="last")]

    close = _numeric_column(frame, "Close").where(lambda values: values > 0)
    raw_adjusted = _numeric_column(frame, "Adj Close", default=np.nan).where(
        lambda values: values > 0
    )
    has_adjusted = raw_adjusted.notna().sum() >= 2
    if has_adjusted:
        adjustment_ratio = (raw_adjusted / close).replace([np.inf, -np.inf], np.nan)
        adjustment_ratio = adjustment_ratio.bfill().ffill()
        adjusted = raw_adjusted.fillna(close * adjustment_ratio)
    else:
        adjusted = close.copy()

    valid = close.notna() & adjusted.notna()
    if valid.sum() < 2:
        return None
    price_index = pd.DatetimeIndex(frame.index[valid])
    close = close.loc[price_index]
    adjusted = adjusted.loc[price_index]

    dividends = _align_actions(_numeric_column(frame, "Dividends"), price_index)
    capital_gains = _align_actions(_numeric_column(frame, "Capital Gains"), price_index)
    splits = _align_actions(
        _numeric_column(frame, "Stock Splits"), price_index, compound=True
    )
    negative_distributions = (dividends < 0) | (capital_gains < 0)
    if negative_distributions.any():
        logger.warning("Ignored negative Yahoo distribution for %s", symbol)
        dividends = dividends.clip(lower=0.0)
        capital_gains = capital_gains.clip(lower=0.0)
    distributions = dividends + capital_gains

    reconciliation = reconcile_corporate_actions(
        close=close,
        adjusted=adjusted,
        splits=splits,
        distributions=distributions,
    )
    close_gross = reconciliation.close_gross
    adjusted_gross = reconciliation.adjusted_gross
    splits = reconciliation.splits
    split_fixes = reconciliation.corrections
    distribution_returns = (distributions / close.shift(1)).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0.0)

    fallback_price_returns = close_gross - 1.0
    fallback_total_returns = fallback_price_returns + distribution_returns
    if has_adjusted:
        total_returns = adjusted_gross - 1.0
        valid_total = np.isfinite(total_returns) & (total_returns >= -1.0)
        total_returns = total_returns.where(valid_total, fallback_total_returns)
    else:
        total_returns = fallback_total_returns

    # Cash distributions add to the price return. Dividing one factor by another subtly
    # overstates non-reinvested results and breaks again after FX conversion.
    price_returns = total_returns - distribution_returns
    invalid_price = ~np.isfinite(price_returns) | (price_returns < -1.0)
    if invalid_price.any():
        price_returns = price_returns.where(~invalid_price, fallback_price_returns)
        total_returns = total_returns.where(
            ~invalid_price, price_returns + distribution_returns
        )

    in_window = (price_index >= pd.Timestamp(start)) & (price_index <= pd.Timestamp(end))
    if in_window.sum() < 2:
        return None
    window_index = price_index[in_window]
    total_returns = total_returns.loc[window_index].astype(float)
    price_returns = price_returns.loc[window_index].astype(float)
    distribution_returns = distribution_returns.loc[window_index].astype(float)
    distributions = distributions.loc[window_index].astype(float)

    first = window_index[0]
    total_returns.loc[first] = 0.0
    price_returns.loc[first] = 0.0
    distribution_returns.loc[first] = 0.0

    repaired = _numeric_column(frame, "Repaired?").astype(bool)
    repaired_observations = int(repaired.reindex(window_index, fill_value=False).sum())
    split_events = int(
        ((splits.loc[window_index] > 0) & ~np.isclose(splits.loc[window_index], 1.0)).sum()
    )
    split_corrections = int(
        split_fixes.reindex(window_index, fill_value=False).sum()
    )

    return AssetHistory(
        symbol=symbol,
        name=symbol,
        currency=currency,
        total_returns=total_returns,
        price_returns=price_returns,
        dividend_returns=distribution_returns,
        dividends=distributions,
        dividend_events=int((dividends.loc[window_index] > 0).sum()),
        capital_gain_events=int((capital_gains.loc[window_index] > 0).sum()),
        split_events=split_events,
        repaired_observations=repaired_observations,
        split_corrections=split_corrections,
    )


def _numeric_column(
    frame: pd.DataFrame, name: str, *, default: float = 0.0
) -> pd.Series:
    if name not in frame:
        return pd.Series(default, index=frame.index, dtype=float)
    values = frame[name]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(
        default
    )


def _align_actions(
    actions: pd.Series, price_index: pd.DatetimeIndex, *, compound: bool = False
) -> pd.Series:
    """Move action-only rows onto the next observed price interval without dropping them."""
    result = pd.Series(0.0, index=price_index, dtype=float)
    for timestamp, value in actions.items():
        amount = float(value)
        if not np.isfinite(amount) or amount == 0.0:
            continue
        position = int(price_index.searchsorted(pd.Timestamp(timestamp), side="left"))
        if position >= len(price_index):
            continue
        target = price_index[position]
        if compound and result.loc[target] != 0.0:
            result.loc[target] *= amount
        else:
            result.loc[target] += amount
    return result


def _correct_residual_splits(
    gross_returns: pd.Series, splits: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Conservatively repair an unmistakable unadjusted split transition."""
    corrected = gross_returns.astype(float).copy()
    changed = pd.Series(False, index=corrected.index, dtype=bool)
    for timestamp, ratio_value in splits.items():
        ratio = float(ratio_value)
        gross = float(corrected.get(timestamp, np.nan))
        if (
            not np.isfinite(ratio)
            or ratio <= 0.0
            or np.isclose(ratio, 1.0)
            or not np.isfinite(gross)
            or gross <= 0.0
        ):
            continue
        candidate = gross * ratio
        if candidate <= 0.0 or not np.isfinite(candidate):
            continue
        raw_distance = abs(np.log(gross))
        candidate_distance = abs(np.log(candidate))
        if (
            candidate_distance <= _SPLIT_UNDERLYING_TOLERANCE
            and raw_distance - candidate_distance >= _SPLIT_MINIMUM_IMPROVEMENT
        ):
            corrected.loc[timestamp] = candidate
            changed.loc[timestamp] = True
    return corrected, changed


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
        dividend_events=history.dividend_events,
        capital_gain_events=history.capital_gain_events,
        split_events=history.split_events,
        repaired_observations=history.repaired_observations,
        split_corrections=history.split_corrections,
    )
