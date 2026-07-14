"""Pydantic models for Readwise Reader API v3.

Re-exports the canonical model definitions from
``readwise_sdk.models.reader`` for backward compatibility. This module is
identity-preserving: every name below is the *same object* as its
counterpart in ``readwise_sdk.models.reader``, not a copy.
"""

from __future__ import annotations

from readwise_sdk.models.reader import (
    CreateDocumentResult,
    Document,
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentTag,
    DocumentUpdate,
)

__all__ = [
    "CreateDocumentResult",
    "Document",
    "DocumentCategory",
    "DocumentCreate",
    "DocumentLocation",
    "DocumentTag",
    "DocumentUpdate",
]
