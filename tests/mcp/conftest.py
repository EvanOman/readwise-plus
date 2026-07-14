"""Shared fixtures for readwise-mcp tests."""

from __future__ import annotations

import os

import pytest

# Capture the real API key at import time, before any monkeypatching.
_REAL_API_KEY: str = ""
_env_key = os.environ.get("READWISE_API_KEY", "")
if _env_key:
    _REAL_API_KEY = _env_key
else:
    _env_file = os.path.expanduser("~/.env")
    if os.path.isfile(_env_file):
        with open(_env_file) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line.startswith("READWISE_API_KEY="):
                    _REAL_API_KEY = _line.split("=", 1)[1].strip().strip("'\"")
                    break


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from leaking env vars or touching the real API."""
    monkeypatch.setenv("READWISE_API_KEY", "test-key-000")


@pytest.fixture()
def api_key_from_env() -> str:
    """Return the real API key for live tests, captured before monkeypatch."""
    if not _REAL_API_KEY:
        pytest.skip("READWISE_API_KEY not available for live tests")
    return _REAL_API_KEY


@pytest.fixture()
def _use_real_api_key(api_key_from_env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override the isolated env with the real API key for live tests."""
    monkeypatch.setenv("READWISE_API_KEY", api_key_from_env)
