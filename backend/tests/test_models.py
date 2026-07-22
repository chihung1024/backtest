from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.models import BacktestRequest, OutputFrequency, PortfolioDefinition


def _minimal_request(**overrides: object) -> dict[str, object]:
    return {
        "portfolios": [{"name": "One", "assets": [{"symbol": "VTI", "weight": 100}]}],
        "start_date": date(2020, 1, 1),
        "end_date": date(2020, 12, 31),
        **overrides,
    }


def test_twd_and_daily_are_mandatory_defaults() -> None:
    request = BacktestRequest.model_validate(_minimal_request())

    assert request.base_currency == "TWD"
    assert request.output_frequency == OutputFrequency.DAILY


def test_non_twd_base_currency_is_rejected() -> None:
    with pytest.raises(ValidationError, match="TWD"):
        BacktestRequest.model_validate(_minimal_request(base_currency="USD"))


def test_weights_must_total_one_hundred() -> None:
    with pytest.raises(ValidationError, match="must total 100"):
        PortfolioDefinition.model_validate(
            {
                "name": "Invalid",
                "assets": [
                    {"symbol": "VTI", "weight": 60},
                    {"symbol": "BND", "weight": 30},
                ],
            }
        )


def test_duplicate_symbols_are_rejected() -> None:
    with pytest.raises(ValidationError, match="same ticker"):
        PortfolioDefinition.model_validate(
            {
                "name": "Duplicate",
                "assets": [
                    {"symbol": "VTI", "weight": 50},
                    {"symbol": "vti", "weight": 50},
                ],
            }
        )


def test_future_end_date_is_rejected() -> None:
    with pytest.raises(ValidationError, match="future"):
        BacktestRequest.model_validate(_minimal_request(end_date=date(2099, 1, 1)))


def test_request_accepts_five_portfolios_but_rejects_six() -> None:
    portfolio = {"name": "Model", "assets": [{"symbol": "VTI", "weight": 100}]}

    request = BacktestRequest.model_validate(_minimal_request(portfolios=[portfolio] * 5))
    assert len(request.portfolios) == 5

    with pytest.raises(ValidationError, match="at most 5"):
        BacktestRequest.model_validate(_minimal_request(portfolios=[portfolio] * 6))
