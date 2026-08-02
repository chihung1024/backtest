from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import Settings, get_settings
from app.models import BacktestRequest, BacktestResponse, SearchResult
from app.service import BacktestService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
app = FastAPI(
    title="Portfolio Backtest API",
    version=__version__,
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Backtest-Key"],
    max_age=86400,
)


class MinuteRateLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.last_cleanup = time.monotonic()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        if now - self.last_cleanup > 60:
            stale = [
                client
                for client, timestamps in self.requests.items()
                if not timestamps or now - timestamps[-1] > 60
            ]
            for client in stale:
                self.requests.pop(client, None)
            self.last_cleanup = now
        window = self.requests[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.limit:
            return False
        window.append(now)
        return True


api_rate_limiter = MinuteRateLimiter(limit=20)
backtest_rate_limiter = MinuteRateLimiter(limit=4)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next: Any) -> Any:
    if request.url.path.startswith("/api/v1/"):
        forwarded = request.headers.get("x-forwarded-for", "")
        fallback = request.client.host if request.client else "unknown"
        client_key = forwarded.split(",")[0].strip() or fallback
        if not api_rate_limiter.allow(client_key):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again in one minute."},
            )
        if (
            request.method == "POST"
            and request.url.path == "/api/v1/backtests"
            and not backtest_rate_limiter.allow(client_key)
        ):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Backtest rate limit exceeded. Try again in one minute."},
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


SettingsDependency = Annotated[Settings, Depends(get_settings)]


def authorize(
    request: Request,
    current_settings: SettingsDependency,
    x_backtest_key: Annotated[str | None, Header()] = None,
) -> None:
    if current_settings.api_key:
        if x_backtest_key is None or not secrets.compare_digest(
            x_backtest_key, current_settings.api_key
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access key",
            )
        return

    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if origin not in current_settings.cors_origin_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser origin is not allowed",
        )


@lru_cache
def get_service() -> BacktestService:
    return BacktestService(get_settings())


ServiceDependency = Annotated[BacktestService, Depends(get_service)]


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "portfolio-backtest-api", "version": __version__}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
        "deployment_sha": os.getenv("VERCEL_GIT_COMMIT_SHA", ""),
    }


@app.get("/api/v1/auth/check", dependencies=[Depends(authorize)])
def auth_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/assets/search",
    response_model=list[SearchResult],
    dependencies=[Depends(authorize)],
)
async def search_assets(
    service: ServiceDependency,
    q: str,
    limit: int = 8,
) -> list[dict[str, str | None]]:
    if len(q.strip()) < 1:
        return []
    return await asyncio.to_thread(service.provider.search, q, min(max(limit, 1), 12))


@app.post(
    "/api/v1/backtests",
    response_model=BacktestResponse,
    dependencies=[Depends(authorize)],
)
async def run_backtest(
    payload: BacktestRequest,
    service: ServiceDependency,
) -> BacktestResponse:
    try:
        return await asyncio.to_thread(service.run, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
