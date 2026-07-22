from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from conftest import history

from app.data.yfinance_provider import (
    _REPAIR_LOOKAHEAD_DAYS,
    _REPAIR_LOOKBACK_DAYS,
    YFinanceProvider,
    _history_from_frame,
    infer_currency,
    normalize_symbol,
)


def test_symbol_normalization_and_currency_inference() -> None:
    assert normalize_symbol(" 2330 ") == "2330.TW"
    assert normalize_symbol("0050.TW") == "0050.TW"
    assert normalize_symbol("BRK-B") == "BRK-B"
    assert infer_currency("2330.TW") == "TWD"
    assert infer_currency("VT") == "USD"


def test_currency_conversion_preserves_native_metadata_and_return_decomposition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = YFinanceProvider()
    asset = history(
        "VT",
        [0.0, 0.02],
        price_returns=[0.0, 0.0],
        dividend_returns=[0.0, 0.02],
        currency="USD",
    )
    asset.dividend_events = 1
    asset.split_events = 2
    fx = pd.Series([1.0, 1.01], index=asset.total_returns.index)
    monkeypatch.setattr(provider, "_download_fx_levels", lambda *args: fx)

    converted = provider._convert_currencies(
        {"VT": asset},
        "TWD",
        date(2020, 1, 1),
        date(2020, 1, 31),
    )["VT"]

    assert converted.currency == "USD"
    assert converted.total_returns.iloc[-1] == pytest.approx(0.0302)
    assert converted.price_returns.iloc[-1] == pytest.approx(0.01)
    assert converted.dividend_returns.iloc[-1] == pytest.approx(0.0202)
    assert converted.total_returns.iloc[-1] == pytest.approx(
        converted.price_returns.iloc[-1] + converted.dividend_returns.iloc[-1]
    )
    assert converted.dividend_events == 1
    assert converted.split_events == 2


def test_fx_levels_do_not_repeat_returns_across_calendar_gaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = YFinanceProvider()
    asset = history("VT", [0.0, 0.0, 0.0], currency="USD")
    fx = pd.Series(
        [1.0, 1.02],
        index=[asset.total_returns.index[0], asset.total_returns.index[2]],
    )
    monkeypatch.setattr(provider, "_download_fx_levels", lambda *args: fx)

    converted = provider._convert_currencies(
        {"VT": asset}, "TWD", date(2020, 1, 1), date(2020, 1, 31)
    )["VT"]

    assert converted.total_returns.tolist() == pytest.approx([0.0, 0.0, 0.02])


def test_adjusted_split_does_not_create_artificial_return() -> None:
    frame = _frame(
        close=[100.0, 102.0, 104.0],
        adjusted=[100.0, 102.0, 104.0],
        splits=[0.0, 4.0, 0.0],
    )

    result = _history_from_frame(
        "SPLT", frame, frame.index[0].date(), frame.index[-1].date(), currency="USD"
    )

    assert result is not None
    assert result.total_returns.iloc[1] == pytest.approx(0.02)
    assert result.split_events == 1
    assert result.split_corrections == 0


@pytest.mark.parametrize(
    ("close", "ratio", "expected"),
    [
        ([100.0, 26.0, 27.0], 4.0, 0.04),
        ([10.0, 82.0, 84.0], 0.125, 0.025),
    ],
)
def test_residual_forward_and_reverse_splits_are_repaired(
    close: list[float], ratio: float, expected: float
) -> None:
    frame = _frame(close=close, adjusted=close, splits=[0.0, ratio, 0.0])

    result = _history_from_frame(
        "SPLT", frame, frame.index[0].date(), frame.index[-1].date(), currency="USD"
    )

    assert result is not None
    assert result.total_returns.iloc[1] == pytest.approx(expected)
    assert result.price_returns.iloc[1] == pytest.approx(expected)
    assert result.split_corrections == 1


def test_cash_distributions_use_additive_decomposition_without_clipping() -> None:
    frame = _frame(
        close=[100.0, 40.0],
        adjusted=[100.0, 110.0],
        dividends=[0.0, 10.0],
        capital_gains=[0.0, 60.0],
    )

    result = _history_from_frame(
        "FUND", frame, frame.index[0].date(), frame.index[-1].date(), currency="USD"
    )

    assert result is not None
    assert result.total_returns.iloc[1] == pytest.approx(0.10)
    assert result.dividend_returns.iloc[1] == pytest.approx(0.70)
    assert result.price_returns.iloc[1] == pytest.approx(-0.60)
    assert result.total_returns.iloc[1] == pytest.approx(
        result.price_returns.iloc[1] + result.dividend_returns.iloc[1]
    )
    assert result.dividend_events == 1
    assert result.capital_gain_events == 1


def test_close_and_distribution_reconstruct_total_return_when_adjusted_is_missing() -> None:
    frame = _frame(close=[100.0, 99.0], dividends=[0.0, 2.0])
    frame = frame.drop(columns="Adj Close")

    result = _history_from_frame(
        "CASH", frame, frame.index[0].date(), frame.index[-1].date(), currency="USD"
    )

    assert result is not None
    assert result.price_returns.iloc[1] == pytest.approx(-0.01)
    assert result.dividend_returns.iloc[1] == pytest.approx(0.02)
    assert result.total_returns.iloc[1] == pytest.approx(0.01)


def test_action_only_row_is_applied_to_next_price_interval() -> None:
    frame = _frame(
        close=[100.0, np.nan, 99.0],
        adjusted=[100.0, np.nan, 101.0],
        dividends=[0.0, 2.0, 0.0],
    )

    result = _history_from_frame(
        "CASH", frame, frame.index[0].date(), frame.index[-1].date(), currency="USD"
    )

    assert result is not None
    assert result.dividends.iloc[-1] == pytest.approx(2.0)
    assert result.dividend_returns.iloc[-1] == pytest.approx(0.02)


def test_download_includes_context_for_yfinance_repairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    frame = _frame(close=[100.0, 101.0])

    def fake_download(**kwargs: object) -> pd.DataFrame:
        captured.update(kwargs)
        return frame

    monkeypatch.setattr("app.data.yfinance_provider.yf.download", fake_download)
    provider = YFinanceProvider()
    start = frame.index[0].date()
    end = frame.index[-1].date()

    result = provider._download_local(["TEST"], start, end)

    assert "TEST" in result
    assert captured["start"] == (start - timedelta(days=_REPAIR_LOOKBACK_DAYS)).isoformat()
    assert captured["end"] == (end + timedelta(days=_REPAIR_LOOKAHEAD_DAYS)).isoformat()
    assert captured["actions"] is True
    assert captured["repair"] is True
    assert captured["keepna"] is True


def _frame(
    *,
    close: list[float],
    adjusted: list[float] | None = None,
    dividends: list[float] | None = None,
    capital_gains: list[float] | None = None,
    splits: list[float] | None = None,
) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=len(close))
    return pd.DataFrame(
        {
            "Close": close,
            "Adj Close": adjusted if adjusted is not None else close,
            "Dividends": dividends or [0.0] * len(close),
            "Capital Gains": capital_gains or [0.0] * len(close),
            "Stock Splits": splits or [0.0] * len(close),
            "Repaired?": [False] * len(close),
        },
        index=index,
    )
