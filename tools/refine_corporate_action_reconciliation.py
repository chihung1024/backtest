from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}: {old[:100]!r}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


CORPORATE_ACTIONS = r'''from __future__ import annotations

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

    The resolver uses three independent representations of the same economic path:

    1. explicit split events supplied by the market-data source;
    2. discontinuities in the adjusted-to-unadjusted price factor, after removing the
       exact cash-distribution adjustment; and
    3. a conservative suspension-boundary fallback for feeds where both the split event
       and adjusted-price correction are missing.

    A ratio is applied only when it removes a price-unit discontinuity. Genuine large
    returns on ordinary consecutive trading days remain untouched. The returned
    distribution multiplier records whether the prior close was expressed in pre-action
    units, so cash paid per current unit is converted to the same economic basis exactly.
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
'''


TESTS = r'''from __future__ import annotations

import pandas as pd
import pytest

from app.data.corporate_actions import reconcile_corporate_actions


def test_explicit_split_repairs_only_the_unadjusted_scale() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 26.0, 27.0], index=index),
        adjusted=pd.Series([100.0, 104.0, 108.0], index=index),
        splits=pd.Series([0.0, 4.0, 0.0], index=index),
    )

    assert result.close_gross.iloc[1] == pytest.approx(1.04)
    assert result.adjusted_gross.iloc[1] == pytest.approx(1.04)
    assert result.distribution_multipliers.iloc[1] == pytest.approx(4.0)
    assert result.corrections.iloc[1]


def test_already_adjusted_close_does_not_rescale_distributions() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 102.0, 104.0], index=index),
        adjusted=pd.Series([100.0, 102.0, 104.0], index=index),
        splits=pd.Series([0.0, 4.0, 0.0], index=index),
    )

    assert result.close_gross.iloc[1] == pytest.approx(1.02)
    assert result.distribution_multipliers.iloc[1] == pytest.approx(1.0)


def test_adjustment_factor_recovers_an_omitted_split_event() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 26.0, 27.0], index=index),
        adjusted=pd.Series([100.0, 104.0, 108.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.iloc[1] == pytest.approx(4.0)
    assert result.close_gross.iloc[1] == pytest.approx(1.04)
    assert result.adjusted_gross.iloc[1] == pytest.approx(1.04)
    assert result.distribution_multipliers.iloc[1] == pytest.approx(4.0)


def test_suspension_boundary_recovers_when_both_price_series_are_unadjusted() -> None:
    index = pd.DatetimeIndex(
        ["2025-11-17", "2025-11-18", "2025-11-26", "2025-11-27"]
    )
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 102.0, 14.7, 15.0], index=index),
        adjusted=pd.Series([100.0, 102.0, 14.7, 15.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.iloc[2] == pytest.approx(7.0)
    assert result.close_gross.iloc[2] == pytest.approx(14.7 / 102.0 * 7.0)
    assert result.adjusted_gross.iloc[2] == pytest.approx(14.7 / 102.0 * 7.0)


def test_weekend_or_short_holiday_is_not_treated_as_a_suspension() -> None:
    index = pd.DatetimeIndex(["2020-01-03", "2020-01-07", "2020-01-08"])
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 50.0, 52.0], index=index),
        adjusted=pd.Series([100.0, 50.0, 52.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.close_gross.iloc[1] == pytest.approx(0.5)


def test_suspension_boundary_supports_reverse_splits() -> None:
    index = pd.DatetimeIndex(
        ["2020-01-01", "2020-01-02", "2020-01-10", "2020-01-13"]
    )
    result = reconcile_corporate_actions(
        close=pd.Series([10.0, 10.2, 82.0, 84.0], index=index),
        adjusted=pd.Series([10.0, 10.2, 82.0, 84.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.iloc[2] == pytest.approx(0.125)
    assert result.close_gross.iloc[2] == pytest.approx(82.0 / 10.2 * 0.125)


def test_genuine_large_return_on_consecutive_trading_days_is_preserved() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 50.0, 52.0], index=index),
        adjusted=pd.Series([100.0, 50.0, 52.0], index=index),
        splits=pd.Series(0.0, index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.close_gross.iloc[1] == pytest.approx(0.5)
    assert not result.corrections.any()


def test_cash_distribution_is_removed_before_split_factor_inference() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    result = reconcile_corporate_actions(
        close=pd.Series([100.0, 40.0, 42.0], index=index),
        adjusted=pd.Series([100.0, 110.0, 115.5], index=index),
        splits=pd.Series(0.0, index=index),
        distributions=pd.Series([0.0, 70.0, 0.0], index=index),
    )

    assert result.splits.eq(0.0).all()
    assert result.adjusted_gross.iloc[1] == pytest.approx(1.10)
'''


def main() -> None:
    (ROOT / "backend/app/data/corporate_actions.py").write_text(
        CORPORATE_ACTIONS, encoding="utf-8"
    )
    (ROOT / "backend/tests/test_corporate_actions.py").write_text(TESTS, encoding="utf-8")

    replace_once(
        "backend/app/data/yfinance_provider.py",
        "_FX_LOOKBACK_DAYS = 10\n_SPLIT_UNDERLYING_TOLERANCE = np.log(1.25)\n_SPLIT_MINIMUM_IMPROVEMENT = np.log(1.10)\n",
        "_FX_LOOKBACK_DAYS = 10\n",
    )
    replace_once(
        "backend/app/data/yfinance_provider.py",
        '''    splits = reconciliation.splits\n    split_fixes = reconciliation.corrections\n    distribution_returns = (distributions / close.shift(1)).replace(\n''',
        '''    splits = reconciliation.splits\n    split_fixes = reconciliation.corrections\n    distribution_returns = (\n        distributions * reconciliation.distribution_multipliers / close.shift(1)\n    ).replace(\n''',
    )
    replace_once(
        "backend/app/data/yfinance_provider.py",
        '''\ndef _correct_residual_splits(\n    gross_returns: pd.Series, splits: pd.Series\n) -> tuple[pd.Series, pd.Series]:\n    """Conservatively repair an unmistakable unadjusted split transition."""\n    corrected = gross_returns.astype(float).copy()\n    changed = pd.Series(False, index=corrected.index, dtype=bool)\n    for timestamp, ratio_value in splits.items():\n        ratio = float(ratio_value)\n        gross = float(corrected.get(timestamp, np.nan))\n        if (\n            not np.isfinite(ratio)\n            or ratio <= 0.0\n            or np.isclose(ratio, 1.0)\n            or not np.isfinite(gross)\n            or gross <= 0.0\n        ):\n            continue\n        candidate = gross * ratio\n        if candidate <= 0.0 or not np.isfinite(candidate):\n            continue\n        raw_distance = abs(np.log(gross))\n        candidate_distance = abs(np.log(candidate))\n        if (\n            candidate_distance <= _SPLIT_UNDERLYING_TOLERANCE\n            and raw_distance - candidate_distance >= _SPLIT_MINIMUM_IMPROVEMENT\n        ):\n            corrected.loc[timestamp] = candidate\n            changed.loc[timestamp] = True\n    return corrected, changed\n\n''',
        "\n",
    )

    replace_once(
        "backend/tests/test_yfinance_provider.py",
        '''def test_close_and_distribution_reconstruct_total_return_when_adjusted_is_missing() -> None:\n''',
        '''def test_split_day_distribution_uses_post_action_share_count() -> None:\n    frame = _frame(\n        close=[100.0, 26.0],\n        adjusted=[100.0, 108.0],\n        dividends=[0.0, 1.0],\n        splits=[0.0, 4.0],\n    )\n\n    result = _history_from_frame(\n        "CASH", frame, frame.index[0].date(), frame.index[-1].date(), currency="USD"\n    )\n\n    assert result is not None\n    assert result.price_returns.iloc[1] == pytest.approx(0.04)\n    assert result.dividend_returns.iloc[1] == pytest.approx(0.04)\n    assert result.total_returns.iloc[1] == pytest.approx(0.08)\n\n\ndef test_close_and_distribution_reconstruct_total_return_when_adjusted_is_missing() -> None:\n''',
    )

    replace_once(
        "backend/pyproject.toml",
        '  "yfinance>=1.2,<2",\n',
        '  "yfinance==1.5.1",\n',
    )

    replace_once(
        "docs/METHODOLOGY.md",
        '''  只有能消除價格尺度斷層的比例才會套用；一般連續交易日的真實大幅漲跌不會被改寫。\n  已完成的調和只記錄於資產稽核欄位，不會以錯誤或中斷方式呈現。\n''',
        '''  只有能消除價格尺度斷層的比例才會套用；一般連續交易日的真實大幅漲跌不會被改寫。\n  若前一收盤仍以企業行動前單位表示，現金配發會同步乘上單位數變動倍率，確保價格報酬、\n  配發收益與總報酬使用同一持有基礎。已完成的調和只記錄於資產稽核欄位，不會以錯誤或\n  中斷方式呈現。\n''',
    )


if __name__ == "__main__":
    main()
