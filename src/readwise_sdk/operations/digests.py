"""Canonical digest data selection and grouping operations."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Protocol

from readwise_sdk.models.readwise import Book, Highlight


class DigestHighlightsResource(Protocol):
    """Highlight iteration required by canonical digest operations."""

    def iter(
        self,
        *,
        book_id: int | None = None,
        updated_after: datetime | None = None,
    ) -> AsyncIterator[Highlight]: ...


class DigestBooksResource(Protocol):
    """Book lookup required by book-specific digests."""

    async def get(self, book_id: int) -> Book: ...


class SyncDigestClient(Protocol):
    """Legacy synchronous capabilities used by the workflow compatibility shim."""

    def list_highlights(
        self,
        *,
        updated_after: datetime | None = None,
        book_id: int | None = None,
    ) -> Iterator[Highlight]: ...

    def get_book(self, book_id: int) -> Book: ...


class DigestGrouping(str, Enum):
    """Grouping already selected by digest operations for presenters."""

    NONE = "none"
    BOOK = "book"
    DATE = "date"


@dataclass(frozen=True, slots=True)
class DigestData:
    """Protocol-neutral digest data ready for a presenter."""

    title: str
    highlights: list[Highlight] = field(default_factory=list)
    grouping: DigestGrouping = DigestGrouping.NONE
    groups: list[tuple[str, list[Highlight]]] = field(default_factory=list)


def group_by_book(highlights: list[Highlight]) -> list[tuple[str, list[Highlight]]]:
    """Group highlights by the legacy synthetic book label."""
    groups: dict[str, list[Highlight]] = {}
    for highlight in highlights:
        key = f"Book {highlight.book_id}" if highlight.book_id else "Unknown"
        groups.setdefault(key, []).append(highlight)
    return list(groups.items())


def group_by_date(highlights: list[Highlight]) -> list[tuple[str, list[Highlight]]]:
    """Group highlights by date, newest date label first."""
    groups: dict[str, list[Highlight]] = {}
    for highlight in highlights:
        key = (
            highlight.highlighted_at.strftime("%Y-%m-%d")
            if highlight.highlighted_at
            else "Unknown Date"
        )
        groups.setdefault(key, []).append(highlight)
    return sorted(groups.items(), reverse=True)


def build_digest(
    highlights: list[Highlight],
    *,
    title: str,
    group_by_book_enabled: bool = True,
    group_by_date_enabled: bool = False,
) -> DigestData:
    """Apply the legacy grouping precedence and return digest data."""
    if group_by_date_enabled:
        grouping = DigestGrouping.DATE
        groups = group_by_date(highlights)
    elif group_by_book_enabled:
        grouping = DigestGrouping.BOOK
        groups = group_by_book(highlights)
    else:
        grouping = DigestGrouping.NONE
        groups = []
    return DigestData(title=title, highlights=highlights, grouping=grouping, groups=groups)


class DigestOperations:
    """Own async digest selection windows, filters, titles, and grouping."""

    def __init__(
        self,
        highlights: DigestHighlightsResource,
        books: DigestBooksResource,
    ) -> None:
        self._highlights = highlights
        self._books = books

    async def daily(self, *, group_by_book: bool = True) -> DigestData:
        """Select highlights updated in the last 24 hours."""
        since = datetime.now(UTC) - timedelta(days=1)
        highlights = [highlight async for highlight in self._highlights.iter(updated_after=since)]
        return build_digest(
            highlights,
            title="Daily Digest",
            group_by_book_enabled=group_by_book,
        )

    async def weekly(self, *, group_by_book: bool = True) -> DigestData:
        """Select highlights updated in the last seven days."""
        since = datetime.now(UTC) - timedelta(days=7)
        highlights = [highlight async for highlight in self._highlights.iter(updated_after=since)]
        return build_digest(
            highlights,
            title="Weekly Digest",
            group_by_book_enabled=group_by_book,
        )

    async def book(self, book_id: int) -> DigestData:
        """Select all highlights for one book and use its title."""
        book = await self._books.get(book_id)
        highlights = [highlight async for highlight in self._highlights.iter(book_id=book_id)]
        return build_digest(
            highlights,
            title=f"Highlights from: {book.title}",
            group_by_book_enabled=False,
        )

    async def custom(
        self,
        *,
        since: datetime | None = None,
        book_id: int | None = None,
        group_by_book: bool = True,
        group_by_date: bool = False,
    ) -> DigestData:
        """Select and group highlights using caller-supplied filters."""
        highlights = [
            highlight
            async for highlight in self._highlights.iter(
                updated_after=since,
                book_id=book_id,
            )
        ]
        return build_digest(
            highlights,
            title="Custom Digest",
            group_by_book_enabled=group_by_book,
            group_by_date_enabled=group_by_date,
        )


class SyncDigestOperations:
    """Synchronous operation adapter used solely by the legacy workflow shim."""

    def __init__(self, client: SyncDigestClient) -> None:
        self._client = client

    def daily(self, *, group_by_book: bool = True) -> DigestData:
        since = datetime.now(UTC) - timedelta(days=1)
        return build_digest(
            list(self._client.list_highlights(updated_after=since)),
            title="Daily Digest",
            group_by_book_enabled=group_by_book,
        )

    def weekly(self, *, group_by_book: bool = True) -> DigestData:
        since = datetime.now(UTC) - timedelta(days=7)
        return build_digest(
            list(self._client.list_highlights(updated_after=since)),
            title="Weekly Digest",
            group_by_book_enabled=group_by_book,
        )

    def book(self, book_id: int) -> DigestData:
        book = self._client.get_book(book_id)
        return build_digest(
            list(self._client.list_highlights(book_id=book_id)),
            title=f"Highlights from: {book.title}",
            group_by_book_enabled=False,
        )

    def custom(
        self,
        *,
        since: datetime | None = None,
        book_id: int | None = None,
        group_by_book: bool = True,
        group_by_date: bool = False,
    ) -> DigestData:
        return build_digest(
            list(self._client.list_highlights(updated_after=since, book_id=book_id)),
            title="Custom Digest",
            group_by_book_enabled=group_by_book,
            group_by_date_enabled=group_by_date,
        )


__all__ = [
    "DigestData",
    "DigestGrouping",
    "DigestOperations",
    "SyncDigestOperations",
    "build_digest",
    "group_by_book",
    "group_by_date",
]
