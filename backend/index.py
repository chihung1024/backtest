"""Vercel ASGI entrypoint for the portfolio backtest API."""

import os
from pathlib import Path

_CACHE_ROOT = Path("/tmp/.cache")
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HOME", "/tmp")
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT))

from app.main import app  # noqa: E402

__all__ = ["app"]
