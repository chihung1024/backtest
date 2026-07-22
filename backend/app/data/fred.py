from __future__ import annotations

from datetime import date

import httpx
import pandas as pd


class FredProvider:
    def __init__(self, api_key: str, timeout: float = 20.0) -> None:
        if not api_key:
            raise ValueError("A FRED API key is required")
        self.api_key = api_key
        self.timeout = timeout
        self._cache: dict[tuple[str, date | None, date | None], pd.Series] = {}

    def series(
        self,
        series_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.Series:
        cache_key = (series_id, start, end)
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start is not None:
            params["observation_start"] = start.isoformat()
        if end is not None:
            params["observation_end"] = end.isoformat()
        response = httpx.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        observations = response.json().get("observations", [])
        frame = pd.DataFrame(observations)
        if frame.empty:
            raise ValueError(f"FRED returned no observations for {series_id}")
        values = pd.to_numeric(frame["value"], errors="coerce")
        index = pd.to_datetime(frame["date"])
        result = pd.Series(values.to_numpy(), index=index, name=series_id).dropna()
        self._cache[cache_key] = result
        return result.copy()
