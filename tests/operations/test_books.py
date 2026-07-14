"""Unit tests for canonical book operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from readwise_sdk.models import BookSearch
from readwise_sdk.operations.books import BookOperations
from readwise_sdk.operations.service import ReadwiseService
from readwise_sdk.v2.models import Book, BookCategory, Highlight


class FakeBooksResource:
    """In-memory seam matching the v2 book resource contract."""

    def __init__(self, books: list[Book] | None = None) -> None:
        self.books = books or []
        self.iter_calls: list[dict[str, object]] = []
        self.get_calls: list[int] = []

    async def iter(
        self,
        *,
        page_size: int = 100,
        category: BookCategory | None = None,
        source: str | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        last_highlight_after: datetime | None = None,
        last_highlight_before: datetime | None = None,
    ) -> AsyncIterator[Book]:
        self.iter_calls.append(
            {
                "page_size": page_size,
                "category": category,
                "source": source,
                "updated_after": updated_after,
                "updated_before": updated_before,
                "last_highlight_after": last_highlight_after,
                "last_highlight_before": last_highlight_before,
            }
        )
        for item in self.books:
            if category is not None and item.category is not category:
                continue
            if source is not None and item.source != source:
                continue
            yield item

    async def get(self, book_id: int) -> Book:
        self.get_calls.append(book_id)
        return next(item for item in self.books if item.id == book_id)


class FakeBookHighlightsResource:
    """Minimal highlight seam used for book composition."""

    def __init__(self, highlights: list[Highlight] | None = None) -> None:
        self.highlights = highlights or []
        self.iter_calls: list[int | None] = []

    async def iter(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> AsyncIterator[Highlight]:
        self.iter_calls.append(book_id)
        for item in self.highlights:
            if book_id is None or item.book_id == book_id:
                yield item


def book(
    book_id: int,
    title: str,
    *,
    author: str | None = None,
    category: BookCategory | None = BookCategory.BOOKS,
    source: str | None = None,
    num_highlights: int = 0,
    last_highlight_at: datetime | None = None,
) -> Book:
    """Build a compact book fixture."""
    return Book(
        id=book_id,
        title=title,
        author=author,
        category=category,
        source=source,
        num_highlights=num_highlights,
        last_highlight_at=last_highlight_at,
    )


def operations(
    books: FakeBooksResource,
    highlights: FakeBookHighlightsResource | None = None,
) -> BookOperations:
    """Compose book operations over local resource seams."""
    return BookOperations(books, highlights or FakeBookHighlightsResource())


@pytest.mark.asyncio
async def test_search_ports_mcp_title_filter_projection_limit_and_resource_arguments() -> None:
    """Canonical search is title-only, case-insensitive, bounded, and projected."""
    updated_after = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)
    resource = FakeBooksResource(
        [
            book(1, "A PYTHON Book", author="Nobody", source="kindle", num_highlights=0),
            book(2, "Unrelated", author="Python Author", source="kindle"),
            book(3, "Python Again", source="kindle"),
        ]
    )

    result = await operations(resource).search(
        BookSearch(
            category=BookCategory.BOOKS,
            source="kindle",
            updated_after=updated_after,
            query="python",
            limit=2,
        )
    )

    assert [item.id for item in result.items] == [1, 3]
    assert result.items[0].num_highlights == 0
    assert result.truncated is True
    assert resource.iter_calls == [
        {
            "page_size": 100,
            "category": BookCategory.BOOKS,
            "source": "kindle",
            "updated_after": updated_after,
            "updated_before": None,
            "last_highlight_after": None,
            "last_highlight_before": None,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("provided", "expected"), [(0, 1), (1000, 100)])
async def test_search_uses_stage_five_limit_clamping(provided: int, expected: int) -> None:
    """Book searches retain MCP's inclusive 1..100 clamp."""
    resource = FakeBooksResource([book(index, f"match-{index}") for index in range(101)])

    result = await operations(resource).search(BookSearch(query="match", limit=provided))

    assert len(result.items) == expected


@pytest.mark.asyncio
async def test_list_get_and_manager_search_variants_preserve_raw_semantics() -> None:
    """Raw listing/get and manager title-or-author search remain available."""
    title_match = book(1, "Python", author="One")
    author_match = book(2, "Other", author="Python Person")
    lower = book(3, "python", author=None)
    resource = FakeBooksResource([title_match, author_match, lower])
    operation = operations(resource)

    assert await operation.list(limit=2) == [title_match, author_match]
    assert await operation.list(limit=0) == []
    assert await operation.get(2) is author_match
    assert await operation.search_items("python") == [title_match, author_match, lower]
    assert await operation.search_items("Python", case_sensitive=True) == [
        title_match,
        author_match,
    ]
    assert await operation.count() == 3


@pytest.mark.asyncio
async def test_book_with_highlights_composes_exact_book_and_materialized_list() -> None:
    """Book composition gets one book and all highlights filtered by its ID."""
    selected = book(7, "Selected")
    books = FakeBooksResource([selected])
    first = Highlight(id=1, text="One", book_id=7)
    second = Highlight(id=2, text="Two", book_id=8)
    highlights = FakeBookHighlightsResource([first, second])

    result = await operations(books, highlights).with_highlights(7)

    assert result.book is selected
    assert result.highlights == [first]
    assert books.get_calls == [7]
    assert highlights.iter_calls == [7]


@pytest.mark.asyncio
async def test_recent_books_preserves_sort_and_truthy_limit_quirks() -> None:
    """Recent books sort missing dates last; zero means no slice and negative slices from the end."""
    now = datetime.now(UTC)
    oldest = book(1, "Old", last_highlight_at=now - timedelta(days=10))
    missing = book(2, "Missing", last_highlight_at=None)
    newest = book(3, "New", last_highlight_at=now - timedelta(days=1))
    operation = operations(FakeBooksResource([oldest, missing, newest]))

    assert await operation.recent(days=30, limit=0) == [newest, oldest, missing]
    assert await operation.recent(days=30, limit=-1) == [newest, oldest]


@pytest.mark.asyncio
async def test_reading_statistics_preserve_all_legacy_aggregations_and_second_query() -> None:
    """Statistics retain unknown buckets, top ten ordering, and a separate recent-books request."""
    now = datetime.now(UTC)
    books = FakeBooksResource(
        [
            book(
                1,
                "Book",
                category=BookCategory.BOOKS,
                source="kindle",
                num_highlights=10,
                last_highlight_at=now - timedelta(days=2),
            ),
            book(
                2,
                "Unknown",
                category=None,
                source=None,
                num_highlights=5,
                last_highlight_at=None,
            ),
        ]
    )

    stats = await operations(books).statistics()

    assert stats.total_books == 2
    assert stats.total_highlights == 15
    assert stats.books_by_category == {"books": 1, "unknown": 1}
    assert stats.highlights_by_category == {"books": 10, "unknown": 5}
    assert stats.highlights_by_source == {"kindle": 10, "unknown": 5}
    assert stats.most_highlighted_books == [("Book", 10), ("Unknown", 5)]
    assert [item.id for item in stats.recent_books] == [1, 2]
    assert len(books.iter_calls) == 2
    recent_cutoff = books.iter_calls[1]["updated_after"]
    assert isinstance(recent_cutoff, datetime)
    assert now - timedelta(days=31) < recent_cutoff < now - timedelta(days=29)


def test_service_wires_canonical_book_operations() -> None:
    """The service composes books from book and highlight resources."""
    service = ReadwiseService(
        documents=None,
        books=FakeBooksResource(),
        book_highlights=FakeBookHighlightsResource(),
    )

    assert isinstance(service.books, BookOperations)
