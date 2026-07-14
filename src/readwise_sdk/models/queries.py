"""Validated inputs for the canonical operations layer."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from readwise_sdk.v2.models import BookCategory
from readwise_sdk.v3.models import DocumentCategory, DocumentLocation


def _normalize_optional_text(value: str | None) -> str | None:
    """Strip an optional text filter and discard whitespace-only values."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class OperationInput(BaseModel):
    """Base configuration shared by immutable operation inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentSearch(OperationInput):
    """Input for filtering and searching Reader documents."""

    location: DocumentLocation | None = None
    category: DocumentCategory | None = None
    updated_after: datetime | None = None
    tags: tuple[str, ...] = ()
    query: str | None = None
    limit: int = 20

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Strip tag names, remove blanks, and preserve unique input order."""
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in value:
            stripped = tag.strip()
            if stripped and stripped not in seen:
                normalized.append(stripped)
                seen.add(stripped)
        return tuple(normalized)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        """Normalize an optional local text query."""
        return _normalize_optional_text(value)

    @field_validator("limit")
    @classmethod
    def clamp_limit(cls, value: int) -> int:
        """Clamp document searches to the current adapter contract."""
        return min(max(value, 1), 100)


class HighlightSearch(OperationInput):
    """Input for filtering and searching Readwise highlights."""

    book_id: int | None = Field(default=None, gt=0)
    updated_after: datetime | None = None
    query: str | None = None
    limit: int = 50

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        """Normalize an optional local text query."""
        return _normalize_optional_text(value)

    @field_validator("limit")
    @classmethod
    def clamp_limit(cls, value: int) -> int:
        """Clamp highlight searches to the current adapter contract."""
        return min(max(value, 1), 200)


class BookSearch(OperationInput):
    """Input for filtering and searching Readwise books and sources."""

    category: BookCategory | None = None
    source: str | None = None
    updated_after: datetime | None = None
    query: str | None = None
    limit: int = 20

    @field_validator("source", "query")
    @classmethod
    def normalize_text_filter(cls, value: str | None) -> str | None:
        """Normalize optional source and local text filters."""
        return _normalize_optional_text(value)

    @field_validator("limit")
    @classmethod
    def clamp_limit(cls, value: int) -> int:
        """Clamp book searches to the current adapter contract."""
        return min(max(value, 1), 100)


__all__ = ["BookSearch", "DocumentSearch", "HighlightSearch"]
