"""Tests for Readwise API v2 client."""

import httpx
import pytest
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.exceptions import NotFoundError
from readwise_sdk.v2.models import BookCategory, HighlightCreate, HighlightUpdate


class TestV2ClientAccess:
    """Tests for accessing v2 client from main client."""

    def test_v2_property(self, api_key: str) -> None:
        """Test that v2 property returns the v2 client."""
        client = ReadwiseClient(api_key=api_key)
        assert client.v2 is not None

    def test_v2_property_cached(self, api_key: str) -> None:
        """Test that v2 client is cached."""
        client = ReadwiseClient(api_key=api_key)
        v2_first = client.v2
        v2_second = client.v2
        assert v2_first is v2_second


class TestHighlights:
    """Tests for highlight operations."""

    @respx.mock
    def test_list_highlights(self, api_key: str) -> None:
        """Test listing highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "First highlight"},
                        {"id": 2, "text": "Second highlight"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        highlights = list(client.v2.list_highlights())

        assert len(highlights) == 2
        assert highlights[0].id == 1
        assert highlights[0].text == "First highlight"

    @respx.mock
    def test_list_highlights_with_filters(self, api_key: str) -> None:
        """Test listing highlights with filters."""
        route = respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        list(client.v2.list_highlights(book_id=123, page_size=50))

        assert route.called
        request = route.calls.last.request
        assert "book_id=123" in str(request.url)
        assert "page_size=50" in str(request.url)

    @respx.mock
    def test_get_highlight(self, api_key: str) -> None:
        """Test getting a single highlight."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/123/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 123,
                    "text": "Test highlight",
                    "note": "My note",
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        highlight = client.v2.get_highlight(123)

        assert highlight.id == 123
        assert highlight.text == "Test highlight"
        assert highlight.note == "My note"

    @respx.mock
    def test_get_highlight_not_found(self, api_key: str) -> None:
        """Test getting a non-existent highlight."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/99999/").mock(
            return_value=httpx.Response(404, text="Not found")
        )

        client = ReadwiseClient(api_key=api_key)
        with pytest.raises(NotFoundError):
            client.v2.get_highlight(99999)

    @respx.mock
    def test_create_highlights(self, api_key: str) -> None:
        """Test creating highlights."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [101, 102]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        highlights = [
            HighlightCreate(text="First new highlight", title="Book 1"),
            HighlightCreate(text="Second new highlight", title="Book 2"),
        ]
        result = client.v2.create_highlights(highlights)

        assert result == [101, 102]

    @respx.mock
    def test_update_highlight(self, api_key: str) -> None:
        """Test updating a highlight."""
        respx.patch(f"{READWISE_API_V2_BASE}/highlights/123/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 123,
                    "text": "Original text",
                    "note": "Updated note",
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        update = HighlightUpdate(note="Updated note")
        highlight = client.v2.update_highlight(123, update)

        assert highlight.id == 123
        assert highlight.note == "Updated note"

    @respx.mock
    def test_delete_highlight(self, api_key: str) -> None:
        """Test deleting a highlight."""
        respx.delete(f"{READWISE_API_V2_BASE}/highlights/123/").mock(
            return_value=httpx.Response(204)
        )

        client = ReadwiseClient(api_key=api_key)
        client.v2.delete_highlight(123)  # Should not raise


class TestBooks:
    """Tests for book operations."""

    @respx.mock
    def test_list_books(self, api_key: str) -> None:
        """Test listing books."""
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "title": "Book One", "author": "Author One"},
                        {"id": 2, "title": "Book Two", "author": "Author Two"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        books = list(client.v2.list_books())

        assert len(books) == 2
        assert books[0].title == "Book One"

    @respx.mock
    def test_list_books_by_category(self, api_key: str) -> None:
        """Test listing books filtered by category."""
        route = respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        list(client.v2.list_books(category=BookCategory.ARTICLES))

        assert route.called
        request = route.calls.last.request
        assert "category=articles" in str(request.url)

    @respx.mock
    def test_get_book(self, api_key: str) -> None:
        """Test getting a single book."""
        respx.get(f"{READWISE_API_V2_BASE}/books/456/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 456,
                    "title": "Test Book",
                    "author": "Test Author",
                    "num_highlights": 10,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        book = client.v2.get_book(456)

        assert book.id == 456
        assert book.title == "Test Book"
        assert book.num_highlights == 10


class TestHighlightTags:
    """Tests for highlight tag operations."""

    @respx.mock
    def test_list_highlight_tags(self, api_key: str) -> None:
        """Test listing tags for a highlight."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/123/tags/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "name": "favorite"},
                        {"id": 2, "name": "important"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        tags = list(client.v2.list_highlight_tags(123))

        assert len(tags) == 2
        assert tags[0].name == "favorite"

    @respx.mock
    def test_create_highlight_tag(self, api_key: str) -> None:
        """Test adding a tag to a highlight."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/123/tags/").mock(
            return_value=httpx.Response(
                200,
                json={"id": 5, "name": "new-tag"},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        tag = client.v2.create_highlight_tag(123, "new-tag")

        assert tag.id == 5
        assert tag.name == "new-tag"

    @respx.mock
    def test_delete_highlight_tag(self, api_key: str) -> None:
        """Test removing a tag from a highlight."""
        respx.delete(f"{READWISE_API_V2_BASE}/highlights/123/tags/5/").mock(
            return_value=httpx.Response(204)
        )

        client = ReadwiseClient(api_key=api_key)
        client.v2.delete_highlight_tag(123, 5)  # Should not raise


class TestBookTags:
    """Tests for book tag operations."""

    @respx.mock
    def test_list_book_tags(self, api_key: str) -> None:
        """Test listing tags for a book."""
        respx.get(f"{READWISE_API_V2_BASE}/books/456/tags/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1, "name": "tech"}],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        tags = list(client.v2.list_book_tags(456))

        assert len(tags) == 1
        assert tags[0].name == "tech"

    @respx.mock
    def test_create_book_tag(self, api_key: str) -> None:
        """Test adding a tag to a book."""
        respx.post(f"{READWISE_API_V2_BASE}/books/456/tags/").mock(
            return_value=httpx.Response(
                200,
                json={"id": 10, "name": "programming"},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        tag = client.v2.create_book_tag(456, "programming")

        assert tag.id == 10
        assert tag.name == "programming"


class TestExport:
    """Tests for export operations."""

    @respx.mock
    def test_export_highlights(self, api_key: str) -> None:
        """Test exporting highlights."""
        respx.get(url__startswith=f"{READWISE_API_V2_BASE}/export/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "user_book_id": 1,
                            "title": "Book One",
                            "author": "Author One",
                            "highlights": [
                                {"id": 1, "text": "Highlight 1"},
                                {"id": 2, "text": "Highlight 2"},
                            ],
                        }
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        export_books = list(client.v2.export_highlights())

        assert len(export_books) == 1
        assert export_books[0].title == "Book One"
        assert len(export_books[0].highlights) == 2


class TestDailyReview:
    """Tests for daily review operations."""

    @respx.mock
    def test_get_daily_review(self, api_key: str) -> None:
        """Test getting daily review."""
        respx.get(f"{READWISE_API_V2_BASE}/review/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "review_id": 12345,
                    "review_url": "https://readwise.io/review/12345",
                    "review_completed": False,
                    "highlights": [
                        {"id": 1, "text": "Review highlight 1"},
                        {"id": 2, "text": "Review highlight 2"},
                    ],
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        review = client.v2.get_daily_review()

        assert review.review_id == 12345
        assert len(review.highlights) == 2
        assert review.review_completed is False
