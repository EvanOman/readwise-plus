"""Transport-backed integration tests for canonical document operations."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from readwise_sdk.config import ClientConfig
from readwise_sdk.models import DocumentSearch
from readwise_sdk.operations.documents import DocumentOperations
from readwise_sdk.resources.v3.documents import AsyncDocumentsResource
from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.v3.models import DocumentCategory, DocumentCreate, DocumentLocation

V3_BASE = "https://readwise.io/api/v3"


def operations_with_transport() -> tuple[DocumentOperations, AsyncTransport]:
    """Compose real resource and transport layers under the operation seam."""
    transport = AsyncTransport(ClientConfig(api_key="token"))
    return DocumentOperations(AsyncDocumentsResource(transport)), transport


@respx.mock
@pytest.mark.asyncio
async def test_search_transport_keeps_single_tag_query_quirk_and_mcp_projection() -> None:
    """All tags reach the resource, whose request intentionally sends only the first."""
    route = respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "doc-1",
                        "url": "https://reader/doc-1",
                        "source_url": "https://source/article",
                        "title": "Python",
                        "location": "later",
                        "category": "article",
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )
    operations, transport = operations_with_transport()

    try:
        result = await operations.search(
            DocumentSearch(
                location=DocumentLocation.LATER,
                category=DocumentCategory.ARTICLE,
                tags=("first", "second"),
                query="python",
            )
        )
    finally:
        await transport.close()

    assert [item.url for item in result.items] == ["https://source/article"]
    assert route.calls.last.request.url.params.get_list("tag") == ["first"]
    assert "second" not in str(route.calls.last.request.url)


@respx.mock
@pytest.mark.asyncio
async def test_save_transport_preserves_buggy_category_omission() -> None:
    """The real save payload omits category while retaining the other MCP fields."""
    route = respx.post(f"{V3_BASE}/save/").mock(
        return_value=httpx.Response(201, json={"id": "doc-1", "url": "reader-url"})
    )
    operations, transport = operations_with_transport()

    try:
        result = await operations.save(
            DocumentCreate(
                url="https://example.com",
                title="Title",
                category=DocumentCategory.ARTICLE,
                location=DocumentLocation.LATER,
                tags=["tag"],
                saved_using="readwise-mcp",
            )
        )
    finally:
        await transport.close()

    assert result.id == "doc-1"
    assert json.loads(route.calls.last.request.content) == {
        "url": "https://example.com",
        "title": "Title",
        "location": "later",
        "saved_using": "readwise-mcp",
        "tags": ["tag"],
    }


@respx.mock
@pytest.mark.asyncio
async def test_add_and_remove_tag_transport_compose_get_then_patch() -> None:
    """Tag mutation fetches current tags and writes the exact merged replacement list."""
    get_route = respx.get(f"{V3_BASE}/list/").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"results": [{"id": "doc-1", "url": "https://example.com", "tags": ["one"]}]},
            ),
            httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc-1",
                            "url": "https://example.com",
                            "tags": ["one", "two", "two"],
                        }
                    ]
                },
            ),
        ]
    )
    patch_route = respx.patch(f"{V3_BASE}/update/doc-1/").mock(
        return_value=httpx.Response(200, json={"id": "doc-1", "url": "reader-url"})
    )
    operations, transport = operations_with_transport()

    try:
        await operations.add_tag("doc-1", "two")
        first_payload = json.loads(patch_route.calls.last.request.content)
        await operations.remove_tag("doc-1", "two")
        second_payload = json.loads(patch_route.calls.last.request.content)
    finally:
        await transport.close()

    assert len(get_route.calls) == 2
    assert first_payload == {"tags": ["one", "two"]}
    assert second_payload == {"tags": ["one"]}
