"""Tests for BookManager."""

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.managers.books import BookManager
from readwise_sdk.v2.models import BookCategory


class TestBookManager:
    """Tests for BookManager."""

    @respx.mock
    def test_get_all_books(self, api_key: str) -> None:
        """Test getting all books."""
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "title": "Book One"},
                        {"id": 2, "title": "Book Two"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = BookManager(client)
        books = manager.get_all_books()

        assert len(books) == 2

    @respx.mock
    def test_get_books_by_category(self, api_key: str) -> None:
        """Test getting books by category."""
        route = respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = BookManager(client)
        manager.get_books_by_category(BookCategory.ARTICLES)

        request = route.calls.last.request
        assert "category=articles" in str(request.url)

    @respx.mock
    def test_get_book_with_highlights(self, api_key: str) -> None:
        """Test getting a book with its highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/books/123/").mock(
            return_value=httpx.Response(
                200,
                json={"id": 123, "title": "Test Book"},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Highlight 1"},
                        {"id": 2, "text": "Highlight 2"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = BookManager(client)
        result = manager.get_book_with_highlights(123)

        assert result.book.id == 123
        assert len(result.highlights) == 2

    @respx.mock
    def test_get_reading_stats(self, api_key: str) -> None:
        """Test getting reading statistics."""
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "title": "Book 1",
                            "category": "books",
                            "source": "kindle",
                            "num_highlights": 10,
                        },
                        {
                            "id": 2,
                            "title": "Article 1",
                            "category": "articles",
                            "source": "instapaper",
                            "num_highlights": 5,
                        },
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = BookManager(client)
        stats = manager.get_reading_stats()

        assert stats.total_books == 2
        assert stats.total_highlights == 15
        assert stats.books_by_category["books"] == 1
        assert stats.books_by_category["articles"] == 1
        assert stats.highlights_by_source["kindle"] == 10

    @respx.mock
    def test_search_books(self, api_key: str) -> None:
        """Test searching books."""
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "title": "Python Programming", "author": "John"},
                        {"id": 2, "title": "JavaScript Guide", "author": "Jane"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = BookManager(client)
        results = manager.search_books("python")

        assert len(results) == 1
        assert "Python" in results[0].title
