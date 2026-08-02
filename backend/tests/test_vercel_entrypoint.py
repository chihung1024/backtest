import os
from pathlib import Path

from fastapi import FastAPI

from index import app


def test_vercel_entrypoint_exports_the_production_app() -> None:
    assert isinstance(app, FastAPI)
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/v1/backtests" in paths
    assert "/api/v1/assets/search" in paths


def test_vercel_entrypoint_uses_writable_cache_paths() -> None:
    assert os.environ["HOME"] == "/tmp"
    assert os.environ["XDG_CACHE_HOME"] == "/tmp/.cache"
    assert Path(os.environ["XDG_CACHE_HOME"]).is_dir()
