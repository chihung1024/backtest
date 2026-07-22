from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from conftest import history

from app.data.yfinance_provider import YFinanceProvider, infer_currency, normalize_symbol


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
    fx = pd.Series([0.0, 0.01], index=asset.total_returns.index)
    monkeypatch.setattr(provider, "_download_fx", lambda *args: fx)

    converted = provider._convert_currencies(
        {"VT": asset},
        "TWD",
        date(2020, 1, 1),
        date(2020, 1, 31),
    )["VT"]

    assert converted.currency == "USD"
    assert converted.total_returns.iloc[-1] == pytest.approx(0.0302)
    assert converted.price_returns.iloc[-1] == pytest.approx(0.01)
    assert converted.dividend_returns.iloc[-1] == pytest.approx(0.02)
