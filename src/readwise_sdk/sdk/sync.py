"""Preferred synchronous SDK facade over the async-first operation service."""

from __future__ import annotations

import builtins
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from datetime import datetime
from functools import partial
from threading import Lock
from typing import TYPE_CHECKING, Any

from anyio.from_thread import BlockingPortal, start_blocking_portal

from readwise_sdk.client import ReadwiseClient
from readwise_sdk.config import DEFAULT_MAX_RETRIES, DEFAULT_RETRY_BACKOFF, DEFAULT_TIMEOUT
from readwise_sdk.models import BookSearch, BulkResult, DocumentSearch, DocumentSearchResult
from readwise_sdk.models.queries import HighlightSearch
from readwise_sdk.operations import (
    BookSearchResult,
    BookWithHighlights,
    DocumentStatistics,
    HighlightCreateResult,
    HighlightDeleteResult,
    HighlightExportResult,
    HighlightPushInput,
    HighlightPushResult,
    HighlightSearchResult,
    HighlightUpdateInput,
    HighlightUpdateResult,
    ReadingStatistics,
)
from readwise_sdk.sdk.async_ import AsyncReadwise
from readwise_sdk.v2.models import Book, BookCategory, Highlight, HighlightCreate, HighlightUpdate
from readwise_sdk.v3.models import (
    CreateDocumentResult,
    Document,
    DocumentCreate,
    DocumentLocation,
    DocumentUpdate,
)

if TYPE_CHECKING:
    from readwise_sdk.operations import BookOperations, DocumentOperations, HighlightOperations
    from readwise_sdk.v2.client import ReadwiseV2Client
    from readwise_sdk.v3.client import ReadwiseV3Client


class _SyncRawClients:
    """Expose the existing native synchronous clients as the raw escape hatch."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client

    @property
    def v2(self) -> ReadwiseV2Client:
        """Return the low-level synchronous Readwise v2 client."""
        return self._client.v2

    @property
    def v3(self) -> ReadwiseV3Client:
        """Return the low-level synchronous Reader v3 client."""
        return self._client.v3


class _SyncOperationGroup:
    """Base for explicit synchronous adapters over one async operation group."""

    def __init__(self, owner: Readwise) -> None:
        self._owner = owner

    def _call[T](
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        return self._owner._call(operation, *args, **kwargs)


class _SyncDocumentOperations(_SyncOperationGroup):
    """Synchronous adapter for every bounded document operation."""

    def __init__(self, owner: Readwise, operations: DocumentOperations) -> None:
        super().__init__(owner)
        self._operations = operations

    def search(self, search: DocumentSearch) -> DocumentSearchResult:
        return self._call(self._operations.search, search)

    def get(self, document_id: str, *, with_content: bool = False) -> Document | None:
        return self._call(
            self._operations.get,
            document_id,
            with_content=with_content,
        )

    def save(self, document: DocumentCreate) -> CreateDocumentResult:
        return self._call(self._operations.save, document)

    def update(
        self,
        document_id: str,
        update: DocumentUpdate,
    ) -> CreateDocumentResult:
        return self._call(self._operations.update, document_id, update)

    def delete(self, document_id: str) -> None:
        return self._call(self._operations.delete, document_id)

    def move(
        self,
        document_id: str,
        location: DocumentLocation,
    ) -> CreateDocumentResult:
        return self._call(self._operations.move, document_id, location)

    def set_tags(self, document_id: str, tags: list[str]) -> CreateDocumentResult:
        return self._call(self._operations.set_tags, document_id, tags)

    def add_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        return self._call(self._operations.add_tag, document_id, tag)

    def remove_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        return self._call(self._operations.remove_tag, document_id, tag)

    def inbox(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[Document]:
        return self._call(
            self._operations.inbox,
            limit=limit,
            with_content=with_content,
        )

    def later(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[Document]:
        return self._call(
            self._operations.later,
            limit=limit,
            with_content=with_content,
        )

    def archive(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[Document]:
        return self._call(
            self._operations.archive,
            limit=limit,
            with_content=with_content,
        )

    def statistics(self) -> DocumentStatistics:
        return self._call(self._operations.statistics)

    def bulk_move(
        self,
        document_ids: list[str],
        location: DocumentLocation,
    ) -> BulkResult[str]:
        return self._call(self._operations.bulk_move, document_ids, location)

    def bulk_set_tags(
        self,
        document_ids: list[str],
        tags: list[str],
    ) -> BulkResult[str]:
        return self._call(self._operations.bulk_set_tags, document_ids, tags)


class _SyncHighlightOperations(_SyncOperationGroup):
    """Synchronous adapter for every bounded highlight operation."""

    def __init__(self, owner: Readwise, operations: HighlightOperations) -> None:
        super().__init__(owner)
        self._operations = operations

    def search(self, search: HighlightSearch) -> HighlightSearchResult:
        return self._call(self._operations.search, search)

    def list(
        self,
        *,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[Highlight]:
        return self._call(
            self._operations.list,
            book_id=book_id,
            updated_after=updated_after,
            updated_before=updated_before,
            highlighted_after=highlighted_after,
            highlighted_before=highlighted_before,
            limit=limit,
        )

    def get(self, highlight_id: int) -> Highlight:
        return self._call(self._operations.get, highlight_id)

    def create(self, highlight: HighlightCreate) -> builtins.list[int]:
        return self._call(self._operations.create, highlight)

    def create_from_fields(
        self,
        *,
        text: str,
        title: str | None = None,
        author: str | None = None,
        source_url: str | None = None,
        note: str | None = None,
        category: str | BookCategory | None = None,
        highlighted_at: datetime | None = None,
    ) -> HighlightCreateResult:
        return self._call(
            self._operations.create_from_fields,
            text=text,
            title=title,
            author=author,
            source_url=source_url,
            note=note,
            category=category,
            highlighted_at=highlighted_at,
        )

    def push_batch(
        self,
        highlights: builtins.list[HighlightPushInput],
        *,
        auto_truncate: bool = True,
    ) -> builtins.list[HighlightPushResult]:
        return self._call(
            self._operations.push_batch,
            highlights,
            auto_truncate=auto_truncate,
        )

    def update(self, highlight_id: int, update: HighlightUpdate) -> Highlight:
        return self._call(self._operations.update, highlight_id, update)

    def update_batch(
        self,
        updates: builtins.list[HighlightUpdateInput],
        *,
        auto_truncate: bool = True,
    ) -> builtins.list[HighlightUpdateResult]:
        return self._call(
            self._operations.update_batch,
            updates,
            auto_truncate=auto_truncate,
        )

    def delete(self, highlight_id: int) -> None:
        return self._call(self._operations.delete, highlight_id)

    def delete_batch(
        self,
        highlight_ids: builtins.list[int],
    ) -> builtins.list[HighlightDeleteResult]:
        return self._call(self._operations.delete_batch, highlight_ids)

    def search_items(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> builtins.list[Highlight]:
        return self._call(
            self._operations.search_items,
            query,
            case_sensitive=case_sensitive,
        )

    def since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> builtins.list[Highlight]:
        return self._call(
            self._operations.since,
            days=days,
            hours=hours,
            since=since,
        )

    def with_notes(self) -> builtins.list[Highlight]:
        return self._call(self._operations.with_notes)

    def count(self) -> int:
        return self._call(self._operations.count)

    def bulk_tag(self, highlight_ids: builtins.list[int], tag: str) -> BulkResult[int]:
        return self._call(self._operations.bulk_tag, highlight_ids, tag)

    def bulk_untag(self, highlight_ids: builtins.list[int], tag: str) -> BulkResult[int]:
        return self._call(self._operations.bulk_untag, highlight_ids, tag)

    def export(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: builtins.list[int] | None = None,
        limit: int = 20,
    ) -> HighlightExportResult:
        return self._call(
            self._operations.export,
            updated_after=updated_after,
            book_ids=book_ids,
            limit=limit,
        )


class _SyncBookOperations(_SyncOperationGroup):
    """Synchronous adapter for every bounded book operation."""

    def __init__(self, owner: Readwise, operations: BookOperations) -> None:
        super().__init__(owner)
        self._operations = operations

    def search(self, search: BookSearch) -> BookSearchResult:
        return self._call(self._operations.search, search)

    def list(
        self,
        *,
        category: BookCategory | None = None,
        source: str | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        last_highlight_after: datetime | None = None,
        last_highlight_before: datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[Book]:
        return self._call(
            self._operations.list,
            category=category,
            source=source,
            updated_after=updated_after,
            updated_before=updated_before,
            last_highlight_after=last_highlight_after,
            last_highlight_before=last_highlight_before,
            limit=limit,
        )

    def get(self, book_id: int) -> Book:
        return self._call(self._operations.get, book_id)

    def with_highlights(self, book_id: int) -> BookWithHighlights:
        return self._call(self._operations.with_highlights, book_id)

    def recent(
        self,
        *,
        days: int | None = None,
        limit: int | None = None,
    ) -> builtins.list[Book]:
        return self._call(self._operations.recent, days=days, limit=limit)

    def statistics(self) -> ReadingStatistics:
        return self._call(self._operations.statistics)

    def search_items(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> builtins.list[Book]:
        return self._call(
            self._operations.search_items,
            query,
            case_sensitive=case_sensitive,
        )

    def count(self) -> int:
        return self._call(self._operations.count)


class Readwise:
    """Concept-oriented synchronous Readwise SDK.

    The facade owns a dedicated AnyIO blocking portal and routes every concept
    operation to the canonical asynchronous service on the portal's event-loop
    thread. Use the facade as a context manager so that it can close both the
    asynchronous service client and the portal deterministically.

    Example::

        from readwise_sdk import Readwise
        from readwise_sdk.models import DocumentSearch

        with Readwise() as readwise:
            result = readwise.documents.search(DocumentSearch(query="python"))

    ``readwise.raw`` intentionally retains the existing native synchronous
    clients, including their legacy iterator APIs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> None:
        """Compose sync adapters and owned clients without starting a thread yet."""
        self._async = AsyncReadwise(api_key, timeout, max_retries, retry_backoff)
        raw_client = ReadwiseClient(api_key, timeout, max_retries, retry_backoff)
        self._raw = _SyncRawClients(raw_client)
        self._documents = _SyncDocumentOperations(self, self._async.documents)
        self._highlights = _SyncHighlightOperations(self, self._async.highlights)
        self._books = _SyncBookOperations(self, self._async.books)
        self._portal: BlockingPortal | None = None
        self._portal_context: AbstractContextManager[BlockingPortal] | None = None
        self._lifecycle_lock = Lock()

    @property
    def documents(self) -> _SyncDocumentOperations:
        """Return synchronous canonical Reader document operations."""
        return self._documents

    @property
    def highlights(self) -> _SyncHighlightOperations:
        """Return synchronous canonical Readwise highlight operations."""
        return self._highlights

    @property
    def books(self) -> _SyncBookOperations:
        """Return synchronous canonical Readwise book operations."""
        return self._books

    # tags, digests, and sync mirror AsyncReadwise by remaining deferred.

    @property
    def raw(self) -> _SyncRawClients:
        """Return the existing low-level native synchronous clients."""
        return self._raw

    def _call[T](
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        portal = self._portal
        if portal is None:
            raise RuntimeError("Readwise is not open; use it as a context manager")
        if kwargs:
            return portal.call(partial(operation, *args, **kwargs))
        return portal.call(operation, *args)

    def close(self) -> None:
        """Close the async client and cancel portal work before joining its thread."""
        with self._lifecycle_lock:
            portal = self._portal
            portal_context = self._portal_context
            if portal is None or portal_context is None:
                self._raw._client.close()
                return

            # Prevent new calls while the owned resources are being torn down.
            self._portal = None
            self._portal_context = None
            try:
                portal.call(self._async.close)
            finally:
                try:
                    shutdown = RuntimeError("Readwise portal is shutting down")
                    portal_context.__exit__(
                        type(shutdown),
                        shutdown,
                        shutdown.__traceback__,
                    )
                finally:
                    self._raw._client.close()

    def __enter__(self) -> Readwise:
        """Start the facade's dedicated event-loop thread and return this instance."""
        with self._lifecycle_lock:
            if self._portal is not None:
                raise RuntimeError("Readwise is already open")
            portal_context = start_blocking_portal(name="readwise-sdk-portal")
            portal = portal_context.__enter__()
            self._portal_context = portal_context
            self._portal = portal
        return self

    def __exit__(self, *args: Any) -> None:
        """Close all owned lifecycle resources when leaving the context."""
        self.close()


__all__ = ["Readwise"]
