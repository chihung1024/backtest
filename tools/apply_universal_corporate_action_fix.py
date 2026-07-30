from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}: {old[:80]!r}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


CORPORATE_ACTIONS = r'''from __future__ import annotations

from dataclasses import dataclass
import math

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
    assert result.corrections.iloc[1]


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
        "from app.data.base import AssetHistory\n",
        "from app.data.base import AssetHistory\n"
        "from app.data.corporate_actions import reconcile_corporate_actions\n",
    )
    replace_once(
        "backend/app/data/yfinance_provider.py",
        '''    close_gross, close_split_fixes = _correct_residual_splits(close / close.shift(1), splits)\n    adjusted_gross, adjusted_split_fixes = _correct_residual_splits(\n        adjusted / adjusted.shift(1), splits\n    )\n    distribution_returns = (distributions / close.shift(1)).replace(\n''',
        '''    reconciliation = reconcile_corporate_actions(\n        close=close,\n        adjusted=adjusted,\n        splits=splits,\n        distributions=distributions,\n    )\n    close_gross = reconciliation.close_gross\n    adjusted_gross = reconciliation.adjusted_gross\n    splits = reconciliation.splits\n    split_fixes = reconciliation.corrections\n    distribution_returns = (distributions / close.shift(1)).replace(\n''',
    )
    replace_once(
        "backend/app/data/yfinance_provider.py",
        '''    split_corrections = int(\n        (close_split_fixes | adjusted_split_fixes)\n        .reindex(window_index, fill_value=False)\n        .sum()\n    )\n''',
        '''    split_corrections = int(\n        split_fixes.reindex(window_index, fill_value=False).sum()\n    )\n''',
    )

    replace_once(
        "backend/app/service.py",
        '''        warnings = list(normalization_warnings)\n        for symbol, history in histories.items():\n            if history.repaired_observations:\n                warnings.append(\n                    f"{symbol}: yfinance repaired {history.repaired_observations} "\n                    "price observation(s) before the backtest"\n                )\n            if history.split_corrections:\n                warnings.append(\n                    f"{symbol}: corrected {history.split_corrections} residual "\n                    "split transition(s) before calculating returns"\n                )\n        aligned = align_histories(histories, request.symbols)\n''',
        '''        # Successful market-data reconciliation is audit metadata, not a user-facing\n        # error condition. Results continue normally after deterministic repair.\n        warnings = list(normalization_warnings)\n        aligned = align_histories(histories, request.symbols)\n''',
    )
    replace_once(
        "backend/tests/test_service.py",
        '''    assert any("yfinance repaired 3" in warning for warning in response.warnings)\n    assert any("residual split" in warning for warning in response.warnings)\n''',
        '''    assert response.warnings == []\n''',
    )

    replace_once(
        "docs/METHODOLOGY.md",
        '''- 引擎以資產價值而非股數運算，拆股與反向拆股本身不產生損益。Yahoo 修復後若仍\n  出現與明確拆股比例相符的殘留價格跳變，僅在校正後單日變動落在保守範圍內才修正，\n  並在 API warning 與資產稽核欄位標示。\n''',
        '''- 引擎以資產價值而非股數運算，拆股與反向拆股本身不產生損益。企業行動會以\n  「明確事件、調整價／未調整價因子、停牌後恢復交易的簡單比例」三層訊號統一調和。\n  只有能消除價格尺度斷層的比例才會套用；一般連續交易日的真實大幅漲跌不會被改寫。\n  已完成的調和只記錄於資產稽核欄位，不會以錯誤或中斷方式呈現。\n''',
    )
    replace_once(
        "docs/API.md",
        '''若 `repaired_observations` 或 `split_corrections` 大於零，`warnings` 也會留下可見提醒。\n''',
        '''這些欄位屬於資料處理稽核；已自動完成的修復不會被呈現為錯誤，也不會中斷回測。\n''',
    )

    replace_once(
        "backend/app/__init__.py",
        '__version__ = "0.6.4"',
        '__version__ = "0.6.5"',
    )
    replace_once(
        "backend/pyproject.toml",
        'version = "0.6.4"',
        'version = "0.6.5"',
    )
    replace_once(
        "frontend/package.json",
        '"version": "0.6.4"',
        '"version": "0.6.5"',
    )
    package_lock = ROOT / "frontend/package-lock.json"
    lock_content = package_lock.read_text(encoding="utf-8")
    matches = lock_content.count('"version": "0.6.4"')
    if matches != 2:
        raise RuntimeError(f"Expected two package-lock version matches, found {matches}")
    package_lock.write_text(
        lock_content.replace('"version": "0.6.4"', '"version": "0.6.5"'),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
