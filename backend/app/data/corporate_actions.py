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
_MIN_MISSING_BUSINESS_DAYS = 3
_MAX_ROWS_BEFORE_SYNTHETIC_SUSPENSION = 3
_MIN_SYNTHETIC_SUSPENSION_ROWS = 3
_SYNTHETIC_SUSPENSION_PRICE_TOLERANCE = math.log(1.0025)
_POST_SUSPENSION_RETURN_LIMIT = math.log(1.20)
_COMPLEXITY_PENALTY = 0.0025


@dataclass(slots=True)
class CorporateActionReconciliation:
    close_gross: pd.Series
    adjusted_gross: pd.Series
    splits: pd.Series
    distribution_multipliers: pd.Series
    corrections: pd.Series


def reconcile_corporate_actions(
    *,
    close: pd.Series,
    adjusted: pd.Series,
    splits: pd.Series,
    distributions: pd.Series | None = None,
) -> CorporateActionReconciliation:
    """Reconcile explicit and omitted share-scale transitions without symbol rules.

    The resolver uses four independent representations of the same economic path:

    1. explicit split events supplied by the market-data source;
    2. discontinuities in the adjusted-to-unadjusted price factor, after removing the
       exact cash-distribution adjustment;
    3. a pre-positioned scale transition followed by a synthetic suspension plateau,
       for feeds that rewrite a few pre-suspension rows into post-action units; and
    4. a missing-date suspension boundary for feeds where the suspended dates are absent.

    A ratio is applied only when it removes a price-unit discontinuity. Genuine large
    returns on ordinary consecutive trading days remain untouched unless the surrounding
    rows independently exhibit a synthetic suspension pattern. The returned distribution
    multiplier records whether the prior close was expressed in pre-action units, so cash
    paid per current unit is converted to the same economic basis exactly.
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
    # With distributions quoted per post-action unit, adjusted prices satisfy:
    # factor_change = share_multiplier * (1 + distribution / ex-date close).
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

    # Some feeds rewrite one or more final pre-suspension rows into post-action units and
    # then emit artificial flat OHLC rows during the suspension. In that representation the
    # scale break occurs on an ordinary trading-day boundary, while the later suspension
    # contains no missing dates. Recover the share multiplier only when the price break is
    # followed within a few rows by a multi-day, business-date-dense, near-perfect plateau
    # that is bounded by prices continuing on the same post-action scale.
    for position in range(1, len(index)):
        ratio_value = float(resolved_splits.iloc[position])
        if ratio_value > 0.0 and not np.isclose(ratio_value, 1.0):
            continue

        raw_gross = float(close_gross.iloc[position])
        total_gross = float(adjusted_gross.iloc[position])
        if not _matching_price_scale(raw_gross, total_gross):
            continue

        ratio = _best_simple_ratio(1.0 / raw_gross, exact=False)
        if ratio is None or not _materially_improves(raw_gross, ratio):
            continue
        if abs(math.log(raw_gross * ratio)) > _local_return_limit(close_gross, position):
            continue
        if not _has_forward_synthetic_suspension(
            index=index,
            close=native_close,
            adjusted=native_adjusted,
            position=position,
        ):
            continue
        resolved_splits.iloc[position] = ratio

    # Some exchanges suspend a security while units are replaced. If the upstream feed
    # omits both the event and the adjustment, the resumption row contains the scale change
    # in both Close and Adj Close. Calendar weekends are not evidence of suspension, so this
    # fallback requires at least three missing weekdays in addition to price agreement and a
    # simple share-count ratio.
    for position in range(1, len(index)):
        ratio_value = float(resolved_splits.iloc[position])
        if ratio_value > 0.0 and not np.isclose(ratio_value, 1.0):
            continue
        if _missing_business_days(index[position - 1], index[position]) < (
            _MIN_MISSING_BUSINESS_DAYS
        ):
            continue

        previous_close = float(native_close.iloc[position - 1])
        distribution = float(cash_distributions.iloc[position])
        if previous_close > 0.0 and distribution / previous_close > 0.05:
            continue

        raw_gross = float(close_gross.iloc[position])
        total_gross = float(adjusted_gross.iloc[position])
        if not _matching_price_scale(raw_gross, total_gross):
            continue

        ratio = _best_simple_ratio(1.0 / raw_gross, exact=False)
        if ratio is None or not _materially_improves(raw_gross, ratio):
            continue
        if abs(math.log(raw_gross * ratio)) > _local_return_limit(close_gross, position):
            continue
        resolved_splits.iloc[position] = ratio

    distribution_multipliers = pd.Series(1.0, index=index, dtype=float)
    corrections = pd.Series(False, index=index, dtype=bool)
    for position in range(1, len(index)):
        ratio = float(resolved_splits.iloc[position])
        if not np.isfinite(ratio) or ratio <= 0.0 or np.isclose(ratio, 1.0):
            continue
        close_changed = _apply_ratio(
            close_gross,
            position,
            ratio,
            trusted=bool(trusted.iloc[position]),
        )
        if close_changed:
            # Previous close was per pre-action unit while distributions are per current
            # unit. One previous unit owns `ratio` current units after the action.
            distribution_multipliers.iloc[position] = ratio
        adjusted_changed = _apply_ratio(
            adjusted_gross,
            position,
            ratio,
            trusted=bool(trusted.iloc[position]),
        )
        corrections.iloc[position] = close_changed or adjusted_changed

    return CorporateActionReconciliation(
        close_gross=close_gross,
        adjusted_gross=adjusted_gross,
        splits=resolved_splits,
        distribution_multipliers=distribution_multipliers,
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


def _missing_business_days(previous: pd.Timestamp, current: pd.Timestamp) -> int:
    start = (previous.normalize() + pd.Timedelta(days=1)).date()
    end = current.normalize().date()
    return int(np.busday_count(start, end))


def _matching_price_scale(close_gross: float, adjusted_gross: float) -> bool:
    if not _valid_gross(close_gross) or not _valid_gross(adjusted_gross):
        return False
    return abs(math.log(close_gross) - math.log(adjusted_gross)) <= math.log(1.05)


def _has_forward_synthetic_suspension(
    *,
    index: pd.DatetimeIndex,
    close: pd.Series,
    adjusted: pd.Series,
    position: int,
) -> bool:
    latest_start = min(
        len(index) - _MIN_SYNTHETIC_SUSPENSION_ROWS,
        position + _MAX_ROWS_BEFORE_SYNTHETIC_SUSPENSION,
    )
    for run_start in range(position, latest_start + 1):
        run_end = run_start
        while run_end + 1 < len(index) and _same_quote(
            close.iloc[run_end],
            adjusted.iloc[run_end],
            close.iloc[run_end + 1],
            adjusted.iloc[run_end + 1],
        ):
            run_end += 1

        if run_end - run_start + 1 < _MIN_SYNTHETIC_SUSPENSION_ROWS:
            continue
        if not _business_date_dense(index[run_start : run_end + 1]):
            continue

        # The plateau must begin at the same post-action quote reached by the immediately
        # preceding row; otherwise an unrelated later flat market could be mis-associated.
        if run_start > position and not _same_quote(
            close.iloc[run_start - 1],
            adjusted.iloc[run_start - 1],
            close.iloc[run_start],
            adjusted.iloc[run_start],
        ):
            continue

        # A bounded plateau is materially stronger evidence than an illiquid tail with no
        # later quote. The first following quote must remain on the same price scale.
        next_position = run_end + 1
        if next_position >= len(index):
            continue
        next_close_gross = float(close.iloc[next_position] / close.iloc[run_end])
        next_adjusted_gross = float(adjusted.iloc[next_position] / adjusted.iloc[run_end])
        if not _matching_price_scale(next_close_gross, next_adjusted_gross):
            continue
        if abs(math.log(next_close_gross)) > _POST_SUSPENSION_RETURN_LIMIT:
            continue
        return True
    return False


def _same_quote(
    first_close: float,
    first_adjusted: float,
    second_close: float,
    second_adjusted: float,
) -> bool:
    values = (first_close, first_adjusted, second_close, second_adjusted)
    if not all(_valid_gross(float(value)) for value in values):
        return False
    close_change = abs(math.log(float(second_close) / float(first_close)))
    adjusted_change = abs(math.log(float(second_adjusted) / float(first_adjusted)))
    return (
        close_change <= _SYNTHETIC_SUSPENSION_PRICE_TOLERANCE
        and adjusted_change <= _SYNTHETIC_SUSPENSION_PRICE_TOLERANCE
    )


def _business_date_dense(index: pd.DatetimeIndex) -> bool:
    if len(index) < _MIN_SYNTHETIC_SUSPENSION_ROWS:
        return False
    expected = pd.bdate_range(index[0].normalize(), index[-1].normalize())
    return len(expected) == len(index) and index.equals(pd.DatetimeIndex(expected))


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
