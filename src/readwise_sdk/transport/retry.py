"""Retry classification and delay calculation."""

from __future__ import annotations

import httpx

from readwise_sdk.errors import RateLimitError

RETRYABLE_NETWORK_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException)


def is_retryable_exception(error: BaseException) -> bool:
    """Return whether the current client retries ``error`` when attempts remain."""
    if isinstance(error, RETRYABLE_NETWORK_EXCEPTIONS):
        return True
    return isinstance(error, RateLimitError) and bool(error.retry_after)


def calculate_backoff(retry_backoff: float, attempt: int) -> float:
    """Calculate the existing exponential delay for a zero-based attempt."""
    return retry_backoff * (2**attempt)


def calculate_retry_delay(
    error: BaseException,
    retry_backoff: float,
    attempt: int,
) -> float | int | None:
    """Return the existing retry delay for ``error``, or ``None`` if not retried."""
    if isinstance(error, RETRYABLE_NETWORK_EXCEPTIONS):
        return calculate_backoff(retry_backoff, attempt)
    if isinstance(error, RateLimitError) and error.retry_after:
        return error.retry_after
    return None


__all__ = [
    "RETRYABLE_NETWORK_EXCEPTIONS",
    "calculate_backoff",
    "calculate_retry_delay",
    "is_retryable_exception",
]
