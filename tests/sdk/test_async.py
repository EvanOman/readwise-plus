"""Public contract tests for the preferred asynchronous SDK facade."""

from __future__ import annotations

import httpx
import pytest

from readwise_sdk.operations import (
    BookOperations,
    DigestOperations,
    DocumentOperations,
    HighlightOperations,
    TagOperations,
)
from readwise_sdk.v2.async_client import AsyncReadwiseV2Client
from readwise_sdk.v3.async_client import AsyncReadwiseV3Client


def test_async_readwise_is_importable_from_the_package_root() -> None:
    """The preferred async facade is available through the documented import."""
    from readwise_sdk import AsyncReadwise

    assert AsyncReadwise.__module__ == "readwise_sdk.sdk.async_"


def test_async_readwise_constructs_canonical_operations() -> None:
    """Construction composes all operation groups that exist today."""
    from readwise_sdk import AsyncReadwise

    readwise = AsyncReadwise("token", 12.5, 7, 1.25)

    assert isinstance(readwise.documents, DocumentOperations)
    assert isinstance(readwise.highlights, HighlightOperations)
    assert isinstance(readwise.books, BookOperations)
    assert isinstance(readwise.tags, TagOperations)
    assert isinstance(readwise.digests, DigestOperations)
    assert (
        readwise._client.api_key,
        readwise._client.timeout,
        readwise._client.max_retries,
        readwise._client.retry_backoff,
    ) == ("token", 12.5, 7, 1.25)


@pytest.mark.parametrize("name", ["documents", "highlights", "books", "tags", "digests"])
def test_concept_attributes_delegate_to_the_canonical_service(name: str) -> None:
    """Each public concept attribute is the operation group owned by the service."""
    from readwise_sdk import AsyncReadwise

    readwise = AsyncReadwise(api_key="token")

    assert getattr(readwise, name) is getattr(readwise._service, name)


def test_raw_exposes_cached_versioned_clients_over_the_shared_client() -> None:
    """The low-level escape hatch reaches both existing resource client facades."""
    from readwise_sdk import AsyncReadwise

    readwise = AsyncReadwise(api_key="token")

    assert isinstance(readwise.raw.v2, AsyncReadwiseV2Client)
    assert isinstance(readwise.raw.v3, AsyncReadwiseV3Client)
    assert readwise.raw.v2 is readwise.raw.v2
    assert readwise.raw.v3 is readwise.raw.v3
    assert readwise.raw.v2._client is readwise._client
    assert readwise.raw.v3._client is readwise._client


def test_sync_operation_group_remains_deferred() -> None:
    """Only synchronization remains deferred after tag and digest consolidation."""
    from readwise_sdk import AsyncReadwise

    readwise = AsyncReadwise(api_key="token")

    assert not hasattr(readwise, "sync")


@pytest.mark.asyncio
async def test_async_context_manager_returns_self_and_closes_shared_transport() -> None:
    """Leaving the facade context closes the transport used by operations and raw clients."""
    from readwise_sdk import AsyncReadwise

    readwise = AsyncReadwise(api_key="token")

    async with readwise as entered:
        transport = entered._client.client
        assert entered is readwise
        assert isinstance(transport, httpx.AsyncClient)
        assert transport.is_closed is False

    assert transport.is_closed is True
    assert readwise._client._client is None
