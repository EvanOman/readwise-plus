"""Characterize construction, composition, and lifecycle of public clients."""

from __future__ import annotations

import httpx
import pytest

from readwise_sdk.client import AsyncReadwiseClient, ReadwiseClient
from readwise_sdk.exceptions import AuthenticationError
from readwise_sdk.v2.async_client import AsyncReadwiseV2Client
from readwise_sdk.v2.client import ReadwiseV2Client
from readwise_sdk.v3.async_client import AsyncReadwiseV3Client
from readwise_sdk.v3.client import ReadwiseV3Client


def test_sync_client_constructor_and_composed_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor settings and lazy cached v2/v3 resources are observable."""
    monkeypatch.delenv("READWISE_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="API key is required"):
        ReadwiseClient()

    client = ReadwiseClient("token", 12.5, 7, 1.25)
    assert (client.api_key, client.timeout, client.max_retries, client.retry_backoff) == (
        "token",
        12.5,
        7,
        1.25,
    )
    assert isinstance(client.v2, ReadwiseV2Client)
    assert isinstance(client.v3, ReadwiseV3Client)
    assert client.v2 is client.v2
    assert client.v3 is client.v3


def test_sync_client_context_manager_returns_self_and_closes_transport() -> None:
    """The sync context manager closes an initialized transport on exit."""
    client = ReadwiseClient(api_key="token")
    with client as entered:
        transport = entered.client
        assert entered is client
        assert isinstance(transport, httpx.Client)
        assert transport.is_closed is False

    assert transport.is_closed is True
    assert client._client is None


def test_sync_create_optional_defers_missing_key_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_optional permits construction but not requests without a key."""
    monkeypatch.delenv("READWISE_API_KEY", raising=False)
    client = ReadwiseClient.create_optional(timeout=9, max_retries=4, retry_backoff=2)
    assert client.is_configured is False
    assert client.api_key is None
    assert (client.timeout, client.max_retries, client.retry_backoff) == (9, 4, 2)
    with pytest.raises(AuthenticationError, match="API key is required"):
        client.get("https://readwise.io/api/v2/highlights/")


def test_async_client_constructor_and_composed_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async construction mirrors sync construction and caches async resources."""
    monkeypatch.delenv("READWISE_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="API key is required"):
        AsyncReadwiseClient()

    client = AsyncReadwiseClient("token", 12.5, 7, 1.25)
    assert (client.api_key, client.timeout, client.max_retries, client.retry_backoff) == (
        "token",
        12.5,
        7,
        1.25,
    )
    assert isinstance(client.v2, AsyncReadwiseV2Client)
    assert isinstance(client.v3, AsyncReadwiseV3Client)
    assert client.v2 is client.v2
    assert client.v3 is client.v3


@pytest.mark.asyncio
async def test_async_client_context_manager_returns_self_and_closes_transport() -> None:
    """The async context manager closes an initialized transport on exit."""
    client = AsyncReadwiseClient(api_key="token")
    async with client as entered:
        transport = entered.client
        assert entered is client
        assert isinstance(transport, httpx.AsyncClient)
        assert transport.is_closed is False

    assert transport.is_closed is True
    assert client._client is None


@pytest.mark.asyncio
async def test_async_create_optional_defers_missing_key_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async create_optional also defers authentication until request time."""
    monkeypatch.delenv("READWISE_API_KEY", raising=False)
    client = AsyncReadwiseClient.create_optional(timeout=9, max_retries=4, retry_backoff=2)
    assert client.is_configured is False
    assert client.api_key is None
    assert (client.timeout, client.max_retries, client.retry_backoff) == (9, 4, 2)
    with pytest.raises(AuthenticationError, match="API key is required"):
        await client.get("https://readwise.io/api/v2/highlights/")
