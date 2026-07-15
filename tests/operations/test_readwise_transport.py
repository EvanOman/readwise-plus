"""Transport-backed tests for highlight and book operations."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from readwise_sdk.config import ClientConfig
from readwise_sdk.models import BookSearch
from readwise_sdk.operations.books import BookOperations
from readwise_sdk.operations.highlights import MAX_TEXT_LENGTH, HighlightOperations
from readwise_sdk.resources.v2 import (
    AsyncBooksResource,
    AsyncExportResource,
    AsyncHighlightsResource,
    AsyncTagsResource,
)
from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.v2.models import BookCategory

V2_BASE = "https://readwise.io/api/v2"


def operation_stack() -> tuple[HighlightOperations, BookOperations, AsyncTransport]:
    """Compose real operations, resources, and transport."""
    transport = AsyncTransport(ClientConfig(api_key="token"))
    highlights = AsyncHighlightsResource(transport)
    return (
        HighlightOperations(
            highlights, AsyncTagsResource(transport), AsyncExportResource(transport)
        ),
        BookOperations(AsyncBooksResource(transport), highlights),
        transport,
    )


@respx.mock
@pytest.mark.asyncio
async def test_create_transport_sends_mcp_slice_and_category_value() -> None:
    """MCP creation policy reaches the real resource as an 8191-char non-ellipsis payload."""
    route = respx.post(f"{V2_BASE}/highlights/").mock(
        return_value=httpx.Response(200, json=[{"modified_highlights": [8]}])
    )
    highlights, _, transport = operation_stack()

    try:
        result = await highlights.create_from_fields(
            text="x" * (MAX_TEXT_LENGTH + 20),
            category="articles",
        )
    finally:
        await transport.close()

    payload = json.loads(route.calls.last.request.content)
    assert result.ids == [8]
    assert payload == {"highlights": [{"text": "x" * MAX_TEXT_LENGTH, "category": "articles"}]}


@respx.mock
@pytest.mark.asyncio
async def test_export_transport_preserves_grouping_query_and_nested_projection() -> None:
    """Export filters and grouped highlights survive the real resource boundary."""
    route = respx.get(f"{V2_BASE}/export/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "user_book_id": 7,
                        "title": "Book",
                        "highlights": [{"id": 1, "text": "Insight", "tags": []}],
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )
    highlights, _, transport = operation_stack()

    try:
        result = await highlights.export(book_ids=[7, 8])
    finally:
        await transport.close()

    assert result.items[0].book_id == 7
    assert result.items[0].highlights[0].text == "Insight"
    assert route.calls.last.request.url.params["ids"] == "7,8"


@respx.mock
@pytest.mark.asyncio
async def test_book_search_transport_keeps_filters_and_title_only_matching() -> None:
    """Book resource filters and operation-local title matching compose without drift."""
    route = respx.get(f"{V2_BASE}/books/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"id": 1, "title": "Other", "author": "Python Author"},
                    {"id": 2, "title": "Python Book", "num_highlights": 0},
                ],
                "next": None,
            },
        )
    )
    _, books, transport = operation_stack()

    try:
        result = await books.search(
            BookSearch(
                category=BookCategory.BOOKS,
                source="kindle",
                query="python",
            )
        )
    finally:
        await transport.close()

    assert [item.id for item in result.items] == [2]
    assert route.calls.last.request.url.params["category"] == "books"
    assert route.calls.last.request.url.params["source"] == "kindle"
