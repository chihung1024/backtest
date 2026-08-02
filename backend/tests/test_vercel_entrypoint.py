from fastapi import FastAPI

from index import app


def test_vercel_entrypoint_exports_the_production_app() -> None:
    assert isinstance(app, FastAPI)
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/v1/backtests" in paths
    assert "/api/v1/assets/search" in paths
