"""Tests for HighlightManager."""

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.managers.highlights import HighlightManager


class TestHighlightManager:
    """Tests for HighlightManager."""

    @respx.mock
    def test_get_all_highlights(self, api_key: str) -> None:
        """Test getting all highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "First"},
                        {"id": 2, "text": "Second"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        highlights = manager.get_all_highlights()

        assert len(highlights) == 2
        assert highlights[0].text == "First"

    @respx.mock
    def test_get_highlights_by_book(self, api_key: str) -> None:
        """Test getting highlights for a specific book."""
        route = respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "text": "Test"}], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        manager.get_highlights_by_book(123)

        request = route.calls.last.request
        assert "book_id=123" in str(request.url)

    @respx.mock
    def test_get_highlights_with_notes(self, api_key: str) -> None:
        """Test getting highlights with notes."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "No note", "note": None},
                        {"id": 2, "text": "Has note", "note": "My note"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        highlights = manager.get_highlights_with_notes()

        assert len(highlights) == 1
        assert highlights[0].id == 2

    @respx.mock
    def test_search_highlights(self, api_key: str) -> None:
        """Test searching highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Python programming"},
                        {"id": 2, "text": "JavaScript basics"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        results = manager.search_highlights("python")

        assert len(results) == 1
        assert "Python" in results[0].text

    @respx.mock
    def test_bulk_tag(self, api_key: str) -> None:
        """Test bulk tagging highlights."""
        respx.post(url__startswith=f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(200, json={"id": 1, "name": "test-tag"})
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        results = manager.bulk_tag([1, 2], "test-tag")

        assert results[1] is True
        assert results[2] is True

    @respx.mock
    def test_create_highlight(self, api_key: str) -> None:
        """Test creating a single highlight."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [999]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        highlight_id = manager.create_highlight(
            text="New highlight text",
            title="My Book",
            author="Author",
        )

        assert highlight_id == 999

    @respx.mock
    def test_get_highlight_count(self, api_key: str) -> None:
        """Test getting highlight count."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = HighlightManager(client)
        count = manager.get_highlight_count()

        assert count == 2
