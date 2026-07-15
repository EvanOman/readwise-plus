"""Live tests against the real Readwise API.

Run with: uv run pytest -m live
Requires READWISE_API_KEY in env or ~/.env.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("mcp")

from readwise_sdk.mcp.server import (
    delete_document,
    export_highlights,
    get_books,
    get_document,
    get_highlights,
    save_to_reader,
    search_documents,
)

pytestmark = pytest.mark.live


@pytest.mark.asyncio
class TestLiveDocuments:
    """Test document operations against the real Reader API."""

    @pytest.mark.usefixtures("_use_real_api_key")
    async def test_search_inbox(self) -> None:
        """List documents in the inbox — read-only, always safe."""
        raw = await search_documents(location="new", limit=3)
        result = json.loads(raw)
        assert isinstance(result, list)
        # Inbox might be empty, but should not error
        if result:
            doc = result[0]
            assert "id" in doc
            assert "title" in doc

    @pytest.mark.usefixtures("_use_real_api_key")
    async def test_save_and_cleanup(self) -> None:
        """Save a test URL to Reader, verify it exists, then delete it."""
        test_url = "https://httpbin.org/html"

        # Save
        save_raw = await save_to_reader(
            url=test_url,
            tags=["mcp-test"],
            notes="Automated MCP server test — safe to delete",
        )
        save_result = json.loads(save_raw)
        assert "id" in save_result, f"Save failed: {save_result}"
        doc_id = save_result["id"]

        # Get — verify it was saved
        get_raw = await get_document(document_id=doc_id)
        get_result = json.loads(get_raw)
        assert get_result.get("id") == doc_id

        # Clean up
        del_raw = await delete_document(document_id=doc_id)
        del_result = json.loads(del_raw)
        assert del_result.get("deleted") == doc_id


@pytest.mark.asyncio
class TestLiveHighlights:
    """Test highlight operations — read-only."""

    @pytest.mark.usefixtures("_use_real_api_key")
    async def test_list_highlights(self) -> None:
        raw = await get_highlights(limit=3)
        result = json.loads(raw)
        assert isinstance(result, list)
        if result:
            h = result[0]
            assert "id" in h
            assert "text" in h

    @pytest.mark.usefixtures("_use_real_api_key")
    async def test_export_highlights(self) -> None:
        raw = await export_highlights(limit=2)
        result = json.loads(raw)
        assert isinstance(result, list)
        if result:
            book = result[0]
            assert "title" in book
            assert "highlights" in book


@pytest.mark.asyncio
class TestLiveBooks:
    """Test book listing — read-only."""

    @pytest.mark.usefixtures("_use_real_api_key")
    async def test_list_books(self) -> None:
        raw = await get_books(limit=3)
        result = json.loads(raw)
        assert isinstance(result, list)
        if result:
            book = result[0]
            assert "id" in book
            assert "title" in book
