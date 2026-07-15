"""Canonical client configuration for the Readwise SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib.metadata import version

READWISE_API_V2_BASE = "https://readwise.io/api/v2"
READWISE_API_V3_BASE = "https://readwise.io/api/v3"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 0.5
DEFAULT_USER_AGENT = f"readwise-plus/{version('readwise-plus')}"


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Immutable settings shared by synchronous and asynchronous clients."""

    api_key: str | None = None
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff: float = DEFAULT_RETRY_BACKOFF
    user_agent: str = DEFAULT_USER_AGENT
    v2_base_url: str = READWISE_API_V2_BASE
    v3_base_url: str = READWISE_API_V3_BASE


def resolve_api_key(api_key: str | None) -> str | None:
    """Resolve an explicit API key with the existing environment fallback."""
    return api_key or os.environ.get("READWISE_API_KEY")


__all__ = [
    "ClientConfig",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_BACKOFF",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "READWISE_API_V2_BASE",
    "READWISE_API_V3_BASE",
]
