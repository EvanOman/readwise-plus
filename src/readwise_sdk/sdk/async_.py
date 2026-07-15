"""Preferred asynchronous SDK facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from readwise_sdk.client import AsyncReadwiseClient
from readwise_sdk.config import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_BACKOFF, DEFAULT_TIMEOUT
from readwise_sdk.operations import (
    BookOperations,
    DigestOperations,
    DocumentOperations,
    HighlightOperations,
    ReadwiseService,
    SyncOperations,
    TagOperations,
)
from readwise_sdk.resources.v2 import (
    AsyncBooksResource,
    AsyncExportResource,
    AsyncHighlightsResource,
    AsyncTagsResource,
)
from readwise_sdk.resources.v3 import AsyncDocumentsResource

if TYPE_CHECKING:
    from readwise_sdk.v2.async_client import AsyncReadwiseV2Client
    from readwise_sdk.v3.async_client import AsyncReadwiseV3Client


class _AsyncRawClients:
    """Expose the existing versioned clients through an explicit escape hatch."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        self._client = client

    @property
    def v2(self) -> AsyncReadwiseV2Client:
        """Return the low-level asynchronous Readwise v2 client."""
        return self._client.v2

    @property
    def v3(self) -> AsyncReadwiseV3Client:
        """Return the low-level asynchronous Reader v3 client."""
        return self._client.v3


class AsyncReadwise:
    """Concept-oriented asynchronous Readwise SDK.

    Example::

        from readwise_sdk import AsyncReadwise
        from readwise_sdk.models import DocumentSearch

        async with AsyncReadwise() as readwise:
            result = await readwise.documents.search(DocumentSearch(query="python"))

    Use ``readwise.raw.v2`` or ``readwise.raw.v3`` for low-level API access.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> None:
        """Compose canonical operations and raw clients over one transport."""
        self._client = AsyncReadwiseClient(
            api_key,
            timeout,
            max_retries,
            retry_backoff,
        )
        transport = self._client._transport
        highlights = AsyncHighlightsResource(transport)
        tags = AsyncTagsResource(transport)
        books = AsyncBooksResource(transport)
        documents = AsyncDocumentsResource(transport)
        self._service = ReadwiseService(
            documents=documents,
            highlights=highlights,
            highlight_tags=tags,
            export=AsyncExportResource(transport),
            books=books,
            book_highlights=highlights,
            tag_highlights=highlights,
            tag_mutations=tags,
            digest_highlights=highlights,
            digest_books=books,
            sync_highlights=highlights,
            sync_books=books,
            sync_documents=documents,
        )
        self._raw = _AsyncRawClients(self._client)

    @property
    def documents(self) -> DocumentOperations:
        """Return canonical Reader document operations."""
        return self._service.documents

    @property
    def highlights(self) -> HighlightOperations:
        """Return canonical Readwise highlight operations."""
        return self._service.highlights

    @property
    def books(self) -> BookOperations:
        """Return canonical Readwise book operations."""
        return self._service.books

    @property
    def tags(self) -> TagOperations:
        """Return canonical Readwise tag operations."""
        return self._service.tags

    @property
    def digests(self) -> DigestOperations:
        """Return canonical Readwise digest data operations."""
        return self._service.digests

    @property
    def sync(self) -> SyncOperations:
        """Return canonical synchronization operations."""
        return self._service.sync

    @property
    def raw(self) -> _AsyncRawClients:
        """Return low-level versioned clients for advanced API access."""
        return self._raw

    async def close(self) -> None:
        """Close the shared asynchronous transport."""
        await self._client.close()

    async def __aenter__(self) -> AsyncReadwise:
        """Enter the facade context and return this instance."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the shared transport when leaving the facade context."""
        await self.close()


__all__ = ["AsyncReadwise"]
