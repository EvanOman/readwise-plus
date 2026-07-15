"""Sync utilities for incremental data fetching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from readwise_sdk._utils import parse_datetime_string
from readwise_sdk.models import SyncCheckpoint
from readwise_sdk.models import SyncResult as CanonicalSyncResult
from readwise_sdk.operations.sync import SyncClient, SyncOperations
from readwise_sdk.state import JsonFileStateStore, MemoryStateStore
from readwise_sdk.v2.models import Book, Highlight
from readwise_sdk.v3.models import Document

if TYPE_CHECKING:
    from collections.abc import Callable

    from readwise_sdk.client import ReadwiseClient


@dataclass
class SyncState:
    """State for tracking sync progress."""

    last_highlight_sync: datetime | None = None
    last_book_sync: datetime | None = None
    last_document_sync: datetime | None = None
    total_syncs: int = 0
    last_sync_time: datetime | None = None

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
            "total_syncs": self.total_syncs,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SyncState:
        """Create from dictionary."""
        return cls(
            last_highlight_sync=parse_datetime_string(data.get("last_highlight_sync")),
            last_book_sync=parse_datetime_string(data.get("last_book_sync")),
            last_document_sync=parse_datetime_string(data.get("last_document_sync")),
            total_syncs=data.get("total_syncs", 0),
            last_sync_time=parse_datetime_string(data.get("last_sync_time")),
        )


@dataclass
class SyncResult:
    """Result of a sync operation."""

    highlights: list[Highlight] = field(default_factory=list)
    books: list[Book] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_empty(self) -> bool:
        """Check if no new data was synced."""
        return not self.highlights and not self.books and not self.documents


class SyncManager:
    """Manager for syncing Readwise data with state persistence."""

    def __init__(
        self,
        client: ReadwiseClient,
        *,
        state_file: Path | str | None = None,
    ) -> None:
        """Initialize the sync manager.

        Args:
            client: The Readwise client.
            state_file: Optional path to persist sync state.
        """
        self._client = client
        self._state_file = Path(state_file) if state_file else None
        self._file_store = JsonFileStateStore(self._state_file) if self._state_file else None
        self._state = self._load_state()
        self._callbacks: list[Callable[[SyncResult], None]] = []
        self._checkpoint_store = MemoryStateStore(self._checkpoint())
        self._operation = SyncOperations(
            sync_client=cast(SyncClient, self._client),
            state_store=self._checkpoint_store,
        )

    def _load_state(self) -> SyncState:
        """Load state from file if it exists."""
        if self._file_store is not None:
            return self._file_store.load_legacy(SyncState.from_dict, SyncState)
        return SyncState()

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if self._file_store is not None:
            self._file_store.save_legacy(self._state.to_dict())

    @property
    def state(self) -> SyncState:
        """Get the current sync state."""
        return self._state

    def on_sync(self, callback: Callable[[SyncResult], None]) -> None:
        """Register a callback for sync events.

        Args:
            callback: Function to call with sync results.
        """
        self._callbacks.append(callback)

    def _notify_callbacks(self, result: SyncResult) -> None:
        """Notify all registered callbacks."""
        self._operation.notify_callbacks(self._callbacks, result)

    def full_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Perform a full sync of all data.

        Args:
            include_highlights: Whether to sync highlights.
            include_books: Whether to sync books.
            include_documents: Whether to sync documents.

        Returns:
            SyncResult with all synced data.
        """
        self._checkpoint_store.save(self._checkpoint())
        canonical = self._operation.full_sync(
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )
        return self._finish(canonical)

    def incremental_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Perform an incremental sync since the last sync.

        Args:
            include_highlights: Whether to sync highlights.
            include_books: Whether to sync books.
            include_documents: Whether to sync documents.

        Returns:
            SyncResult with newly synced data.
        """
        self._checkpoint_store.save(self._checkpoint())
        canonical = self._operation.incremental_sync(
            include_highlights=include_highlights,
            include_books=include_books,
            include_documents=include_documents,
        )
        return self._finish(canonical)

    def sync_highlights_only(self) -> SyncResult:
        """Sync only highlights.

        Returns:
            SyncResult with synced highlights.
        """
        return self.incremental_sync(include_books=False, include_documents=False)

    def sync_documents_only(self) -> SyncResult:
        """Sync only documents.

        Returns:
            SyncResult with synced documents.
        """
        return self.incremental_sync(include_highlights=False, include_books=False)

    def reset_state(self) -> None:
        """Reset the sync state (next sync will be full)."""
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
