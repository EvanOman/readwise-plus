"""Legacy book manager compatibility shim."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from readwise_sdk.operations.books import BookOperations
from readwise_sdk.operations.compat import SyncBooksResource, SyncHighlightsResource, run_sync
from readwise_sdk.v2.models import Book, BookCategory, Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import ReadwiseClient


@dataclass
class BookWithHighlights:
    book: Book
    highlights: list[Highlight]


@dataclass
class ReadingStats:
    total_books: int
    total_highlights: int
    books_by_category: dict[str, int]
    highlights_by_category: dict[str, int]
    highlights_by_source: dict[str, int]
    most_highlighted_books: list[tuple[str, int]]
    recent_books: list[Book]


class BookManager:
    """Compatibility wrapper over canonical book operations."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client
        self._operations = BookOperations(
            SyncBooksResource(client),
            SyncHighlightsResource(client),
        )

    def get_all_books(self) -> list[Book]:
        return run_sync(self._operations.list())

    def get_books_by_category(self, category: BookCategory) -> list[Book]:
        return run_sync(self._operations.list(category=category))

    def get_books_by_source(self, source: str) -> list[Book]:
        return run_sync(self._operations.list(source=source))

    def get_book_with_highlights(self, book_id: int) -> BookWithHighlights:
        result = run_sync(self._operations.with_highlights(book_id))
        return BookWithHighlights(book=result.book, highlights=result.highlights)

    def get_recent_books(
        self,
        *,
        days: int | None = None,
        limit: int | None = None,
    ) -> list[Book]:
        return run_sync(self._operations.recent(days=days, limit=limit))

    def get_reading_stats(self) -> ReadingStats:
        result = run_sync(self._operations.statistics())
        return ReadingStats(
            total_books=result.total_books,
            total_highlights=result.total_highlights,
            books_by_category=result.books_by_category,
            highlights_by_category=result.highlights_by_category,
            highlights_by_source=result.highlights_by_source,
            most_highlighted_books=result.most_highlighted_books,
            recent_books=result.recent_books,
        )

    def search_books(self, query: str, *, case_sensitive: bool = False) -> list[Book]:
        return run_sync(self._operations.search_items(query, case_sensitive=case_sensitive))

    def get_book_count(self) -> int:
        return run_sync(self._operations.count())
