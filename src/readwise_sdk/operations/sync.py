"""Canonical synchronization, batching, polling, and scheduling behavior."""

from __future__ import annotations

import inspect
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

from readwise_sdk.models import SyncCheckpoint
from readwise_sdk.models.results import SyncResult
from readwise_sdk.state import MemoryStateStore, StateStore
from readwise_sdk.v2.models import Book, Highlight
from readwise_sdk.v3.models import Document


class AsyncHighlightsResource(Protocol):
    """Highlight stream required by synchronization."""

    def iter(self, *, updated_after: datetime | None = None) -> AsyncIterator[Highlight]:
        """Yield highlights, optionally after a cursor."""
        ...


class AsyncBooksResource(Protocol):
    """Book stream required by synchronization."""

    def iter(self, *, updated_after: datetime | None = None) -> AsyncIterator[Book]:
        """Yield books, optionally after a cursor."""
        ...


class AsyncDocumentsResource(Protocol):
    """Document stream required by synchronization."""

    def iter(self, *, updated_after: datetime | None = None) -> AsyncIterator[Document]:
        """Yield documents, optionally after a cursor."""
        ...


class SyncV2Client(Protocol):
    """Legacy synchronous v2 streams used by compatibility shims."""

    def list_highlights(
        self, *, updated_after: datetime | None = None, **kwargs: Any
    ) -> Iterator[Highlight]:
        """Yield highlights."""
        ...

    def list_books(self, *, updated_after: datetime | None = None, **kwargs: Any) -> Iterator[Book]:
        """Yield books."""
        ...


class SyncV3Client(Protocol):
    """Legacy synchronous v3 streams used by compatibility shims."""

    def list_documents(
        self, *, updated_after: datetime | None = None, **kwargs: Any
    ) -> Iterator[Document]:
        """Yield documents."""
        ...


class SyncClient(Protocol):
    """Legacy synchronous client shape used at the operation seam."""

    @property
    def v2(self) -> SyncV2Client:
        """Return v2 streams."""
        ...

    @property
    def v3(self) -> SyncV3Client:
        """Return v3 streams."""
        ...


class AsyncV2Client(Protocol):
    """Legacy asynchronous v2 streams used by compatibility shims."""

    def list_highlights(
        self, *, updated_after: datetime | None = None, **kwargs: Any
    ) -> AsyncIterator[Highlight]:
        """Yield highlights."""
        ...

    def list_books(
        self, *, updated_after: datetime | None = None, **kwargs: Any
    ) -> AsyncIterator[Book]:
        """Yield books."""
        ...


class AsyncV3Client(Protocol):
    """Legacy asynchronous v3 streams used by compatibility shims."""

    def list_documents(
        self, *, updated_after: datetime | None = None, **kwargs: Any
    ) -> AsyncIterator[Document]:
        """Yield documents."""
        ...


class AsyncSyncClient(Protocol):
    """Legacy asynchronous client shape used at the operation seam."""

    @property
    def v2(self) -> AsyncV2Client:
        """Return v2 streams."""
        ...

    @property
    def v3(self) -> AsyncV3Client:
        """Return v3 streams."""
        ...


@dataclass
class BatchSyncOutcome:
    """Statistics and errors from one resource batch synchronization."""

    success: bool
    new_items: int = 0
    updated_items: int = 0
    failed_items: int = 0
    errors: list[str] = field(default_factory=list)
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))


class SyncOperations:
    """Run every synchronization mode over shared checkpoint behavior."""

    def __init__(
        self,
        *,
        highlights: AsyncHighlightsResource | None = None,
        books: AsyncBooksResource | None = None,
        documents: AsyncDocumentsResource | None = None,
        state_store: StateStore | None = None,
        sync_client: SyncClient | None = None,
        async_client: AsyncSyncClient | None = None,
    ) -> None:
        self._highlights = highlights
        self._books = books
        self._documents = documents
        self._state_store = state_store or MemoryStateStore()
        self._sync_client = sync_client
        self._async_client = async_client

    def status(self) -> SyncCheckpoint:
        """Return the current persisted checkpoint."""
        return self._state_store.load()

    def reset(self) -> None:
        """Persist an empty checkpoint so the next incremental sync is full."""
        self._state_store.save(SyncCheckpoint())

    async def full(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Fetch complete streams and advance included resource cursors."""
        return await self._sync_async(
            checkpoint=self._state_store.load(),
            incremental=False,
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )

    async def incremental(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Fetch streams after the current resource-specific cursors."""
        return await self._sync_async(
            checkpoint=self._state_store.load(),
            incremental=True,
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )

    async def poll_once(
        self,
        *,
        include_highlights: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Poll once, coupling books to the highlight cursor as the legacy poller did."""
        checkpoint = self._state_store.load()
        now = datetime.now(UTC)
        highlights: list[Highlight] = []
        books: list[Book] = []
        documents: list[Document] = []
        updates: dict[str, datetime | None] = {"last_sync_time": now}

        if include_highlights:
            since = checkpoint.last_highlight_sync
            highlights = [item async for item in self._iter_highlights(since)]
            books = [item async for item in self._iter_books(since)]
            updates["last_highlight_sync"] = now

        if include_documents:
            documents = [item async for item in self._iter_documents(checkpoint.last_document_sync)]
            updates["last_document_sync"] = now

        next_checkpoint = checkpoint.model_copy(update=updates)
        self._state_store.save(next_checkpoint)
        return SyncResult(
            highlights=highlights,
            books=books,
            documents=documents,
            checkpoint=next_checkpoint,
        )

    async def batch_highlights(
        self,
        *,
        on_item: Callable[[Highlight], object] | None = None,
        on_batch: Callable[[list[Highlight]], object] | None = None,
        batch_size: int = 100,
        continue_on_error: bool = True,
        full_sync: bool = False,
    ) -> BatchSyncOutcome:
        """Synchronize highlights with item and batch callbacks."""
        checkpoint = self._state_store.load()
        return await self._batch_async(
            self._iter_highlights(
                None if full_sync else checkpoint.last_highlight_sync,
                always_pass_cursor=True,
            ),
            resource_name="highlight",
            on_item=on_item,
            on_batch=on_batch,
            batch_size=batch_size,
            continue_on_error=continue_on_error,
            checkpoint=checkpoint,
            checkpoint_field="last_highlight_sync",
        )

    async def batch_books(
        self,
        *,
        on_item: Callable[[Book], object] | None = None,
        on_batch: Callable[[list[Book]], object] | None = None,
        batch_size: int = 100,
        continue_on_error: bool = True,
        full_sync: bool = False,
    ) -> BatchSyncOutcome:
        """Synchronize books with item and batch callbacks."""
        checkpoint = self._state_store.load()
        return await self._batch_async(
            self._iter_books(
                None if full_sync else checkpoint.last_book_sync,
                always_pass_cursor=True,
            ),
            resource_name="book",
            on_item=on_item,
            on_batch=on_batch,
            batch_size=batch_size,
            continue_on_error=continue_on_error,
            checkpoint=checkpoint,
            checkpoint_field="last_book_sync",
        )

    async def batch_documents(
        self,
        *,
        on_item: Callable[[Document], object] | None = None,
        on_batch: Callable[[list[Document]], object] | None = None,
        batch_size: int = 100,
        continue_on_error: bool = True,
        full_sync: bool = False,
    ) -> BatchSyncOutcome:
        """Synchronize documents with item and batch callbacks."""
        checkpoint = self._state_store.load()
        return await self._batch_async(
            self._iter_documents(
                None if full_sync else checkpoint.last_document_sync,
                always_pass_cursor=True,
            ),
            resource_name="document",
            on_item=on_item,
            on_batch=on_batch,
            batch_size=batch_size,
            continue_on_error=continue_on_error,
            checkpoint=checkpoint,
            checkpoint_field="last_document_sync",
        )

    def full_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Native synchronous full sync used by compatibility adapters."""
        return self._sync_native(
            checkpoint=self._state_store.load(),
            incremental=False,
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )

    def incremental_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Native synchronous incremental sync used by compatibility adapters."""
        return self._sync_native(
            checkpoint=self._state_store.load(),
            incremental=True,
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )

    def poll_once_sync(
        self,
        *,
        include_highlights: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Native synchronous poll-once behavior used by BackgroundPoller."""
        client = self._require(self._sync_client, "synchronous client")
        checkpoint = self._state_store.load()
        now = datetime.now(UTC)
        highlights: list[Highlight] = []
        books: list[Book] = []
        documents: list[Document] = []
        updates: dict[str, datetime | None] = {"last_sync_time": now}

        if include_highlights:
            since = checkpoint.last_highlight_sync
            if since is None:
                highlights = list(client.v2.list_highlights())
                books = list(client.v2.list_books())
            else:
                highlights = list(client.v2.list_highlights(updated_after=since))
                books = list(client.v2.list_books(updated_after=since))
            updates["last_highlight_sync"] = now
        if include_documents:
            since = checkpoint.last_document_sync
            if since is None:
                documents = list(client.v3.list_documents())
            else:
                documents = list(client.v3.list_documents(updated_after=since))
            updates["last_document_sync"] = now

        next_checkpoint = checkpoint.model_copy(update=updates)
        self._state_store.save(next_checkpoint)
        return SyncResult(
            highlights=highlights,
            books=books,
            documents=documents,
            checkpoint=next_checkpoint,
        )

    def batch_highlights_sync(
        self,
        *,
        on_item: Callable[[Highlight], None] | None = None,
        on_batch: Callable[[list[Highlight]], None] | None = None,
        batch_size: int = 100,
        continue_on_error: bool = True,
        full_sync: bool = False,
    ) -> BatchSyncOutcome:
        """Native synchronous highlight batching for BatchSync."""
        client = self._require(self._sync_client, "synchronous client")
        checkpoint = self._state_store.load()
        return self._batch_native(
            client.v2.list_highlights(
                updated_after=None if full_sync else checkpoint.last_highlight_sync
            ),
            resource_name="highlight",
            on_item=on_item,
            on_batch=on_batch,
            batch_size=batch_size,
            continue_on_error=continue_on_error,
            checkpoint=checkpoint,
            checkpoint_field="last_highlight_sync",
        )

    def batch_books_sync(
        self,
        *,
        on_item: Callable[[Book], None] | None = None,
        on_batch: Callable[[list[Book]], None] | None = None,
        batch_size: int = 100,
        continue_on_error: bool = True,
        full_sync: bool = False,
    ) -> BatchSyncOutcome:
        """Native synchronous book batching for BatchSync."""
        client = self._require(self._sync_client, "synchronous client")
        checkpoint = self._state_store.load()
        return self._batch_native(
            client.v2.list_books(updated_after=None if full_sync else checkpoint.last_book_sync),
            resource_name="book",
            on_item=on_item,
            on_batch=on_batch,
            batch_size=batch_size,
            continue_on_error=continue_on_error,
            checkpoint=checkpoint,
            checkpoint_field="last_book_sync",
        )

    def batch_documents_sync(
        self,
        *,
        on_item: Callable[[Document], None] | None = None,
        on_batch: Callable[[list[Document]], None] | None = None,
        batch_size: int = 100,
        continue_on_error: bool = True,
        full_sync: bool = False,
    ) -> BatchSyncOutcome:
        """Native synchronous document batching for BatchSync."""
        client = self._require(self._sync_client, "synchronous client")
        checkpoint = self._state_store.load()
        return self._batch_native(
            client.v3.list_documents(
                updated_after=None if full_sync else checkpoint.last_document_sync
            ),
            resource_name="document",
            on_item=on_item,
            on_batch=on_batch,
            batch_size=batch_size,
            continue_on_error=continue_on_error,
            checkpoint=checkpoint,
            checkpoint_field="last_document_sync",
        )

    @staticmethod
    def notify_callbacks[ValueT](
        callbacks: list[Callable[[ValueT], None]],
        value: ValueT,
    ) -> None:
        """Invoke every callback while suppressing each callback exception."""
        for callback in callbacks:
            try:
                callback(value)
            except Exception:
                pass

    async def _sync_async(
        self,
        *,
        checkpoint: SyncCheckpoint,
        incremental: bool,
        include_highlights: bool,
        include_books: bool,
        include_documents: bool,
    ) -> SyncResult:
        now = datetime.now(UTC)
        highlights: list[Highlight] = []
        books: list[Book] = []
        documents: list[Document] = []
        updates: dict[str, datetime | None] = {"last_sync_time": now}

        if include_highlights:
            since = checkpoint.last_highlight_sync if incremental else None
            highlights = [item async for item in self._iter_highlights(since)]
            updates["last_highlight_sync"] = now
        if include_books:
            since = checkpoint.last_book_sync if incremental else None
            books = [item async for item in self._iter_books(since)]
            updates["last_book_sync"] = now
        if include_documents:
            since = checkpoint.last_document_sync if incremental else None
            documents = [item async for item in self._iter_documents(since)]
            updates["last_document_sync"] = now

        next_checkpoint = checkpoint.model_copy(update=updates)
        self._state_store.save(next_checkpoint)
        return SyncResult(
            highlights=highlights,
            books=books,
            documents=documents,
            checkpoint=next_checkpoint,
        )

    def _sync_native(
        self,
        *,
        checkpoint: SyncCheckpoint,
        incremental: bool,
        include_highlights: bool,
        include_books: bool,
        include_documents: bool,
    ) -> SyncResult:
        client = self._require(self._sync_client, "synchronous client")
        now = datetime.now(UTC)
        highlights: list[Highlight] = []
        books: list[Book] = []
        documents: list[Document] = []
        updates: dict[str, datetime | None] = {"last_sync_time": now}

        if include_highlights:
            since = checkpoint.last_highlight_sync if incremental else None
            if since is None:
                highlights = list(client.v2.list_highlights())
            else:
                highlights = list(client.v2.list_highlights(updated_after=since))
            updates["last_highlight_sync"] = now
        if include_books:
            since = checkpoint.last_book_sync if incremental else None
            if since is None:
                books = list(client.v2.list_books())
            else:
                books = list(client.v2.list_books(updated_after=since))
            updates["last_book_sync"] = now
        if include_documents:
            since = checkpoint.last_document_sync if incremental else None
            if since is None:
                documents = list(client.v3.list_documents())
            else:
                documents = list(client.v3.list_documents(updated_after=since))
            updates["last_document_sync"] = now

        next_checkpoint = checkpoint.model_copy(update=updates)
        self._state_store.save(next_checkpoint)
        return SyncResult(
            highlights=highlights,
            books=books,
            documents=documents,
            checkpoint=next_checkpoint,
        )

    async def _batch_async[ItemT](
        self,
        items: AsyncIterator[ItemT],
        *,
        resource_name: str,
        on_item: Callable[[ItemT], object] | None,
        on_batch: Callable[[list[ItemT]], object] | None,
        batch_size: int,
        continue_on_error: bool,
        checkpoint: SyncCheckpoint,
        checkpoint_field: Literal["last_highlight_sync", "last_book_sync", "last_document_sync"],
    ) -> BatchSyncOutcome:
        now = datetime.now(UTC)
        result = BatchSyncOutcome(success=True, sync_time=now)
        batch: list[ItemT] = []
        try:
            async for item in items:
                try:
                    if on_item is not None:
                        callback_result = on_item(item)
                        if inspect.isawaitable(callback_result):
                            await callback_result
                    batch.append(item)
                    result.new_items += 1
                    if len(batch) >= batch_size:
                        if on_batch is not None:
                            batch_result = on_batch(batch)
                            if inspect.isawaitable(batch_result):
                                await batch_result
                        batch = []
                except Exception as error:
                    result.failed_items += 1
                    result.errors.append(
                        f"Error processing {resource_name} {cast(Any, item).id}: {error}"
                    )
                    if not continue_on_error:
                        result.success = False
                        break
            if batch and on_batch is not None:
                batch_result = on_batch(batch)
                if inspect.isawaitable(batch_result):
                    await batch_result
            next_checkpoint = checkpoint.model_copy(
                update={checkpoint_field: now, "last_sync_time": now}
            )
            self._state_store.save(next_checkpoint)
        except Exception as error:
            result.success = False
            result.errors.append(f"Sync failed: {error}")
        return result

    def _batch_native[ItemT](
        self,
        items: Iterator[ItemT],
        *,
        resource_name: str,
        on_item: Callable[[ItemT], None] | None,
        on_batch: Callable[[list[ItemT]], None] | None,
        batch_size: int,
        continue_on_error: bool,
        checkpoint: SyncCheckpoint,
        checkpoint_field: Literal["last_highlight_sync", "last_book_sync", "last_document_sync"],
    ) -> BatchSyncOutcome:
        now = datetime.now(UTC)
        result = BatchSyncOutcome(success=True, sync_time=now)
        batch: list[ItemT] = []
        try:
            for item in items:
                try:
                    if on_item is not None:
                        on_item(item)
                    batch.append(item)
                    result.new_items += 1
                    if len(batch) >= batch_size:
                        if on_batch is not None:
                            on_batch(batch)
                        batch = []
                except Exception as error:
                    result.failed_items += 1
                    result.errors.append(
                        f"Error processing {resource_name} {cast(Any, item).id}: {error}"
                    )
                    if not continue_on_error:
                        result.success = False
                        break
            if batch and on_batch is not None:
                on_batch(batch)
            next_checkpoint = checkpoint.model_copy(
                update={checkpoint_field: now, "last_sync_time": now}
            )
            self._state_store.save(next_checkpoint)
        except Exception as error:
            result.success = False
            result.errors.append(f"Sync failed: {error}")
        return result

    @staticmethod
    def _require[ValueT](value: ValueT | None, name: str) -> ValueT:
        if value is None:
            raise RuntimeError(f"{name.capitalize()} synchronization was not configured")
        return value

    def _iter_highlights(
        self,
        updated_after: datetime | None,
        *,
        always_pass_cursor: bool = False,
    ) -> AsyncIterator[Highlight]:
        if self._highlights is not None:
            return self._highlights.iter(updated_after=updated_after)
        client = self._require(self._async_client, "highlight")
        if updated_after is None and not always_pass_cursor:
            return client.v2.list_highlights()
        return client.v2.list_highlights(updated_after=updated_after)

    def _iter_books(
        self,
        updated_after: datetime | None,
        *,
        always_pass_cursor: bool = False,
    ) -> AsyncIterator[Book]:
        if self._books is not None:
            return self._books.iter(updated_after=updated_after)
        client = self._require(self._async_client, "book")
        if updated_after is None and not always_pass_cursor:
            return client.v2.list_books()
        return client.v2.list_books(updated_after=updated_after)

    def _iter_documents(
        self,
        updated_after: datetime | None,
        *,
        always_pass_cursor: bool = False,
    ) -> AsyncIterator[Document]:
        if self._documents is not None:
            return self._documents.iter(updated_after=updated_after)
        client = self._require(self._async_client, "document")
        if updated_after is None and not always_pass_cursor:
            return client.v3.list_documents()
        return client.v3.list_documents(updated_after=updated_after)


class BackgroundSyncScheduler:
    """Run a synchronous poll callback repeatedly with legacy backoff semantics."""

    def __init__(
        self,
        poll: Callable[[], object],
        *,
        poll_interval: int,
        max_consecutive_errors: int,
        backoff_multiplier: float,
        max_backoff: int,
        on_success: Callable[[object], None],
        on_error: Callable[[Exception], None],
        on_running_change: Callable[[bool], None],
    ) -> None:
        self._poll = poll
        self._poll_interval = poll_interval
        self._max_consecutive_errors = max_consecutive_errors
        self._backoff_multiplier = backoff_multiplier
        self._max_backoff = max_backoff
        self._on_success = on_success
        self._on_error = on_error
        self._on_running_change = on_running_change
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.consecutive_errors = 0
        self.current_backoff: float = poll_interval

    def run(self) -> None:
        """Poll until stopped or the consecutive error limit is reached."""
        while not self.stop_event.is_set():
            try:
                result = self._poll()
                self.consecutive_errors = 0
                self.current_backoff = self._poll_interval
                self._on_success(result)
            except Exception as error:
                self.consecutive_errors += 1
                self.current_backoff = min(
                    self.current_backoff * self._backoff_multiplier,
                    self._max_backoff,
                )
                self._on_error(error)
                if self.consecutive_errors >= self._max_consecutive_errors:
                    self._on_running_change(False)
                    return
            wait_time = self.current_backoff if self.consecutive_errors > 0 else self._poll_interval
            self.stop_event.wait(wait_time)
        self._on_running_change(False)

    def start(self, *, blocking: bool = False) -> None:
        """Start in the current thread or a daemon background thread."""
        self.stop_event.clear()
        self._on_running_change(True)
        if blocking:
            self.run()
        else:
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self, *, timeout: float | None = None) -> None:
        """Request shutdown and join a running background thread."""
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)
        self._on_running_change(False)

    def reset_errors(self) -> None:
        """Reset consecutive errors and the current backoff."""
        self.consecutive_errors = 0
        self.current_backoff = self._poll_interval


__all__ = [
    "BackgroundSyncScheduler",
    "BatchSyncOutcome",
    "SyncOperations",
]
