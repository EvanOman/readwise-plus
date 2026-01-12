"""Tests for DigestBuilder."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.workflows.digest import DigestBuilder, DigestFormat


class TestDigestBuilder:
    """Tests for DigestBuilder."""

    @respx.mock
    def test_create_daily_digest_markdown(self, api_key: str) -> None:
        """Test creating daily digest in markdown format."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "text": "Test highlight one",
                            "note": "My note",
                            "book_id": 100,
                        },
                        {
                            "id": 2,
                            "text": "Test highlight two",
                            "book_id": 100,
                        },
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_daily_digest(output_format=DigestFormat.MARKDOWN)

        assert "# Daily Digest" in digest
        assert "Test highlight one" in digest
        assert "Test highlight two" in digest
        assert "My note" in digest

    @respx.mock
    def test_create_weekly_digest(self, api_key: str) -> None:
        """Test creating weekly digest."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1, "text": "Weekly highlight"}],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_weekly_digest(output_format=DigestFormat.TEXT)

        assert "Weekly Digest" in digest
        assert "Weekly highlight" in digest

    @respx.mock
    def test_create_book_digest(self, api_key: str) -> None:
        """Test creating digest for a specific book."""
        respx.get(f"{READWISE_API_V2_BASE}/books/123/").mock(
            return_value=httpx.Response(
                200,
                json={"id": 123, "title": "My Book", "num_highlights": 2},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Book highlight 1", "book_id": 123},
                        {"id": 2, "text": "Book highlight 2", "book_id": 123},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_book_digest(123, output_format=DigestFormat.MARKDOWN)

        assert "My Book" in digest
        assert "Book highlight 1" in digest
        assert "Book highlight 2" in digest

    @respx.mock
    def test_digest_json_format(self, api_key: str) -> None:
        """Test JSON output format."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1, "text": "JSON highlight", "note": "Note"}],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_daily_digest(output_format=DigestFormat.JSON)

        data = json.loads(digest)
        assert data["title"] == "Daily Digest"
        assert data["count"] == 1
        assert data["highlights"][0]["text"] == "JSON highlight"

    @respx.mock
    def test_digest_csv_format(self, api_key: str) -> None:
        """Test CSV output format."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1, "text": "CSV highlight"}],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_daily_digest(output_format=DigestFormat.CSV)

        assert "id,text,note" in digest
        assert "CSV highlight" in digest

    @respx.mock
    def test_digest_empty(self, api_key: str) -> None:
        """Test digest with no highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_daily_digest()

        assert "0 highlights" in digest

    @respx.mock
    def test_digest_group_by_date(self, api_key: str) -> None:
        """Test grouping highlights by date."""
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)

        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "text": "Today highlight",
                            "highlighted_at": now.isoformat(),
                        },
                        {
                            "id": 2,
                            "text": "Yesterday highlight",
                            "highlighted_at": yesterday.isoformat(),
                        },
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        builder = DigestBuilder(client)
        digest = builder.create_custom_digest(
            output_format=DigestFormat.MARKDOWN,
            group_by_date=True,
            group_by_book=False,
        )

        assert "Today highlight" in digest
        assert "Yesterday highlight" in digest
