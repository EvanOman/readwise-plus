"""Sync utilities for incremental data fetching."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from readwise_sdk._utils import parse_datetime_string
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
        self._state = self._load_state()
        self._callbacks: list[Callable[[SyncResult], None]] = []

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

    def on_sync(self, callback: Callable[[SyncResult], None]) -> None:
        """Register a callback for sync events.

        Args:
            callback: Function to call with sync results.
        """
        self._callbacks.append(callback)

    def _notify_callbacks(self, result: SyncResult) -> None:
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass  # Don't let callback errors break the sync

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
        now = datetime.now(UTC)
        result = SyncResult(sync_time=now)

        if include_highlights:
            result.highlights = list(self._client.v2.list_highlights())
            self._state.last_highlight_sync = now

        if include_books:
            result.books = list(self._client.v2.list_books())
            self._state.last_book_sync = now

        if include_documents:
            result.documents = list(self._client.v3.list_documents())
            self._state.last_document_sync = now

        self._state.total_syncs += 1
        self._state.last_sync_time = now
        self._save_state()
        self._notify_callbacks(result)

        return result

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
        now = datetime.now(UTC)
        result = SyncResult(sync_time=now)

        if include_highlights:
            since = self._state.last_highlight_sync
            if since:
                result.highlights = list(self._client.v2.list_highlights(updated_after=since))
            else:
                result.highlights = list(self._client.v2.list_highlights())
            self._state.last_highlight_sync = now

        if include_books:
            since = self._state.last_book_sync
            if since:
                result.books = list(self._client.v2.list_books(updated_after=since))
            else:
                result.books = list(self._client.v2.list_books())
            self._state.last_book_sync = now

        if include_documents:
            since = self._state.last_document_sync
            if since:
                result.documents = list(self._client.v3.list_documents(updated_after=since))
            else:
                result.documents = list(self._client.v3.list_documents())
            self._state.last_document_sync = now

        self._state.total_syncs += 1
        self._state.last_sync_time = now
        self._save_state()
        self._notify_callbacks(result)

        return result

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
        self._save_state()
