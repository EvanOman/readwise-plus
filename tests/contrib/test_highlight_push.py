"""Tests for HighlightPusher."""

from datetime import datetime

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.contrib.highlight_push import (
    MAX_AUTHOR_LENGTH,
    MAX_NOTE_LENGTH,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    HighlightPusher,
    PushResult,
    SimpleHighlight,
)
from readwise_sdk.v2.models import BookCategory


class TestSimpleHighlight:
    """Tests for SimpleHighlight dataclass."""

    def test_minimal_highlight(self) -> None:
        """Test creating a minimal highlight."""
        h = SimpleHighlight(text="Test text", title="Test Title")
        assert h.text == "Test text"
        assert h.title == "Test Title"
        assert h.author is None
        assert h.category == BookCategory.ARTICLES

    def test_full_highlight(self) -> None:
        """Test creating a full highlight with all fields."""
        now = datetime.now()
        h = SimpleHighlight(
            text="Test text",
            title="Test Title",
            author="John Doe",
            source_url="https://example.com",
            source_type="custom",
            category=BookCategory.BOOKS,
            note="My note",
            location=42,
            location_type="page",
            highlighted_at=now,
            tags=["tag1", "tag2"],
        )
        assert h.text == "Test text"
        assert h.author == "John Doe"
        assert h.category == BookCategory.BOOKS
        assert h.highlighted_at == now
        assert h.tags == ["tag1", "tag2"]


class TestPushResult:
    """Tests for PushResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful push result."""
        result = PushResult(success=True, highlight_id=123, book_id=456)
        assert result.success is True
        assert result.highlight_id == 123
        assert result.book_id == 456
        assert result.error is None
        assert result.was_truncated is False

    def test_failure_result(self) -> None:
        """Test failed push result."""
        result = PushResult(success=False, error="API error")
        assert result.success is False
        assert result.highlight_id is None
        assert result.error == "API error"


class TestHighlightPusher:
    """Tests for HighlightPusher."""

    @respx.mock
    def test_push_single_highlight(self, api_key: str) -> None:
        """Test pushing a single highlight."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [123]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        result = pusher.push(
            text="Test highlight",
            title="Test Book",
            author="Test Author",
        )

        assert result.success is True
        assert result.highlight_id == 123
        assert result.was_truncated is False

    @respx.mock
    def test_push_with_all_fields(self, api_key: str) -> None:
        """Test pushing a highlight with all fields."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [456]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        result = pusher.push(
            text="Test highlight",
            title="Test Book",
            author="Test Author",
            source_url="https://example.com",
            source_type="article",
            category=BookCategory.ARTICLES,
            note="My note",
            location=10,
            highlighted_at=datetime(2024, 1, 1),
            tags=["tag1"],
        )

        assert result.success is True
        assert result.highlight_id == 456

    @respx.mock
    def test_push_highlight_object(self, api_key: str) -> None:
        """Test pushing a SimpleHighlight object."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [789]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        highlight = SimpleHighlight(text="Object highlight", title="Object Book")
        result = pusher.push_highlight(highlight)

        assert result.success is True
        assert result.highlight_id == 789
        assert result.original is highlight

    @respx.mock
    def test_push_batch(self, api_key: str) -> None:
        """Test pushing multiple highlights."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [1, 2, 3]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        highlights = [
            SimpleHighlight(text="First", title="Book 1"),
            SimpleHighlight(text="Second", title="Book 2"),
            SimpleHighlight(text="Third", title="Book 3"),
        ]
        results = pusher.push_batch(highlights)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].highlight_id == 1
        assert results[1].highlight_id == 2
        assert results[2].highlight_id == 3

    def test_push_batch_empty(self, api_key: str) -> None:
        """Test pushing empty batch."""
        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        results = pusher.push_batch([])
        assert results == []

    @respx.mock
    def test_push_batch_api_failure(self, api_key: str) -> None:
        """Test batch push with API failure."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        highlights = [
            SimpleHighlight(text="First", title="Book 1"),
            SimpleHighlight(text="Second", title="Book 2"),
        ]
        results = pusher.push_batch(highlights)

        assert len(results) == 2
        assert all(not r.success for r in results)
        assert all(r.error is not None for r in results)

    @respx.mock
    def test_push_with_truncation(self, api_key: str) -> None:
        """Test pushing with auto-truncation of long fields."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [999]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client, auto_truncate=True)

        # Create text longer than MAX_TEXT_LENGTH
        long_text = "x" * (MAX_TEXT_LENGTH + 100)
        result = pusher.push(text=long_text, title="Test")

        assert result.success is True
        assert result.was_truncated is True

    @respx.mock
    def test_push_truncation_all_fields(self, api_key: str) -> None:
        """Test truncation of all field types."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [111]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client, auto_truncate=True)

        result = pusher.push(
            text="x" * (MAX_TEXT_LENGTH + 10),
            title="y" * (MAX_TITLE_LENGTH + 10),
            author="z" * (MAX_AUTHOR_LENGTH + 10),
            note="n" * (MAX_NOTE_LENGTH + 10),
        )

        assert result.success is True
        assert result.was_truncated is True

    @respx.mock
    def test_push_no_truncation_when_disabled(self, api_key: str) -> None:
        """Test that truncation is not applied when disabled."""
        route = respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [222]}],
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client, auto_truncate=False)

        # Text within limits - should not truncate
        short_text = "Short text"
        result = pusher.push(text=short_text, title="Test")

        assert result.success is True
        assert result.was_truncated is False
        # Verify the request was made
        assert route.called

    def test_truncate_field_none(self) -> None:
        """Test truncating None value."""
        from readwise_sdk._utils import truncate_string

        value, was_truncated = truncate_string(None, 100)
        assert value is None
        assert was_truncated is False

    def test_truncate_field_short(self) -> None:
        """Test truncating short value (no truncation needed)."""
        from readwise_sdk._utils import truncate_string

        value, was_truncated = truncate_string("short", 100)
        assert value == "short"
        assert was_truncated is False

    def test_truncate_field_long(self) -> None:
        """Test truncating long value."""
        from readwise_sdk._utils import truncate_string

        long_value = "x" * 200
        value, was_truncated = truncate_string(long_value, 100)
        assert value is not None
        assert len(value) == 100
        assert value.endswith("...")
        assert was_truncated is True

    @respx.mock
    def test_validate_token(self, api_key: str) -> None:
        """Test token validation."""
        respx.get(f"{READWISE_API_V2_BASE}/auth/").mock(return_value=httpx.Response(204))

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        assert pusher.validate_token() is True

    @respx.mock
    def test_push_partial_api_result(self, api_key: str) -> None:
        """Test when API returns fewer results than expected."""
        respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [1]}],  # Only 1 result for 2 highlights
            )
        )

        client = ReadwiseClient(api_key=api_key)
        pusher = HighlightPusher(client)

        highlights = [
            SimpleHighlight(text="First", title="Book 1"),
            SimpleHighlight(text="Second", title="Book 2"),
        ]
        results = pusher.push_batch(highlights)

        assert len(results) == 2
        assert results[0].success is True
        assert results[0].highlight_id == 1
        assert results[1].success is False
        assert results[1].error is not None
        assert "No API result returned" in results[1].error
