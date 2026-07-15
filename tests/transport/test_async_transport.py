"""Tests for the canonical asynchronous transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from readwise_sdk.config import ClientConfig
from readwise_sdk.transport.async_ import AsyncTransport


@respx.mock
@pytest.mark.asyncio
async def test_async_transport_builds_authenticated_requests_from_config() -> None:
    """The transport owns the canonical async request path and lifecycle."""
    url = "https://example.test/items/"
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"ok": True}))
    transport = AsyncTransport(
        ClientConfig(
            api_key="test-token",
            timeout=7.5,
            user_agent="readwise-plus/test",
        )
    )

    response = await transport.get(url, params={"page": 2})

    assert response.json() == {"ok": True}
    assert route.calls.last.request.headers["Authorization"] == "Token test-token"
    assert route.calls.last.request.headers["Content-Type"] == "application/json"
    assert route.calls.last.request.headers["User-Agent"] == "readwise-plus/test"
    assert str(route.calls.last.request.url) == f"{url}?page=2"

    raw_client = transport.client
    await transport.close()
    assert raw_client.is_closed is True
    assert transport.raw_client is None
