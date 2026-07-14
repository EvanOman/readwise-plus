"""Legacy asynchronous manager compatibility shims."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from readwise_sdk.managers.books import BookWithHighlights, ReadingStats
from readwise_sdk.managers.documents import InboxStats
from readwise_sdk.managers.sync import SyncResult, SyncState
from readwise_sdk.models import SyncCheckpoint
from readwise_sdk.models import SyncResult as CanonicalSyncResult
from readwise_sdk.operations.books import BookOperations
from readwise_sdk.operations.compat import (
    AsyncBooksResource,
    AsyncDocumentsResource,
    AsyncHighlightsResource,
    bulk_result_map,
)
from readwise_sdk.operations.documents import DocumentOperations
from readwise_sdk.operations.highlights import HighlightOperations
from readwise_sdk.operations.sync import AsyncSyncClient, SyncOperations
from readwise_sdk.state import JsonFileStateStore, MemoryStateStore
from readwise_sdk.v2.models import Book, BookCategory, Highlight, HighlightCreate
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from readwise_sdk.client import AsyncReadwiseClient


class AsyncHighlightManager:
    """Compatibility wrapper over canonical highlight operations."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        self._client = client
        resource = AsyncHighlightsResource(client)
        self._operations = HighlightOperations(resource, resource, resource)

    async def get_all_highlights(self) -> list[Highlight]:
        return await self._operations.list()

    async def get_highlights_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Highlight]:
        return await self._operations.since(days=days, hours=hours, since=since)

    async def get_highlights_by_book(self, book_id: int) -> list[Highlight]:
        return await self._operations.list(book_id=book_id)

    async def get_highlights_with_notes(self) -> list[Highlight]:
        return await self._operations.with_notes()

    async def search_highlights(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Highlight]:
        return await self._operations.search_items(query, case_sensitive=case_sensitive)

    def filter_highlights(
        self,
        predicate: Callable[[Highlight], bool],
    ) -> AsyncIterator[Highlight]:
        return self._operations.filter(predicate)

    async def bulk_tag(self, highlight_ids: list[int], tag: str) -> dict[int, bool]:
        return bulk_result_map(highlight_ids, await self._operations.bulk_tag(highlight_ids, tag))

    async def bulk_untag(self, highlight_ids: list[int], tag: str) -> dict[int, bool]:
        return bulk_result_map(highlight_ids, await self._operations.bulk_untag(highlight_ids, tag))

    async def create_highlight(
        self,
        text: str,
        *,
        title: str | None = None,
        author: str | None = None,
        note: str | None = None,
        source_url: str | None = None,
    ) -> int:
        ids = await self._operations.create(
            HighlightCreate(
                text=text,
                title=title,
                author=author,
                note=note,
                source_url=source_url,
            )
        )
        return ids[0] if ids else 0

    async def get_highlight_count(self) -> int:
        return await self._operations.count()


class AsyncBookManager:
    """Compatibility wrapper over canonical book operations."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        self._client = client
        self._operations = BookOperations(
            AsyncBooksResource(client),
            AsyncHighlightsResource(client),
        )

    async def get_all_books(self) -> list[Book]:
        return await self._operations.list()

    async def get_books_by_category(self, category: BookCategory) -> list[Book]:
        return await self._operations.list(category=category)

    async def get_books_by_source(self, source: str) -> list[Book]:
        return await self._operations.list(source=source)

    async def get_book_with_highlights(self, book_id: int) -> BookWithHighlights:
        result = await self._operations.with_highlights(book_id)
        return BookWithHighlights(book=result.book, highlights=result.highlights)

    async def get_recent_books(
        self,
        *,
        days: int | None = None,
        limit: int | None = None,
    ) -> list[Book]:
        return await self._operations.recent(days=days, limit=limit)

    async def get_reading_stats(self) -> ReadingStats:
        result = await self._operations.statistics()
        return ReadingStats(
            total_books=result.total_books,
            total_highlights=result.total_highlights,
            books_by_category=result.books_by_category,
            highlights_by_category=result.highlights_by_category,
            highlights_by_source=result.highlights_by_source,
            most_highlighted_books=result.most_highlighted_books,
            recent_books=result.recent_books,
        )

    async def search_books(self, query: str, *, case_sensitive: bool = False) -> list[Book]:
        return await self._operations.search_items(query, case_sensitive=case_sensitive)

    async def get_book_count(self) -> int:
        return await self._operations.count()


class AsyncDocumentManager:
    """Compatibility wrapper over canonical document operations."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        self._client = client
        self._operations = DocumentOperations(AsyncDocumentsResource(client, manager_compat=True))

    async def get_inbox(self) -> list[Document]:
        return await self._operations.inbox()

    async def get_reading_list(self) -> list[Document]:
        return await self._operations.later()

    async def get_archive(self) -> list[Document]:
        return await self._operations.archive()

    async def get_documents_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Document]:
        return await self._operations.since(days=days, hours=hours, since=since)

    async def move_to_later(self, document_id: str) -> None:
        await self._operations.move(document_id, DocumentLocation.LATER)

    async def archive(self, document_id: str) -> None:
        await self._operations.move(document_id, DocumentLocation.ARCHIVE)

    async def move_to_inbox(self, document_id: str) -> None:
        await self._operations.move(document_id, DocumentLocation.NEW)

    async def bulk_archive(self, document_ids: list[str]) -> dict[str, bool]:
        result = await self._operations.bulk_move(document_ids, DocumentLocation.ARCHIVE)
        return bulk_result_map(document_ids, result)

    async def bulk_tag_documents(
        self,
        document_ids: list[str],
        tags: list[str],
    ) -> dict[str, bool]:
        return bulk_result_map(
            document_ids,
            await self._operations.bulk_set_tags(document_ids, tags),
        )

    def filter_documents(
        self,
        predicate: Callable[[Document], bool],
        *,
        location: DocumentLocation | None = None,
    ) -> AsyncIterator[Document]:
        return self._operations.filter(predicate, location=location)

    async def search_documents(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        return await self._operations.search_items(
            query,
            case_sensitive=case_sensitive,
            location=location,
        )

    async def get_inbox_stats(self) -> InboxStats:
        result = await self._operations.statistics()
        return InboxStats(
            inbox_count=result.inbox_count,
            reading_list_count=result.reading_list_count,
            archive_count=result.archive_count,
            total_count=result.total_count,
            by_category=result.by_category,
            oldest_inbox_item=result.oldest_inbox_item,
            newest_inbox_item=result.newest_inbox_item,
        )

    async def get_documents_by_category(
        self,
        category: DocumentCategory,
    ) -> list[Document]:
        return await self._operations.by_category(category)

    async def get_unread_count(self) -> int:
        return await self._operations.unread_count()


class AsyncSyncManager:
    """Async compatibility wrapper over canonical synchronization operations."""

    def __init__(
        self,
        client: AsyncReadwiseClient,
        *,
        state_file: Path | str | None = None,
    ) -> None:
        self._client = client
        self._state_file = Path(state_file) if state_file else None
        self._file_store = JsonFileStateStore(self._state_file) if self._state_file else None
        self._state = self._load_state()
        self._callbacks: list[Callable[[SyncResult], None]] = []
        self._checkpoint_store = MemoryStateStore(self._checkpoint())
        self._operation = SyncOperations(
            async_client=cast(AsyncSyncClient, self._client),
            state_store=self._checkpoint_store,
        )

    def _load_state(self) -> SyncState:
        if self._file_store is not None:
            return self._file_store.load_legacy(SyncState.from_dict, SyncState)
        return SyncState()

    def _save_state(self) -> None:
        if self._file_store is not None:
            self._file_store.save_legacy(self._state.to_dict())

    @property
    def state(self) -> SyncState:
        return self._state

    def on_sync(self, callback: Callable[[SyncResult], None]) -> None:
        self._callbacks.append(callback)

    def _notify_callbacks(self, result: SyncResult) -> None:
        self._operation.notify_callbacks(self._callbacks, result)

    async def full_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        self._checkpoint_store.save(self._checkpoint())
        canonical = await self._operation.full(
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )
        return self._finish(canonical)

    async def incremental_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        self._checkpoint_store.save(self._checkpoint())
        canonical = await self._operation.incremental(
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )
        return self._finish(canonical)

    async def sync_highlights_only(self) -> SyncResult:
        return await self.incremental_sync(include_books=False, include_documents=False)

    async def sync_documents_only(self) -> SyncResult:
        return await self.incremental_sync(include_highlights=False, include_books=False)

    def reset_state(self) -> None:
        self._state = SyncState()
        self._checkpoint_store.save(SyncCheckpoint())
        self._save_state()

    def _checkpoint(self) -> SyncCheckpoint:
        return SyncCheckpoint(
            last_highlight_sync=self._state.last_highlight_sync,
            last_book_sync=self._state.last_book_sync,
            last_document_sync=self._state.last_document_sync,
            last_sync_time=self._state.last_sync_time,
        )

    def _finish(self, canonical: CanonicalSyncResult) -> SyncResult:
        checkpoint = canonical.checkpoint
        self._state.last_highlight_sync = checkpoint.last_highlight_sync
        self._state.last_book_sync = checkpoint.last_book_sync
        self._state.last_document_sync = checkpoint.last_document_sync
        self._state.last_sync_time = checkpoint.last_sync_time
        self._state.total_syncs += 1
        self._save_state()
        result = SyncResult(
            highlights=canonical.highlights,
            books=canonical.books,
            documents=canonical.documents,
            sync_time=checkpoint.last_sync_time or datetime.now(UTC),
        )
        self._notify_callbacks(result)
        return result
