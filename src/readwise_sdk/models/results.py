"""Shared semantic projections and declared operation results."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from readwise_sdk.v2.models import Book, BookCategory, Highlight, HighlightColor
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation


class SummaryModel(BaseModel):
    """Base configuration for immutable semantic read projections."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentSummary(SummaryModel):
    """Document fields shared by current CLI and MCP list projections."""

    id: str
    title: str | None = None
    author: str | None = None
    url: str
    category: DocumentCategory | None = None
    location: DocumentLocation | None = None
    tags: tuple[str, ...] = ()
    word_count: int | None = None
    reading_progress: float | None = None
    site_name: str | None = None
    published_date: datetime | None = None
    saved_at: datetime | None = None


class HighlightSummary(SummaryModel):
    """Highlight fields shared by current CLI and MCP list projections."""

    id: int
    text: str
    note: str | None = None
    book_id: int | None = None
    color: HighlightColor | None = None
    location: int | None = None
    highlighted_at: datetime | None = None
    tags: tuple[str, ...] = ()


class BookSummary(SummaryModel):
    """Book fields shared by current CLI and MCP list projections."""

    id: int
    title: str
    author: str | None = None
    category: BookCategory | None = None
    source: str | None = None
    num_highlights: int = 0
    source_url: str | None = None
    cover_image_url: str | None = None
    last_highlight_at: datetime | None = None


class DocumentSearchResult(BaseModel):
    """Bounded results from a document search operation."""

    items: list[DocumentSummary] = Field(default_factory=list)
    truncated: bool = False


class OperationFailure(BaseModel):
    """One failed item from a bulk operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    item: str | int
    error: Exception

    @property
    def message(self) -> str:
        """Return the adapter-safe text of the original exception."""
        return str(self.error)


class BulkResult[T](BaseModel):
    """Successful items and item-specific failures from a bulk operation."""

    succeeded: list[T] = Field(default_factory=list)
    failures: list[OperationFailure] = Field(default_factory=list)


class SyncCheckpoint(BaseModel):
    """Unified cursors for the next incremental synchronization."""

    model_config = ConfigDict(frozen=True)

    last_highlight_sync: datetime | None = None
    last_book_sync: datetime | None = None
    last_document_sync: datetime | None = None
    last_sync_time: datetime | None = None


class SyncResult(BaseModel):
    """Resource data and checkpoint produced by one sync operation."""

    highlights: list[Highlight] = Field(default_factory=list)
    books: list[Book] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    checkpoint: SyncCheckpoint = Field(default_factory=SyncCheckpoint)

    @property
    def is_empty(self) -> bool:
        """Return whether the sync yielded no resource data."""
        return not self.highlights and not self.books and not self.documents


__all__ = [
    "BookSummary",
    "BulkResult",
    "DocumentSearchResult",
    "DocumentSummary",
    "HighlightSummary",
    "OperationFailure",
    "SyncCheckpoint",
    "SyncResult",
]
