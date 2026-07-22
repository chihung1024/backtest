from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.models import BacktestRequest, PortfolioDefinition


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
        BacktestRequest.model_validate(
            {
                "portfolios": [
                    {"name": "One", "assets": [{"symbol": "VTI", "weight": 100}]}
                ],
                "start_date": date(2020, 1, 1),
                "end_date": date(2099, 1, 1),
            }
        )
