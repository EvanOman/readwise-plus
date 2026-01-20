"""Tests for internal utility functions."""

from datetime import UTC, datetime

import httpx
import pytest

from readwise_sdk._utils import (
    handle_response,
    parse_datetime_string,
    parse_pagination_cursor,
    truncate_string,
)
from readwise_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ReadwiseError,
    ServerError,
    ValidationError,
)


class TestHandleResponse:
    """Tests for handle_response function."""

    def test_success_response(self) -> None:
        """Test that successful responses are returned as-is."""
        response = httpx.Response(200, json={"data": "test"})
        result = handle_response(response)
        assert result is response

    def test_204_success(self) -> None:
        """Test that 204 No Content is treated as success."""
        response = httpx.Response(204)
        result = handle_response(response)
        assert result is response

    def test_401_raises_authentication_error(self) -> None:
        """Test that 401 raises AuthenticationError."""
        response = httpx.Response(401, text="Unauthorized")
        with pytest.raises(AuthenticationError) as exc_info:
            handle_response(response)
        assert "Unauthorized" in str(exc_info.value.response_body)

    def test_404_raises_not_found_error(self) -> None:
        """Test that 404 raises NotFoundError."""
        response = httpx.Response(404, text="Not Found")
        with pytest.raises(NotFoundError):
            handle_response(response)

    def test_429_raises_rate_limit_error(self) -> None:
        """Test that 429 raises RateLimitError."""
        response = httpx.Response(429, text="Too Many Requests")
        with pytest.raises(RateLimitError):
            handle_response(response)

    def test_429_with_retry_after(self) -> None:
        """Test that 429 with Retry-After header is captured."""
        response = httpx.Response(429, text="Too Many Requests", headers={"Retry-After": "60"})
        with pytest.raises(RateLimitError) as exc_info:
            handle_response(response)
        assert exc_info.value.retry_after == 60

    def test_400_raises_validation_error(self) -> None:
        """Test that 400 raises ValidationError."""
        response = httpx.Response(400, text="Bad Request")
        with pytest.raises(ValidationError):
            handle_response(response)

    def test_500_raises_server_error(self) -> None:
        """Test that 500 raises ServerError."""
        response = httpx.Response(500, text="Internal Server Error")
        with pytest.raises(ServerError) as exc_info:
            handle_response(response)
        assert exc_info.value.status_code == 500

    def test_502_raises_server_error(self) -> None:
        """Test that 502 also raises ServerError."""
        response = httpx.Response(502, text="Bad Gateway")
        with pytest.raises(ServerError) as exc_info:
            handle_response(response)
        assert exc_info.value.status_code == 502

    def test_other_error_raises_readwise_error(self) -> None:
        """Test that other errors raise generic ReadwiseError."""
        response = httpx.Response(418, text="I'm a teapot")
        with pytest.raises(ReadwiseError) as exc_info:
            handle_response(response)
        assert exc_info.value.status_code == 418


class TestParsePaginationCursor:
    """Tests for parse_pagination_cursor function."""

    def test_cursor_string(self) -> None:
        """Test parsing a simple cursor string."""
        url, params = parse_pagination_cursor(
            "abc123",
            "https://api.example.com/items",
            {"limit": 10},
        )
        assert url == "https://api.example.com/items"
        assert params == {"limit": 10, "pageCursor": "abc123"}

    def test_full_url_cursor(self) -> None:
        """Test parsing a full URL cursor."""
        url, params = parse_pagination_cursor(
            "https://api.example.com/items?pageCursor=xyz&limit=20",
            "https://api.example.com/items",
            {"limit": 10},
        )
        assert url == "https://api.example.com/items"
        assert params == {"pageCursor": "xyz", "limit": "20"}

    def test_preserves_original_params_for_cursor_string(self) -> None:
        """Test that original params are preserved when using cursor string."""
        url, params = parse_pagination_cursor(
            "cursor123",
            "https://api.example.com/items",
            {"filter": "active", "sort": "date"},
        )
        assert params["filter"] == "active"
        assert params["sort"] == "date"
        assert params["pageCursor"] == "cursor123"


class TestParseDatetimeString:
    """Tests for parse_datetime_string function."""

    def test_none_returns_none(self) -> None:
        """Test that None input returns None."""
        assert parse_datetime_string(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        assert parse_datetime_string("") is None

    def test_datetime_passthrough(self) -> None:
        """Test that datetime objects are returned as-is."""
        dt = datetime(2024, 1, 15, 12, 30, 0, tzinfo=UTC)
        assert parse_datetime_string(dt) is dt

    def test_iso_format_string(self) -> None:
        """Test parsing ISO format string."""
        result = parse_datetime_string("2024-01-15T12:30:00+00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30

    def test_z_suffix(self) -> None:
        """Test parsing datetime with Z suffix."""
        result = parse_datetime_string("2024-01-15T12:30:00Z")
        assert result is not None
        assert result.year == 2024

    def test_invalid_string_returns_none(self) -> None:
        """Test that invalid string returns None."""
        assert parse_datetime_string("not a date") is None

    def test_partial_date_returns_none(self) -> None:
        """Test that partial date returns None."""
        assert parse_datetime_string("2024-01") is None


class TestTruncateString:
    """Tests for truncate_string function."""

    def test_none_returns_none(self) -> None:
        """Test that None input returns None with no truncation."""
        value, was_truncated = truncate_string(None, 100)
        assert value is None
        assert was_truncated is False

    def test_short_string_unchanged(self) -> None:
        """Test that short strings are returned unchanged."""
        value, was_truncated = truncate_string("hello", 100)
        assert value == "hello"
        assert was_truncated is False

    def test_exact_length_unchanged(self) -> None:
        """Test that string at exact max length is unchanged."""
        value, was_truncated = truncate_string("hello", 5)
        assert value == "hello"
        assert was_truncated is False

    def test_long_string_truncated(self) -> None:
        """Test that long strings are truncated with ellipsis."""
        long_text = "x" * 200
        value, was_truncated = truncate_string(long_text, 100)
        assert value is not None
        assert len(value) == 100
        assert value.endswith("...")
        assert was_truncated is True

    def test_truncation_preserves_content(self) -> None:
        """Test that truncation preserves the beginning of content."""
        text = "abcdefghijklmnopqrstuvwxyz"
        value, was_truncated = truncate_string(text, 10)
        assert value == "abcdefg..."
        assert was_truncated is True
