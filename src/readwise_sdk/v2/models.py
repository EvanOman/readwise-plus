"""Pydantic models for Readwise API v2.

Re-exports the canonical model definitions from
``readwise_sdk.models.readwise`` for backward compatibility. This module is
identity-preserving: every name below is the *same object* as its
counterpart in ``readwise_sdk.models.readwise``, not a copy.
"""

from __future__ import annotations

from readwise_sdk.models.readwise import (
    Book,
    BookCategory,
    DailyReview,
    ExportBook,
    Highlight,
    HighlightColor,
    HighlightCreate,
    HighlightUpdate,
    Tag,
)

__all__ = [
    "Book",
    "BookCategory",
    "DailyReview",
    "ExportBook",
    "Highlight",
    "HighlightColor",
    "HighlightCreate",
    "HighlightUpdate",
    "Tag",
]
