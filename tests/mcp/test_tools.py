"""Unit tests for MCP tool handlers with mocked HTTP transport."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
import respx

pytest.importorskip("mcp")

from readwise_sdk.mcp.server import (
    _get_api_key,
    _json_result,
    _parse_iso_datetime,
    create_highlight,
    delete_document,
    export_highlights,
    get_books,
    get_document,
    get_highlights,
    save_to_reader,
    search_documents,
    update_document,
)

# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestGetApiKey:
    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("READWISE_API_KEY", "env-key-123")
        assert _get_api_key() == "env-key-123"

    def test_from_dotenv_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.delenv("READWISE_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("READWISE_API_KEY=file-key-456\n")
        with patch("readwise_sdk.mcp.server.os.path.expanduser", return_value=str(env_file)):
            assert _get_api_key() == "file-key-456"

    def test_missing_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.delenv("READWISE_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_KEY=nope\n")
        with (
            patch("readwise_sdk.mcp.server.os.path.expanduser", return_value=str(env_file)),
            pytest.raises(RuntimeError, match="READWISE_API_KEY not found"),
        ):
            _get_api_key()


class TestParseIsoDatetime:
    def test_valid(self) -> None:
        dt = _parse_iso_datetime("2025-01-15T10:30:00")
        assert dt is not None
        assert dt.year == 2025

    def test_none(self) -> None:
        assert _parse_iso_datetime(None) is None

    def test_empty(self) -> None:
        assert _parse_iso_datetime("") is None

    def test_invalid(self) -> None:
        assert _parse_iso_datetime("not-a-date") is None


class TestJsonResult:
    def test_serializes_dict(self) -> None:
        result = _json_result({"id": "abc", "count": 42})
        parsed = json.loads(result)
        assert parsed == {"id": "abc", "count": 42}

    def test_serializes_list(self) -> None:
        result = _json_result([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Tool tests with respx mocking
# ---------------------------------------------------------------------------

V3_BASE = "https://readwise.io/api/v3"
V2_BASE = "https://readwise.io/api/v2"


@pytest.mark.asyncio
class TestSaveToReader:
    @respx.mock
    async def test_save_url(self) -> None:
        respx.post(f"{V3_BASE}/save/").mock(
            return_value=httpx.Response(
                201,
                json={"id": "doc-1", "url": "https://read.readwise.io/read/doc-1"},
            )
        )
        result = json.loads(await save_to_reader(url="https://example.com/article"))
        assert result["id"] == "doc-1"
        assert "url" in result

    @respx.mock
    async def test_save_with_html(self) -> None:
        respx.post(f"{V3_BASE}/save/").mock(
            return_value=httpx.Response(
                201,
                json={"id": "doc-2", "url": "https://read.readwise.io/read/doc-2"},
            )
        )
        result = json.loads(
            await save_to_reader(
                url="https://local-upload.example.com/test",
                title="My Document",
                html="<p>Content here</p>",
                tags=["test"],
            )
        )
        assert result["id"] == "doc-2"

    async def test_invalid_location(self) -> None:
        result = json.loads(await save_to_reader(url="https://example.com", location="invalid"))
        assert "error" in result
        assert "Invalid location" in result["error"]


@pytest.mark.asyncio
class TestSearchDocuments:
    @respx.mock
    async def test_basic_search(self) -> None:
        respx.get(f"{V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc-1",
                            "url": "https://read.readwise.io/read/doc-1",
                            "title": "Test Article",
                            "author": "Author",
                            "category": "article",
                            "location": "new",
                            "tags": [],
                        }
                    ],
                    "nextPageCursor": None,
                },
            )
        )
        result = json.loads(await search_documents(limit=5))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Test Article"

    @respx.mock
    async def test_search_with_query_filter(self) -> None:
        respx.get(f"{V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc-1",
                            "url": "https://r.io/1",
                            "title": "Python Testing Guide",
                            "category": "article",
                            "location": "new",
                            "tags": [],
                        },
                        {
                            "id": "doc-2",
                            "url": "https://r.io/2",
                            "title": "Rust Programming",
                            "category": "article",
                            "location": "new",
                            "tags": [],
                        },
                    ],
                    "nextPageCursor": None,
                },
            )
        )
        result = json.loads(await search_documents(query="Python"))
        assert len(result) == 1
        assert result[0]["title"] == "Python Testing Guide"

    async def test_invalid_location(self) -> None:
        result = json.loads(await search_documents(location="bogus"))
        assert "error" in result


@pytest.mark.asyncio
class TestGetDocument:
    @respx.mock
    async def test_found(self) -> None:
        respx.get(f"{V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc-1",
                            "url": "https://read.readwise.io/read/doc-1",
                            "title": "Full Article",
                            "content": "<p>Full HTML content</p>",
                            "summary": "A test article",
                            "category": "article",
                            "location": "later",
                            "tags": ["test"],
                        }
                    ],
                    "nextPageCursor": None,
                },
            )
        )
        result = json.loads(await get_document(document_id="doc-1"))
        assert result["title"] == "Full Article"
        assert result["content"] == "<p>Full HTML content</p>"

    @respx.mock
    async def test_not_found(self) -> None:
        respx.get(f"{V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )
        result = json.loads(await get_document(document_id="no-such-doc"))
        assert "error" in result
        assert "not found" in result["error"]


@pytest.mark.asyncio
class TestUpdateDocument:
    @respx.mock
    async def test_move_to_archive(self) -> None:
        respx.patch(f"{V3_BASE}/update/doc-1/").mock(
            return_value=httpx.Response(
                200,
                json={"id": "doc-1", "url": "https://read.readwise.io/read/doc-1"},
            )
        )
        result = json.loads(await update_document(document_id="doc-1", location="archive"))
        assert result["id"] == "doc-1"

    async def test_invalid_location(self) -> None:
        result = json.loads(await update_document(document_id="doc-1", location="nowhere"))
        assert "error" in result


@pytest.mark.asyncio
class TestDeleteDocument:
    @respx.mock
    async def test_delete_success(self) -> None:
        respx.delete(f"{V3_BASE}/delete/doc-1/").mock(return_value=httpx.Response(204))
        result = json.loads(await delete_document(document_id="doc-1"))
        assert result["deleted"] == "doc-1"


@pytest.mark.asyncio
class TestGetHighlights:
    @respx.mock
    async def test_list_highlights(self) -> None:
        respx.get(f"{V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 1,
                    "next": None,
                    "results": [
                        {
                            "id": 101,
                            "text": "Important insight from the book",
                            "note": "My note",
                            "book_id": 42,
                            "color": "yellow",
                            "tags": [{"id": 1, "name": "insight"}],
                        }
                    ],
                },
            )
        )
        result = json.loads(await get_highlights(limit=10))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["text"] == "Important insight from the book"

    @respx.mock
    async def test_query_filter(self) -> None:
        respx.get(f"{V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": None,
                    "results": [
                        {"id": 1, "text": "Python is great", "tags": []},
                        {"id": 2, "text": "Rust is fast", "tags": []},
                    ],
                },
            )
        )
        result = json.loads(await get_highlights(query="Python"))
        assert len(result) == 1
        assert "Python" in result[0]["text"]


@pytest.mark.asyncio
class TestExportHighlights:
    @respx.mock
    async def test_export(self) -> None:
        respx.get(f"{V2_BASE}/export/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "user_book_id": 42,
                            "title": "Test Book",
                            "author": "Author Name",
                            "category": "books",
                            "highlights": [
                                {"id": 1, "text": "A highlight", "tags": []},
                                {"id": 2, "text": "Another highlight", "tags": []},
                            ],
                        }
                    ],
                    "nextPageCursor": None,
                },
            )
        )
        result = json.loads(await export_highlights(limit=5))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Test Book"
        assert len(result[0]["highlights"]) == 2


@pytest.mark.asyncio
class TestCreateHighlight:
    @respx.mock
    async def test_create(self) -> None:
        respx.post(f"{V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json=[{"modified_highlights": [999]}],
            )
        )
        result = json.loads(
            await create_highlight(
                text="Test highlight text",
                title="My Book",
                author="Author",
            )
        )
        assert result["created_highlight_ids"] == [999]

    async def test_invalid_category(self) -> None:
        result = json.loads(await create_highlight(text="Some text", category="invalid"))
        assert "error" in result


@pytest.mark.asyncio
class TestGetBooks:
    @respx.mock
    async def test_list_books(self) -> None:
        respx.get(f"{V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 1,
                    "next": None,
                    "results": [
                        {
                            "id": 42,
                            "title": "The Art of Testing",
                            "author": "Jane Doe",
                            "category": "books",
                            "num_highlights": 15,
                            "source": "kindle",
                            "tags": [],
                        }
                    ],
                },
            )
        )
        result = json.loads(await get_books(limit=10))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "The Art of Testing"

    @respx.mock
    async def test_query_filter(self) -> None:
        respx.get(f"{V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": None,
                    "results": [
                        {"id": 1, "title": "Python Cookbook", "num_highlights": 5, "tags": []},
                        {"id": 2, "title": "Rust Handbook", "num_highlights": 3, "tags": []},
                    ],
                },
            )
        )
        result = json.loads(await get_books(query="Python"))
        assert len(result) == 1
        assert result[0]["title"] == "Python Cookbook"

    async def test_invalid_category(self) -> None:
        result = json.loads(await get_books(category="invalid"))
        assert "error" in result
