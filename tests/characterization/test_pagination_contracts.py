"""Lock the three pagination cursor dialects and exact request sequences."""

from __future__ import annotations

import httpx
import pytest
import respx

from readwise_sdk.client import (
    READWISE_API_V2_BASE,
    READWISE_API_V3_BASE,
    AsyncReadwiseClient,
    ReadwiseClient,
)


def _urls(route: respx.Route) -> list[str]:
    return [str(call.request.url) for call in route.calls]


@respx.mock
def test_sync_v2_next_url_replaces_the_request_url_and_parameters() -> None:
    """Standard v2 `next` is a full URL whose query replaces prior params."""
    route = respx.get(url__startswith=f"{READWISE_API_V2_BASE}/highlights/").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "results": [],
                    "next": f"{READWISE_API_V2_BASE}/highlights/?page=2",
                },
            ),
            httpx.Response(200, json={"results": [], "next": None}),
        ]
    )

    list(ReadwiseClient("token").v2.list_highlights(page_size=25, book_id=7))

    assert _urls(route) == [
        f"{READWISE_API_V2_BASE}/highlights/?page_size=25&book_id=7",
        f"{READWISE_API_V2_BASE}/highlights/?page=2",
    ]


@respx.mock
def test_sync_v2_export_integer_cursor_becomes_page_cursor() -> None:
    """The v2 export integer cursor is stringified into `pageCursor`."""
    route = respx.get(f"{READWISE_API_V2_BASE}/export/").mock(
        side_effect=[
            httpx.Response(200, json={"results": [], "nextPageCursor": 42}),
            httpx.Response(200, json={"results": [], "nextPageCursor": None}),
        ]
    )

    list(ReadwiseClient("token").v2.export_highlights(book_ids=[3, 4]))

    assert _urls(route) == [
        f"{READWISE_API_V2_BASE}/export/?ids=3%2C4",
        f"{READWISE_API_V2_BASE}/export/?ids=3%2C4&pageCursor=42",
    ]


@respx.mock
def test_sync_v3_cursor_becomes_page_cursor_and_retains_filters() -> None:
    """Reader's `nextPageCursor` retains filters and adds `pageCursor`."""
    route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
        side_effect=[
            httpx.Response(200, json={"results": [], "nextPageCursor": "reader-cursor"}),
            httpx.Response(200, json={"results": [], "nextPageCursor": None}),
        ]
    )

    from readwise_sdk.v3.models import DocumentLocation

    list(ReadwiseClient("token").v3.list_documents(location=DocumentLocation.LATER))

    assert _urls(route) == [
        f"{READWISE_API_V3_BASE}/list/?location=later",
        f"{READWISE_API_V3_BASE}/list/?location=later&pageCursor=reader-cursor",
    ]


@respx.mock
@pytest.mark.asyncio
async def test_async_v2_next_url_replaces_the_request_url_and_parameters() -> None:
    """Async standard v2 pagination issues the same exact sequence."""
    route = respx.get(url__startswith=f"{READWISE_API_V2_BASE}/highlights/").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "results": [],
                    "next": f"{READWISE_API_V2_BASE}/highlights/?page=2",
                },
            ),
            httpx.Response(200, json={"results": [], "next": None}),
        ]
    )

    async with AsyncReadwiseClient("token") as client:
        _ = [item async for item in client.v2.list_highlights(page_size=25, book_id=7)]

    assert _urls(route) == [
        f"{READWISE_API_V2_BASE}/highlights/?page_size=25&book_id=7",
        f"{READWISE_API_V2_BASE}/highlights/?page=2",
    ]


@respx.mock
@pytest.mark.asyncio
async def test_async_v2_export_integer_cursor_becomes_page_cursor() -> None:
    """Async v2 export stringifies integer cursors in the same way."""
    route = respx.get(f"{READWISE_API_V2_BASE}/export/").mock(
        side_effect=[
            httpx.Response(200, json={"results": [], "nextPageCursor": 42}),
            httpx.Response(200, json={"results": [], "nextPageCursor": None}),
        ]
    )

    async with AsyncReadwiseClient("token") as client:
        _ = [item async for item in client.v2.export_highlights(book_ids=[3, 4])]

    assert _urls(route) == [
        f"{READWISE_API_V2_BASE}/export/?ids=3%2C4",
        f"{READWISE_API_V2_BASE}/export/?ids=3%2C4&pageCursor=42",
    ]


@respx.mock
@pytest.mark.asyncio
async def test_async_v3_cursor_becomes_page_cursor_and_retains_filters() -> None:
    """Async Reader pagination retains filters while adding its cursor."""
    route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
        side_effect=[
            httpx.Response(200, json={"results": [], "nextPageCursor": "reader-cursor"}),
            httpx.Response(200, json={"results": [], "nextPageCursor": None}),
        ]
    )

    from readwise_sdk.v3.models import DocumentLocation

    async with AsyncReadwiseClient("token") as client:
        _ = [item async for item in client.v3.list_documents(location=DocumentLocation.LATER)]

    assert _urls(route) == [
        f"{READWISE_API_V3_BASE}/list/?location=later",
        f"{READWISE_API_V3_BASE}/list/?location=later&pageCursor=reader-cursor",
    ]
