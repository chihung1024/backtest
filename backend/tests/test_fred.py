from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.data.fred import FredProvider


def test_fred_provider_filters_dates_and_caches_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []

    def fake_get(url: str, *, params: dict[str, str], timeout: float) -> httpx.Response:
        calls.append(params)
        return httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2020-01-01", "value": "100.0"},
                    {"date": "2020-02-01", "value": "."},
                    {"date": "2020-03-01", "value": "102.5"},
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = FredProvider("fred-test-key")

    first = provider.series("CPIAUCSL", date(2020, 1, 1), date(2020, 3, 31))
    first.iloc[0] = -1
    second = provider.series("CPIAUCSL", date(2020, 1, 1), date(2020, 3, 31))

    assert len(calls) == 1
    assert calls[0]["observation_start"] == "2020-01-01"
    assert calls[0]["observation_end"] == "2020-03-31"
    assert second.tolist() == [100.0, 102.5]


def test_fred_provider_rejects_empty_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={"observations": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(ValueError, match="no observations"):
        FredProvider("fred-test-key").series("EMPTY")
