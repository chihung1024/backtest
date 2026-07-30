from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.data.yfinance_provider import YFinanceProvider


def _corrupt_direct_frame() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2011-10-24", "2011-10-25", "2011-10-26"])
    return pd.DataFrame(
        {
            "Open": [30.22, 30.07, 30.09],
            "High": [30.22, 30.08, 30.13],
            "Low": [29.387, 29.387, 29.40],
            "Close": [29.254, 1.8015, 30.11],
        },
        index=index,
    )


def test_fx_download_repairs_an_impossible_close_inside_the_data_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _corrupt_direct_frame()
    monkeypatch.setattr(
        "app.data.yfinance_provider.yf.download",
        lambda *args, **kwargs: frame.copy(),
    )

    levels = YFinanceProvider()._download_fx_levels(
        "USD", "TWD", date(2011, 10, 24), date(2011, 10, 26)
    )

    repaired = levels.loc[pd.Timestamp("2011-10-25")]
    assert 29.387 <= repaired <= 30.08
    assert levels.pct_change(fill_method=None).abs().max() < 0.10


def test_fx_download_prefers_the_cleanest_normalized_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"])
    clean = pd.DataFrame(
        {
            "Open": [30.0, 30.1, 30.2],
            "High": [30.1, 30.2, 30.3],
            "Low": [29.9, 30.0, 30.1],
            "Close": [30.0, 30.1, 30.2],
        },
        index=index,
    )

    def fake_download(ticker: str, **kwargs: object) -> pd.DataFrame:
        if ticker == "TWD=X":
            return _corrupt_direct_frame()
        return clean.copy()

    monkeypatch.setattr("app.data.yfinance_provider.yf.download", fake_download)

    levels = YFinanceProvider()._download_fx_levels(
        "USD", "TWD", date(2020, 1, 2), date(2020, 1, 6)
    )

    assert levels.equals(clean["Close"].astype(float))


def test_fx_download_normalizes_inverse_ohlc_before_inversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"])
    inverse = pd.DataFrame(
        {
            "Open": [1 / 30.0, 1 / 30.1, 1 / 30.2],
            "High": [1 / 29.9, 1 / 30.0, 1 / 30.1],
            "Low": [1 / 30.1, 1 / 30.2, 1 / 30.3],
            "Close": [1 / 30.0, 1 / 30.1, 1 / 30.2],
        },
        index=index,
    )

    def fake_download(ticker: str, **kwargs: object) -> pd.DataFrame:
        if ticker != "TWDUSD=X":
            return pd.DataFrame()
        return inverse.copy()

    monkeypatch.setattr("app.data.yfinance_provider.yf.download", fake_download)

    levels = YFinanceProvider()._download_fx_levels(
        "USD", "TWD", date(2020, 1, 2), date(2020, 1, 6)
    )

    assert levels.tolist() == pytest.approx([30.0, 30.1, 30.2])


def test_fx_download_does_not_rewrite_a_valid_large_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"])
    frame = pd.DataFrame(
        {
            "Open": [30.0, 16.0, 17.0],
            "High": [30.2, 18.0, 18.0],
            "Low": [29.8, 14.0, 16.0],
            "Close": [30.0, 15.0, 17.0],
        },
        index=index,
    )
    monkeypatch.setattr(
        "app.data.yfinance_provider.yf.download",
        lambda *args, **kwargs: frame.copy(),
    )

    levels = YFinanceProvider()._download_fx_levels(
        "USD", "TWD", date(2020, 1, 2), date(2020, 1, 6)
    )

    assert levels.iloc[1] == pytest.approx(15.0)
