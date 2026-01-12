"""High-level book management operations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from readwise_sdk.v2.models import Book, BookCategory, Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import ReadwiseClient


@dataclass
class BookWithHighlights:
    """A book with its associated highlights."""

    book: Book
    highlights: list[Highlight]


@dataclass
class ReadingStats:
    """Aggregated reading statistics."""

    total_books: int
    total_highlights: int
    books_by_category: dict[str, int]
    highlights_by_category: dict[str, int]
    highlights_by_source: dict[str, int]
    most_highlighted_books: list[tuple[str, int]]
    recent_books: list[Book]


class BookManager:
    """High-level operations for managing books."""

    def __init__(self, client: ReadwiseClient) -> None:
        """Initialize the book manager.

        Args:
            client: The Readwise client.
        """
        self._client = client

    def get_all_books(self) -> list[Book]:
        """Get all books, exhausting pagination.

        Returns:
            List of all books.
        """
        return list(self._client.v2.list_books())

    def get_books_by_category(self, category: BookCategory) -> list[Book]:
        """Get books filtered by category.

        Args:
            category: The category to filter by.

        Returns:
            List of books in the category.
        """
        return list(self._client.v2.list_books(category=category))

    def get_books_by_source(self, source: str) -> list[Book]:
        """Get books filtered by source.

        Args:
            source: The source to filter by (e.g., "kindle", "instapaper").

        Returns:
            List of books from the source.
        """
        return list(self._client.v2.list_books(source=source))

    def get_book_with_highlights(self, book_id: int) -> BookWithHighlights:
        """Get a book with all its highlights.

        Args:
            book_id: The book ID.

        Returns:
            BookWithHighlights containing the book and its highlights.
        """
        book = self._client.v2.get_book(book_id)
        highlights = list(self._client.v2.list_highlights(book_id=book_id))
        return BookWithHighlights(book=book, highlights=highlights)

    def get_recent_books(
        self,
        *,
        days: int | None = None,
        limit: int | None = None,
    ) -> list[Book]:
        """Get recently updated books.

        Args:
            days: Only include books updated in the last N days.
            limit: Maximum number of books to return.

        Returns:
            List of recent books.
        """
        since = None
        if days is not None:
            since = datetime.now(UTC) - timedelta(days=days)

        books = list(self._client.v2.list_books(updated_after=since))

        # Sort by last_highlight_at descending
        books.sort(
            key=lambda b: b.last_highlight_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

        if limit:
            books = books[:limit]

        return books

    def get_reading_stats(self) -> ReadingStats:
        """Get aggregated reading statistics.

        Returns:
            ReadingStats with various aggregations.
        """
        books = self.get_all_books()

        # Aggregate by category
        books_by_category: Counter[str] = Counter()
        highlights_by_category: Counter[str] = Counter()
        highlights_by_source: Counter[str] = Counter()

        for book in books:
            cat = book.category.value if book.category else "unknown"
            books_by_category[cat] += 1
            highlights_by_category[cat] += book.num_highlights

            source = book.source or "unknown"
            highlights_by_source[source] += book.num_highlights

        # Most highlighted books
        most_highlighted = sorted(
            [(b.title, b.num_highlights) for b in books],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Recent books
        recent = self.get_recent_books(days=30, limit=10)

        return ReadingStats(
            total_books=len(books),
            total_highlights=sum(b.num_highlights for b in books),
            books_by_category=dict(books_by_category),
            highlights_by_category=dict(highlights_by_category),
            highlights_by_source=dict(highlights_by_source),
            most_highlighted_books=most_highlighted,
            recent_books=recent,
        )

    def search_books(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Book]:
        """Search books by title or author.

        Args:
            query: The search query.
            case_sensitive: Whether to perform case-sensitive search.

        Returns:
            List of matching books.
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        for book in self._client.v2.list_books():
            title = book.title if case_sensitive else book.title.lower()
            author = (book.author or "") if case_sensitive else (book.author or "").lower()

            if query in title or query in author:
                results.append(book)

        return results

    def get_book_count(self) -> int:
        """Get the total number of books.

        Returns:
            Total book count.
        """
        return len(self.get_all_books())
