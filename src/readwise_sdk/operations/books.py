"""Canonical async-first operations for Readwise books and sources."""

from __future__ import annotations

import builtins
from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from readwise_sdk.models import BookSearch, BookSummary
from readwise_sdk.v2.models import Book, BookCategory, Highlight


class BooksResource(Protocol):
    """Low-level book capabilities required by book operations."""

    def iter(
        self,
        *,
        page_size: int = 100,
        category: BookCategory | None = None,
        source: str | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        last_highlight_after: datetime | None = None,
        last_highlight_before: datetime | None = None,
    ) -> AsyncIterator[Book]: ...

    async def get(self, book_id: int) -> Book: ...


class BookHighlightsResource(Protocol):
    """The highlight iteration capability required for book composition."""

    def iter(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> AsyncIterator[Highlight]: ...


@dataclass(frozen=True, slots=True)
class BookSearchResult:
    """Bounded semantic book summaries."""

    items: list[BookSummary] = field(default_factory=list)
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class BookWithHighlights:
    """One book and its materialized highlights."""

    book: Book
    highlights: list[Highlight] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReadingStatistics:
    """Aggregated reading statistics from the legacy book managers."""

    total_books: int
    total_highlights: int
    books_by_category: dict[str, int]
    highlights_by_category: dict[str, int]
    highlights_by_source: dict[str, int]
    most_highlighted_books: list[tuple[str, int]]
    recent_books: list[Book]


def _summary(book: Book) -> BookSummary:
    """Project the fields shared by current CLI and MCP adapters."""
    return BookSummary(
        id=book.id,
        title=book.title,
        author=book.author,
        category=book.category,
        source=book.source,
        num_highlights=book.num_highlights,
        source_url=book.source_url,
        cover_image_url=book.cover_image_url,
        last_highlight_at=book.last_highlight_at,
    )


class BookOperations:
    """Own book filtering, composition, limits, and reading aggregations."""

    def __init__(self, resource: BooksResource, highlights: BookHighlightsResource) -> None:
        self._resource = resource
        self._highlights = highlights

    async def search(self, search: BookSearch) -> BookSearchResult:
        """Return bounded MCP-compatible summaries using title-only matching."""
        query = search.query.lower() if search.query else None
        items: list[BookSummary] = []
        async for book in self._resource.iter(
            category=search.category,
            source=search.source,
            updated_after=search.updated_after,
        ):
            if query and query not in book.title.lower():
                continue
            items.append(_summary(book))
            if len(items) >= search.limit:
                return BookSearchResult(items=items, truncated=True)
        return BookSearchResult(items=items, truncated=False)

    async def list(
        self,
        *,
        category: BookCategory | None = None,
        source: str | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        last_highlight_after: datetime | None = None,
        last_highlight_before: datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[Book]:
        """Materialize raw books with the CLI's un-clamped limit behavior."""
        items: list[Book] = []
        async for book in self._resource.iter(
            category=category,
            source=source,
            updated_after=updated_after,
            updated_before=updated_before,
            last_highlight_after=last_highlight_after,
            last_highlight_before=last_highlight_before,
        ):
            if limit is not None and len(items) >= limit:
                break
            items.append(book)
        return items

    async def get(self, book_id: int) -> Book:
        """Get one book."""
        return await self._resource.get(book_id)

    async def with_highlights(self, book_id: int) -> BookWithHighlights:
        """Compose a book with every highlight returned for its ID."""
        book = await self.get(book_id)
        highlights = [item async for item in self._highlights.iter(book_id=book_id)]
        return BookWithHighlights(book=book, highlights=highlights)

    async def recent(
        self,
        *,
        days: int | None = None,
        limit: int | None = None,
    ) -> builtins.list[Book]:
        """Reproduce manager date filtering, sorting, and truthy-limit slicing."""
        since = datetime.now(UTC) - timedelta(days=days) if days is not None else None
        books = await self.list(updated_after=since)
        books.sort(
            key=lambda book: book.last_highlight_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        if limit:
            books = books[:limit]
        return books

    async def statistics(self) -> ReadingStatistics:
        """Compose the exact legacy reading-statistics aggregations."""
        books = await self.list()
        books_by_category: Counter[str] = Counter()
        highlights_by_category: Counter[str] = Counter()
        highlights_by_source: Counter[str] = Counter()

        for book in books:
            category = book.category.value if book.category else "unknown"
            books_by_category[category] += 1
            highlights_by_category[category] += book.num_highlights
            source = book.source or "unknown"
            highlights_by_source[source] += book.num_highlights

        most_highlighted = sorted(
            [(book.title, book.num_highlights) for book in books],
            key=lambda item: item[1],
            reverse=True,
        )[:10]
        recent = await self.recent(days=30, limit=10)
        return ReadingStatistics(
            total_books=len(books),
            total_highlights=sum(book.num_highlights for book in books),
            books_by_category=dict(books_by_category),
            highlights_by_category=dict(highlights_by_category),
            highlights_by_source=dict(highlights_by_source),
            most_highlighted_books=most_highlighted,
            recent_books=recent,
        )

    async def search_items(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> builtins.list[Book]:
        """Reproduce manager search across book titles and authors."""
        normalized = query if case_sensitive else query.lower()
        results: list[Book] = []
        async for book in self._resource.iter():
            title = book.title if case_sensitive else book.title.lower()
            author = book.author or ""
            if not case_sensitive:
                author = author.lower()
            if normalized in title or normalized in author:
                results.append(book)
        return results

    async def count(self) -> int:
        """Count books using the manager's materialized-list behavior."""
        return len(await self.list())


__all__ = [
    "BookOperations",
    "BookHighlightsResource",
    "BookSearchResult",
    "BooksResource",
    "BookWithHighlights",
    "ReadingStatistics",
]
