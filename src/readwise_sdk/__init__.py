"""Comprehensive Python SDK for Readwise with high-level workflow abstractions."""

from readwise_sdk.client import AsyncReadwiseClient, ReadwiseClient
from readwise_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ReadwiseError,
    ServerError,
    ValidationError,
)
from readwise_sdk.v2 import (
    Book,
    BookCategory,
    DailyReview,
    Highlight,
    HighlightColor,
    Tag,
)

__version__ = "0.1.0"

__all__ = [
    # Clients
    "ReadwiseClient",
    "AsyncReadwiseClient",
    # Exceptions
    "ReadwiseError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
    # V2 Models
    "Book",
    "BookCategory",
    "Highlight",
    "HighlightColor",
    "Tag",
    "DailyReview",
]
