from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

_MIN_SCALE_RATIO = 1.20
_MAX_SCALE_RATIO = 100.0
_EXACT_RATIO_TOLERANCE = math.log(1.035)
_INFERRED_RETURN_LIMIT = math.log(1.35)
_MINIMUM_IMPROVEMENT = math.log(1.20)
_SUSPENSION_GAP_DAYS = 4
_COMPLEXITY_PENALTY = 0.0025


@dataclass(slots=True)
class CorporateActionReconciliation:
    close_gross: pd.Series
    adjusted_gross: pd.Series
    splits: pd.Series
    corrections: pd.Series


def reconcile_corporate_actions(
    *,
    close: pd.Series,
    adjusted: pd.Series,
    splits: pd.Series,
    distributions: pd.Series | None = None,
) -> CorporateActionReconciliation:
    """Reconcile explicit and omitted split transitions without symbol-specific rules.

    The resolver uses three independent representations of the same economic path:

    1. explicit split events supplied by the market-data source;
    2. discontinuities in the adjusted-to-unadjusted price factor, after removing the
       exact cash-distribution adjustment; and
    3. a conservative suspension-boundary fallback for feeds where both the split event
       and adjusted-price correction are missing.

    A ratio is applied only when it removes a scale discontinuity. Genuine large returns
    on ordinary consecutive trading days remain untouched.
    """
    index = pd.DatetimeIndex(close.index)
    native_close = _positive_series(close, index)
    native_adjusted = _positive_series(adjusted, index)
    resolved_splits = _numeric_series(splits, index)
    cash_distributions = (
        pd.Series(0.0, index=index, dtype=float)
        if distributions is None
        else _numeric_series(distributions, index)
    )

    close_gross = native_close / native_close.shift(1)
    adjusted_gross = native_adjusted / native_adjusted.shift(1)
    trusted = pd.Series(False, index=index, dtype=bool)

    explicit = (resolved_splits > 0.0) & ~np.isclose(resolved_splits, 1.0)
    trusted.loc[explicit] = True

    adjustment_factor = (native_adjusted / native_close).replace(
        [np.inf, -np.inf], np.nan
    )
    factor_change = adjustment_factor / adjustment_factor.shift(1)
    # Yahoo-style adjusted prices satisfy:
    # factor_change = split_ratio * (1 + cash_distribution / ex_date_close).
    cash_factor = (1.0 + cash_distributions / native_close).replace(
        [np.inf, -np.inf], np.nan
    )
    factor_candidate = factor_change / cash_factor

    for position in range(1, len(index)):
        if explicit.iloc[position]:
            continue
        ratio = _best_simple_ratio(float(factor_candidate.iloc[position]), exact=True)
        if ratio is None:
            continue
        raw_gross = float(close_gross.iloc[position])
        if not _materially_improves(raw_gross, ratio):
            continue
        resolved_splits.iloc[position] = ratio
        trusted.iloc[position] = True

    # Some exchanges suspend an ETF while certificates are replaced. If the upstream feed
    # omits both the action and the adjustment, the resumption row contains the scale change
    # in both Close and Adj Close. Restrict this inference to a multi-day suspension boundary,
    # require both price representations to agree, and require a simple share-count ratio.
    for position in range(1, len(index)):
        ratio_value = float(resolved_splits.iloc[position])
        if ratio_value > 0.0 and not np.isclose(ratio_value, 1.0):
            continue
        if (index[position] - index[position - 1]).days < _SUSPENSION_GAP_DAYS:
            continue

        previous_close = float(native_close.iloc[position - 1])
        distribution = float(cash_distributions.iloc[position])
        if previous_close > 0.0 and distribution / previous_close > 0.05:
            continue

        raw_gross = float(close_gross.iloc[position])
        total_gross = float(adjusted_gross.iloc[position])
        if not _valid_gross(raw_gross) or not _valid_gross(total_gross):
            continue
        if abs(math.log(raw_gross) - math.log(total_gross)) > math.log(1.05):
            continue

        ratio = _best_simple_ratio(1.0 / raw_gross, exact=False)
        if ratio is None or not _materially_improves(raw_gross, ratio):
            continue
        if abs(math.log(raw_gross * ratio)) > _local_return_limit(close_gross, position):
            continue
        resolved_splits.iloc[position] = ratio

    corrections = pd.Series(False, index=index, dtype=bool)
    for position in range(1, len(index)):
        ratio = float(resolved_splits.iloc[position])
        if not np.isfinite(ratio) or ratio <= 0.0 or np.isclose(ratio, 1.0):
            continue
        changed = _apply_ratio(
            close_gross,
            position,
            ratio,
            trusted=bool(trusted.iloc[position]),
        )
        changed = (
            _apply_ratio(
                adjusted_gross,
                position,
                ratio,
                trusted=bool(trusted.iloc[position]),
            )
            or changed
        )
        corrections.iloc[position] = changed

    return CorporateActionReconciliation(
        close_gross=close_gross,
        adjusted_gross=adjusted_gross,
        splits=resolved_splits,
        corrections=corrections,
    )


def _positive_series(values: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    return _numeric_series(values, index).where(lambda item: item > 0.0)


def _numeric_series(values: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    return (
        pd.to_numeric(values.reindex(index), errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype(float)
    )


def _simple_ratio_candidates() -> tuple[tuple[float, float], ...]:
    candidates: list[tuple[float, float]] = []
    for numerator in range(1, 101):
        for denominator in range(1, 101):
            if math.gcd(numerator, denominator) != 1:
                continue
            ratio = numerator / denominator
            scale = max(ratio, 1.0 / ratio)
            if scale < _MIN_SCALE_RATIO or scale > _MAX_SCALE_RATIO:
                continue
            complexity = _COMPLEXITY_PENALTY * (numerator + denominator)
            candidates.append((ratio, complexity))
    return tuple(candidates)


_SIMPLE_RATIOS = _simple_ratio_candidates()


def _best_simple_ratio(target: float, *, exact: bool) -> float | None:
    if not np.isfinite(target) or target <= 0.0:
        return None
    scale = max(target, 1.0 / target)
    if scale < _MIN_SCALE_RATIO or scale > _MAX_SCALE_RATIO * 1.35:
        return None

    best: tuple[float, float, float] | None = None
    for ratio, complexity in _SIMPLE_RATIOS:
        error = abs(math.log(target / ratio))
        score = error + complexity
        if best is None or score < best[0]:
            best = (score, error, ratio)
    if best is None:
        return None

    _, error, ratio = best
    if exact and error > _EXACT_RATIO_TOLERANCE:
        return None
    return ratio


def _valid_gross(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0.0)


def _materially_improves(gross: float, ratio: float) -> bool:
    if not _valid_gross(gross):
        return False
    corrected = gross * ratio
    if not _valid_gross(corrected):
        return False
    return abs(math.log(gross)) - abs(math.log(corrected)) >= _MINIMUM_IMPROVEMENT


def _apply_ratio(
    gross_returns: pd.Series,
    position: int,
    ratio: float,
    *,
    trusted: bool,
) -> bool:
    gross = float(gross_returns.iloc[position])
    if not _materially_improves(gross, ratio):
        return False
    corrected = gross * ratio
    if not trusted and abs(math.log(corrected)) > _local_return_limit(
        gross_returns, position
    ):
        return False
    gross_returns.iloc[position] = corrected
    return True


def _local_return_limit(gross_returns: pd.Series, position: int) -> float:
    positive = gross_returns.where(gross_returns > 0.0)
    log_returns = np.log(positive.replace([np.inf, -np.inf], np.nan))
    start = max(1, position - 20)
    end = min(len(log_returns), position + 6)
    nearby = log_returns.iloc[start:end].drop(
        log_returns.index[position], errors="ignore"
    )
    nearby = nearby.dropna()
    nearby = nearby[nearby.abs() < math.log(1.8)]
    if len(nearby) < 4:
        return _INFERRED_RETURN_LIMIT

    median = float(nearby.median())
    mad = float((nearby - median).abs().median())
    robust_limit = abs(median) + 8.0 * 1.4826 * mad
    return min(
        max(robust_limit, math.log(1.20)),
        _INFERRED_RETURN_LIMIT,
    )
