from __future__ import annotations

from datetime import date

from conftest import history

from app.config import Settings
from app.data.base import AssetHistory
from app.service import BacktestService


class StubProvider:
    def histories(
        self, symbols: list[str], start: date, end: date, base_currency: str
    ) -> dict[str, AssetHistory]:
        return {symbol: history(symbol, [0.0, 0.01, -0.005, 0.002]) for symbol in symbols}

    def search(self, query: str, limit: int = 8) -> list[dict[str, str | None]]:
        return [{"symbol": "2330.TW", "name": "TSMC", "currency": "TWD"}]


class RecordingProvider(StubProvider):
    end_received: date | None = None

    def histories(
        self, symbols: list[str], start: date, end: date, base_currency: str
    ) -> dict[str, AssetHistory]:
        self.end_received = end
        return super().histories(symbols, start, end, base_currency)


class CorporateActionProvider(StubProvider):
    def histories(
        self, symbols: list[str], start: date, end: date, base_currency: str
    ) -> dict[str, AssetHistory]:
        values = super().histories(symbols, start, end, base_currency)
        for item in values.values():
            item.dividend_events = 4
            item.capital_gain_events = 1
            item.split_events = 2
            item.repaired_observations = 3
            item.split_corrections = 1
        return values


def test_service_normalizes_taiwan_ticker() -> None:
    from app.models import BacktestRequest

    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Taiwan", "assets": [{"symbol": "2330", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "base_currency": "TWD",
        }
    )
    service = BacktestService(Settings(), provider=StubProvider())
    response = service.run(request)
    assert response.assets[0].symbol == "2330.TW"
    assert any("Normalized 2330" in warning for warning in response.warnings)
    assert response.results[0].metrics["final_balance"] is not None


def test_service_excludes_incomplete_current_year_when_ytd_is_disabled() -> None:
    from app.models import BacktestRequest

    today = date.today()
    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Calendar years", "assets": [{"symbol": "VT", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": today,
            "include_ytd": False,
        }
    )
    provider = RecordingProvider()

    response = BacktestService(Settings(), provider=provider).run(request)

    assert provider.end_received == date(today.year - 1, 12, 31)
    assert any("Excluded the incomplete" in warning for warning in response.warnings)


def test_service_reports_corporate_action_audit_metadata() -> None:
    from app.models import BacktestRequest

    request = BacktestRequest.model_validate(
        {
            "portfolios": [
                {"name": "Audited", "assets": [{"symbol": "VT", "weight": 100}]}
            ],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        }
    )

    response = BacktestService(Settings(), provider=CorporateActionProvider()).run(request)
    metadata = response.assets[0]

    assert metadata.dividend_events == 4
    assert metadata.capital_gain_events == 1
    assert metadata.split_events == 2
    assert metadata.repaired_observations == 3
    assert metadata.split_corrections == 1
    assert any("yfinance repaired 3" in warning for warning in response.warnings)
    assert any("residual split" in warning for warning in response.warnings)
