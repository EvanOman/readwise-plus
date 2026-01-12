"""Pytest configuration and fixtures."""

import os

import pytest


@pytest.fixture
def api_key() -> str:
    """Return a test API key."""
    return "test_api_key_12345"


@pytest.fixture
def mock_env_api_key(api_key: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Set the API key in environment variables."""
    monkeypatch.setenv("READWISE_API_KEY", api_key)
    return api_key


@pytest.fixture
def live_api_key() -> str | None:
    """Return the live API key from environment, or None if not set."""
    return os.environ.get("READWISE_API_KEY")
