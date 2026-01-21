"""Batch synchronization utilities with state tracking.

Designed for readwise_digest and similar projects that need efficient
batch synchronization with progress tracking and error recovery.

Example:
    from readwise_sdk import ReadwiseClient
    from readwise_sdk.contrib import BatchSync, BatchSyncConfig

    client = ReadwiseClient()

    # Configure sync
    config = BatchSyncConfig(
        batch_size=100,
        state_file="sync_state.json",
    )

    sync = BatchSync(client, config=config)

    # Incremental sync with callback
    def on_highlight(highlight):
        print(f"New highlight: {highlight.text[:50]}...")
        # Process highlight (e.g., save to database)

    result = sync.sync_highlights(on_item=on_highlight)
    print(f"Synced {result.new_items} new highlights")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from readwise_sdk._utils import parse_datetime_string
from readwise_sdk.v2.models import Book, Highlight

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from readwise_sdk.client import AsyncReadwiseClient, ReadwiseClient


@dataclass
class BatchSyncConfig:
    """Configuration for batch synchronization."""

    batch_size: int = 100
    state_file: Path | str | None = None
    continue_on_error: bool = True


@dataclass
class SyncState:
    """State tracking for synchronization."""

    last_highlight_sync: datetime | None = None
    last_book_sync: datetime | None = None
    last_document_sync: datetime | None = None
    total_highlights_synced: int = 0
    total_books_synced: int = 0
    total_documents_synced: int = 0
    last_sync_time: datetime | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "last_highlight_sync": self.last_highlight_sync.isoformat()
            if self.last_highlight_sync
            else None,
            "last_book_sync": self.last_book_sync.isoformat() if self.last_book_sync else None,
            "last_document_sync": self.last_document_sync.isoformat()
            if self.last_document_sync
            else None,
            "total_highlights_synced": self.total_highlights_synced,
            "total_books_synced": self.total_books_synced,
            "total_documents_synced": self.total_documents_synced,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "errors": self.errors[-100:],  # Keep last 100 errors
        }

    @classmethod
    def from_dict(cls, data: dict) -> SyncState:
        """Create from dictionary."""
        return cls(
            last_highlight_sync=parse_datetime_string(data.get("last_highlight_sync")),
            last_book_sync=parse_datetime_string(data.get("last_book_sync")),
            last_document_sync=parse_datetime_string(data.get("last_document_sync")),
            total_highlights_synced=data.get("total_highlights_synced", 0),
            total_books_synced=data.get("total_books_synced", 0),
            total_documents_synced=data.get("total_documents_synced", 0),
            last_sync_time=parse_datetime_string(data.get("last_sync_time")),
            errors=data.get("errors", []),
        )


@dataclass
class BatchSyncResult:
    """Result of a batch sync operation."""

    success: bool
    new_items: int = 0
    updated_items: int = 0
    failed_items: int = 0
    errors: list[str] = field(default_factory=list)
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))


class BatchSync:
    """Efficient batch synchronization with state tracking.

    Provides:
    - Incremental sync using last sync timestamps
    - Batch processing with configurable batch size
    - Callback hooks for item processing
    - State persistence across sessions
    - Error recovery and logging
    """

    def __init__(
        self,
        client: ReadwiseClient,
        *,
        config: BatchSyncConfig | None = None,
    ) -> None:
        """Initialize batch sync.

        Args:
            client: The Readwise client.
            config: Optional sync configuration.
        """
        self._client = client
        self._config = config or BatchSyncConfig()
        self._state_file = Path(self._config.state_file) if self._config.state_file else None
        self._state = self._load_state()

    def _load_state(self) -> SyncState:
        """Load state from file if it exists."""
        if self._state_file and self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return SyncState.from_dict(data)
            except Exception:
                pass
        return SyncState()

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if self._state_file:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(self._state.to_dict(), indent=2))

    @property
    def state(self) -> SyncState:
        """Get the current sync state."""
        return self._state

    def sync_highlights(
        self,
        *,
        on_item: Callable[[Highlight], None] | None = None,
        on_batch: Callable[[list[Highlight]], None] | None = None,
        full_sync: bool = False,
    ) -> BatchSyncResult:
        """Sync highlights from Readwise.

        Args:
            on_item: Callback for each highlight.
            on_batch: Callback for each batch of highlights.
            full_sync: If True, sync all highlights. If False, sync since last sync.

        Returns:
            BatchSyncResult with sync statistics.
        """
        now = datetime.now(UTC)
        result = BatchSyncResult(success=True, sync_time=now)

        since = None if full_sync else self._state.last_highlight_sync

        batch: list[Highlight] = []

        try:
            for highlight in self._client.v2.list_highlights(updated_after=since):
                try:
                    if on_item:
                        on_item(highlight)

                    batch.append(highlight)
                    result.new_items += 1

                    # Process batch when full
                    if len(batch) >= self._config.batch_size:
                        if on_batch:
                            on_batch(batch)
                        batch = []

                except Exception as e:
                    result.failed_items += 1
                    error_msg = f"Error processing highlight {highlight.id}: {e}"
                    result.errors.append(error_msg)
                    self._state.errors.append(error_msg)

                    if not self._config.continue_on_error:
                        result.success = False
                        break

            # Process remaining batch
            if batch and on_batch:
                on_batch(batch)

            # Update state
            self._state.last_highlight_sync = now
            self._state.total_highlights_synced += result.new_items
            self._state.last_sync_time = now
            self._save_state()

        except Exception as e:
            result.success = False
            result.errors.append(f"Sync failed: {e}")

        return result

    def sync_books(
        self,
        *,
        on_item: Callable[[Book], None] | None = None,
        on_batch: Callable[[list[Book]], None] | None = None,
        full_sync: bool = False,
    ) -> BatchSyncResult:
        """Sync books from Readwise.

        Args:
            on_item: Callback for each book.
            on_batch: Callback for each batch of books.
            full_sync: If True, sync all books. If False, sync since last sync.

        Returns:
            BatchSyncResult with sync statistics.
        """
        now = datetime.now(UTC)
        result = BatchSyncResult(success=True, sync_time=now)

        since = None if full_sync else self._state.last_book_sync

        batch: list[Book] = []

        try:
            for book in self._client.v2.list_books(updated_after=since):
                try:
                    if on_item:
                        on_item(book)

                    batch.append(book)
                    result.new_items += 1

                    # Process batch when full
                    if len(batch) >= self._config.batch_size:
                        if on_batch:
                            on_batch(batch)
                        batch = []

                except Exception as e:
                    result.failed_items += 1
                    error_msg = f"Error processing book {book.id}: {e}"
                    result.errors.append(error_msg)
                    self._state.errors.append(error_msg)

                    if not self._config.continue_on_error:
                        result.success = False
                        break

            # Process remaining batch
            if batch and on_batch:
                on_batch(batch)

            # Update state
            self._state.last_book_sync = now
            self._state.total_books_synced += result.new_items
            self._state.last_sync_time = now
            self._save_state()

        except Exception as e:
            result.success = False
            result.errors.append(f"Sync failed: {e}")

        return result

    def sync_all(
        self,
        *,
        on_highlight: Callable[[Highlight], None] | None = None,
        on_book: Callable[[Book], None] | None = None,
        full_sync: bool = False,
    ) -> tuple[BatchSyncResult, BatchSyncResult]:
        """Sync both highlights and books.

        Args:
            on_highlight: Callback for each highlight.
            on_book: Callback for each book.
            full_sync: If True, sync all data.

        Returns:
            Tuple of (highlight_result, book_result).
        """
        highlight_result = self.sync_highlights(on_item=on_highlight, full_sync=full_sync)
        book_result = self.sync_books(on_item=on_book, full_sync=full_sync)
        return highlight_result, book_result

    def reset_state(self) -> None:
        """Reset sync state (next sync will be full sync)."""
        self._state = SyncState()
        self._save_state()

    def get_stats(self) -> dict:
        """Get sync statistics.

        Returns:
            Dictionary with sync statistics.
        """
        return {
            "last_highlight_sync": self._state.last_highlight_sync,
            "last_book_sync": self._state.last_book_sync,
            "total_highlights_synced": self._state.total_highlights_synced,
            "total_books_synced": self._state.total_books_synced,
            "error_count": len(self._state.errors),
            "last_sync_time": self._state.last_sync_time,
        }


class AsyncBatchSync:
    """Async version of BatchSync for efficient batch synchronization.

    Provides the same functionality as BatchSync but with async/await
    support for use with async frameworks like FastAPI or aiohttp.

    Example:
        from readwise_sdk import AsyncReadwiseClient
        from readwise_sdk.contrib import AsyncBatchSync, BatchSyncConfig

        async with AsyncReadwiseClient() as client:
            config = BatchSyncConfig(
                batch_size=100,
                state_file="sync_state.json",
            )

            sync = AsyncBatchSync(client, config=config)

            # Incremental sync with async callback
            async def on_highlight(highlight):
                print(f"New highlight: {highlight.text[:50]}...")
                await save_to_database(highlight)

            result = await sync.sync_highlights(on_item=on_highlight)
            print(f"Synced {result.new_items} new highlights")
    """

    def __init__(
        self,
        client: AsyncReadwiseClient,
        *,
        config: BatchSyncConfig | None = None,
    ) -> None:
        """Initialize async batch sync.

        Args:
            client: The async Readwise client.
            config: Optional sync configuration.
        """
        self._client = client
        self._config = config or BatchSyncConfig()
        self._state_file = Path(self._config.state_file) if self._config.state_file else None
        self._state = self._load_state()

    def _load_state(self) -> SyncState:
        """Load state from file if it exists."""
        if self._state_file and self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return SyncState.from_dict(data)
            except Exception:
                pass
        return SyncState()

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if self._state_file:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(self._state.to_dict(), indent=2))

    @property
    def state(self) -> SyncState:
        """Get the current sync state."""
        return self._state

    async def sync_highlights(
        self,
        *,
        on_item: Callable[[Highlight], None] | Callable[[Highlight], Awaitable[None]] | None = None,
        on_batch: (
            Callable[[list[Highlight]], None] | Callable[[list[Highlight]], Awaitable[None]] | None
        ) = None,
        full_sync: bool = False,
    ) -> BatchSyncResult:
        """Sync highlights from Readwise asynchronously.

        Args:
            on_item: Callback for each highlight (can be sync or async).
            on_batch: Callback for each batch of highlights (can be sync or async).
            full_sync: If True, sync all highlights. If False, sync since last sync.

        Returns:
            BatchSyncResult with sync statistics.
        """
        import inspect

        now = datetime.now(UTC)
        result = BatchSyncResult(success=True, sync_time=now)

        since = None if full_sync else self._state.last_highlight_sync

        batch: list[Highlight] = []

        try:
            async for highlight in self._client.v2.list_highlights(updated_after=since):
                try:
                    if on_item:
                        cb_result = on_item(highlight)
                        if inspect.isawaitable(cb_result):
                            await cb_result

                    batch.append(highlight)
                    result.new_items += 1

                    # Process batch when full
                    if len(batch) >= self._config.batch_size:
                        if on_batch:
                            batch_result = on_batch(batch)
                            if inspect.isawaitable(batch_result):
                                await batch_result
                        batch = []

                except Exception as e:
                    result.failed_items += 1
                    error_msg = f"Error processing highlight {highlight.id}: {e}"
                    result.errors.append(error_msg)
                    self._state.errors.append(error_msg)

                    if not self._config.continue_on_error:
                        result.success = False
                        break

            # Process remaining batch
            if batch and on_batch:
                batch_result = on_batch(batch)
                if inspect.isawaitable(batch_result):
                    await batch_result

            # Update state
            self._state.last_highlight_sync = now
            self._state.total_highlights_synced += result.new_items
            self._state.last_sync_time = now
            self._save_state()

        except Exception as e:
            result.success = False
            result.errors.append(f"Sync failed: {e}")

        return result

    async def sync_books(
        self,
        *,
        on_item: Callable[[Book], None] | Callable[[Book], Awaitable[None]] | None = None,
        on_batch: (
            Callable[[list[Book]], None] | Callable[[list[Book]], Awaitable[None]] | None
        ) = None,
        full_sync: bool = False,
    ) -> BatchSyncResult:
        """Sync books from Readwise asynchronously.

        Args:
            on_item: Callback for each book (can be sync or async).
            on_batch: Callback for each batch of books (can be sync or async).
            full_sync: If True, sync all books. If False, sync since last sync.

        Returns:
            BatchSyncResult with sync statistics.
        """
        import inspect

        now = datetime.now(UTC)
        result = BatchSyncResult(success=True, sync_time=now)

        since = None if full_sync else self._state.last_book_sync

        batch: list[Book] = []

        try:
            async for book in self._client.v2.list_books(updated_after=since):
                try:
                    if on_item:
                        cb_result = on_item(book)
                        if inspect.isawaitable(cb_result):
                            await cb_result

                    batch.append(book)
                    result.new_items += 1

                    # Process batch when full
                    if len(batch) >= self._config.batch_size:
                        if on_batch:
                            batch_result = on_batch(batch)
                            if inspect.isawaitable(batch_result):
                                await batch_result
                        batch = []

                except Exception as e:
                    result.failed_items += 1
                    error_msg = f"Error processing book {book.id}: {e}"
                    result.errors.append(error_msg)
                    self._state.errors.append(error_msg)

                    if not self._config.continue_on_error:
                        result.success = False
                        break

            # Process remaining batch
            if batch and on_batch:
                batch_result = on_batch(batch)
                if inspect.isawaitable(batch_result):
                    await batch_result

            # Update state
            self._state.last_book_sync = now
            self._state.total_books_synced += result.new_items
            self._state.last_sync_time = now
            self._save_state()

        except Exception as e:
            result.success = False
            result.errors.append(f"Sync failed: {e}")

        return result

    async def sync_all(
        self,
        *,
        on_highlight: (
            Callable[[Highlight], None] | Callable[[Highlight], Awaitable[None]] | None
        ) = None,
        on_book: Callable[[Book], None] | Callable[[Book], Awaitable[None]] | None = None,
        full_sync: bool = False,
    ) -> tuple[BatchSyncResult, BatchSyncResult]:
        """Sync both highlights and books asynchronously.

        Args:
            on_highlight: Callback for each highlight (can be sync or async).
            on_book: Callback for each book (can be sync or async).
            full_sync: If True, sync all data.

        Returns:
            Tuple of (highlight_result, book_result).
        """
        highlight_result = await self.sync_highlights(on_item=on_highlight, full_sync=full_sync)
        book_result = await self.sync_books(on_item=on_book, full_sync=full_sync)
        return highlight_result, book_result

    def reset_state(self) -> None:
        """Reset sync state (next sync will be full sync)."""
        self._state = SyncState()
        self._save_state()

    def get_stats(self) -> dict:
        """Get sync statistics.

        Returns:
            Dictionary with sync statistics.
        """
        return {
            "last_highlight_sync": self._state.last_highlight_sync,
            "last_book_sync": self._state.last_book_sync,
            "total_highlights_synced": self._state.total_highlights_synced,
            "total_books_synced": self._state.total_books_synced,
            "error_count": len(self._state.errors),
            "last_sync_time": self._state.last_sync_time,
        }
