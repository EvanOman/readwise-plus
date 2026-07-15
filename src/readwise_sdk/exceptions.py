"""Compatibility re-exports for the canonical Readwise SDK errors."""

from readwise_sdk.errors import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ReadwiseError,
    ServerError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ReadwiseError",
    "ServerError",
    "ValidationError",
]
