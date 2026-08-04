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
async def test_zero_config_mode_rejects_requests_without_browser_origin() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(api_key=None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/auth/check")
    assert response.status_code == 403
    assert response.json()["detail"] == "Browser origin is not allowed"


@pytest.mark.asyncio
async def test_zero_config_mode_accepts_configured_browser_origin() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(api_key=None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/check",
            headers={"Origin": "https://chihung1024.github.io"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://chihung1024.github.io"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_zero_config_mode_rejects_unconfigured_browser_origin() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(api_key=None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/check",
            headers={"Origin": "https://example.com"},
        )
    assert response.status_code == 403


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
    assert body["results"][0]["display_name"] == "Global · VT 100%"
    assert body["results"][0]["target_allocation"] == {"VT": 1.0}
    assert body["benchmark"]["name"] == "Benchmark · VT"
    assert body["benchmark"]["display_name"] == "Benchmark · VT"
    assert body["assets"][0]["symbol"] == "VT"
    assert body["assets"][0]["split_events"] == 0
    assert body["assets"][0]["capital_gain_events"] == 0
    assert body["results"][0]["metrics"]["final_balance"] > 0
    assert len(body["results"][0]["series"]) == 4


@pytest.mark.asyncio
async def test_retirement_mode_returns_gone_for_every_legacy_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORCE_LEGACY_RETIREMENT", "1")
    requests = [
        ("GET", "/", None),
        ("GET", "/health", None),
        ("GET", "/api/v1/auth/check", None),
        ("GET", "/api/v1/assets/search?q=VT&limit=5", None),
        ("POST", "/api/v1/backtests", {}),
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        responses = [
            await client.request(method, path, json=payload)
            for method, path, payload in requests
        ]

    for response in responses:
        assert response.status_code == 410
        assert response.json()["status"] == "retired"
        assert response.json()["code"] == "legacy_project_retired"
        assert response.json()["replacement_url"] == (
            "https://backteststock.chired.workers.dev/portfolio/"
        )
        assert response.headers["location"] == (
            "https://backteststock.chired.workers.dev/portfolio/"
        )
        assert response.headers["cache-control"] == "no-store"
