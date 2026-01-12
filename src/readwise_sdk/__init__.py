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
from readwise_sdk.managers import (
    BookManager,
    DocumentManager,
    HighlightManager,
    SyncManager,
    SyncState,
)
from readwise_sdk.v2 import (
    Book,
    BookCategory,
    DailyReview,
    Highlight,
    HighlightColor,
    Tag,
)
from readwise_sdk.v3 import (
    Document,
    DocumentCategory,
    DocumentLocation,
    DocumentTag,
)
from readwise_sdk.workflows import (
    BackgroundPoller,
    DigestBuilder,
    DigestFormat,
    ReadingInbox,
    TagWorkflow,
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
    # V3 Models
    "Document",
    "DocumentCategory",
    "DocumentLocation",
    "DocumentTag",
    # Managers
    "HighlightManager",
    "BookManager",
    "DocumentManager",
    "SyncManager",
    "SyncState",
    # Workflows
    "DigestBuilder",
    "DigestFormat",
    "BackgroundPoller",
    "TagWorkflow",
    "ReadingInbox",
]
