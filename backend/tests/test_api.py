from __future__ import annotations

from datetime import date

import pytest
from conftest import history
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.data.base import AssetHistory
from app.main import app, get_service
from app.service import BacktestService


class ApiStubProvider:
    def histories(
        self, symbols: list[str], start: date, end: date, base_currency: str
    ) -> dict[str, AssetHistory]:
        return {symbol: history(symbol, [0.0, 0.01, -0.005, 0.002]) for symbol in symbols}

    def search(self, query: str, limit: int = 8) -> list[dict[str, str | None]]:
        return [
            {
                "symbol": "VT",
                "name": "Vanguard Total World Stock ETF",
                "exchange": "NYSE Arca",
                "quote_type": "ETF",
                "currency": "USD",
            }
        ]


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_backtest_endpoint_requires_configured_access_key() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(api_key="test-secret")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/backtests", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_check_verifies_access_key() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(api_key="test-secret")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        denied = await client.get("/api/v1/auth/check")
        allowed = await client.get(
            "/api/v1/auth/check",
            headers={"X-Backtest-Key": "test-secret"},
        )
    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_backtest_endpoint_returns_calculated_response() -> None:
    settings = Settings(api_key="test-secret")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_service] = lambda: BacktestService(
        settings,
        provider=ApiStubProvider(),
    )
    payload = {
        "portfolios": [
            {"name": "Global", "assets": [{"symbol": "VT", "weight": 100}]}
        ],
        "benchmark": "VT",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "base_currency": "TWD",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/backtests",
            json=payload,
            headers={"X-Backtest-Key": "test-secret"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["base_currency"] == "TWD"
    assert body["results"][0]["name"] == "Global"
    assert body["benchmark"]["name"] == "Benchmark · VT"
    assert body["assets"][0]["symbol"] == "VT"
    assert body["assets"][0]["split_events"] == 0
    assert body["assets"][0]["capital_gain_events"] == 0
    assert body["results"][0]["metrics"]["final_balance"] > 0
    assert len(body["results"][0]["series"]) == 4
