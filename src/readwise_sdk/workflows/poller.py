"""Background poller for continuous sync operations."""

from __future__ import annotations

import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from readwise_sdk._utils import parse_datetime_string
from readwise_sdk.managers.sync import SyncResult
from readwise_sdk.models import SyncCheckpoint
from readwise_sdk.models import SyncResult as CanonicalSyncResult
from readwise_sdk.operations.sync import (
    BackgroundSyncScheduler,
    SyncClient,
    SyncOperations,
)
from readwise_sdk.state import JsonFileStateStore, MemoryStateStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from readwise_sdk.client import ReadwiseClient


@dataclass
class PollerState:
    """State for the background poller."""

    last_poll_time: datetime | None = None
    last_highlight_sync: datetime | None = None
    last_document_sync: datetime | None = None
    poll_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    is_running: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "last_poll_time": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "last_highlight_sync": self.last_highlight_sync.isoformat()
            if self.last_highlight_sync
            else None,
            "last_document_sync": self.last_document_sync.isoformat()
            if self.last_document_sync
            else None,
            "poll_count": self.poll_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PollerState:
        """Create from dictionary."""
        return cls(
            last_poll_time=parse_datetime_string(data.get("last_poll_time")),
            last_highlight_sync=parse_datetime_string(data.get("last_highlight_sync")),
            last_document_sync=parse_datetime_string(data.get("last_document_sync")),
            poll_count=data.get("poll_count", 0),
            error_count=data.get("error_count", 0),
            last_error=data.get("last_error"),
        )


@dataclass
class PollerConfig:
    """Configuration for the background poller."""

    poll_interval: int = 300  # 5 minutes
    include_highlights: bool = True
    include_documents: bool = True
    max_consecutive_errors: int = 5
    backoff_multiplier: float = 2.0
    max_backoff: int = 3600  # 1 hour
    state_file: Path | None = None


class BackgroundPoller:
    """Background poller for continuous sync operations with error recovery."""

    def __init__(
        self,
        client: ReadwiseClient,
        *,
        config: PollerConfig | None = None,
    ) -> None:
        """Initialize the background poller.

        Args:
            client: The Readwise client.
            config: Optional poller configuration.
        """
        self._client = client
        self._config = config or PollerConfig()
        self._file_store = (
            JsonFileStateStore(self._config.state_file) if self._config.state_file else None
        )
        self._state = self._load_state()
        self._callbacks: list[Callable[[SyncResult], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._checkpoint_store = MemoryStateStore(self._checkpoint())
        self._operation = SyncOperations(
            sync_client=cast(SyncClient, self._client),
            state_store=self._checkpoint_store,
        )
        self._scheduler = BackgroundSyncScheduler(
            self._do_poll,
            poll_interval=self._config.poll_interval,
            max_consecutive_errors=self._config.max_consecutive_errors,
            backoff_multiplier=self._config.backoff_multiplier,
            max_backoff=self._config.max_backoff,
            on_success=self._handle_poll_success,
            on_error=self._handle_poll_error,
            on_running_change=self._set_running,
        )
        self._stop_event = self._scheduler.stop_event

    def _load_state(self) -> PollerState:
        """Load state from file if it exists."""
        if self._file_store is not None:
            return self._file_store.load_legacy(PollerState.from_dict, PollerState)
        return PollerState()

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if self._file_store is not None:
            self._file_store.save_legacy(self._state.to_dict())

    @property
    def state(self) -> PollerState:
        """Get the current poller state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if the poller is currently running."""
        return self._state.is_running

    def on_sync(self, callback: Callable[[SyncResult], None]) -> None:
        """Register a callback for successful sync events.

        Args:
            callback: Function to call with sync results.
        """
        self._callbacks.append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register a callback for error events.

        Args:
            callback: Function to call with the exception.
        """
        self._error_callbacks.append(callback)

    def _notify_callbacks(self, result: SyncResult) -> None:
        """Notify all registered callbacks."""
        self._operation.notify_callbacks(self._callbacks, result)

    def _notify_error_callbacks(self, error: Exception) -> None:
        """Notify all error callbacks."""
        self._operation.notify_callbacks(self._error_callbacks, error)

    def _do_poll(self) -> SyncResult:
        """Perform a single poll operation."""
        self._checkpoint_store.save(self._checkpoint())
        canonical = self._operation.poll_once_sync(
            include_highlights=self._config.include_highlights,
            include_documents=self._config.include_documents,
        )
        checkpoint = canonical.checkpoint
        self._state.last_highlight_sync = checkpoint.last_highlight_sync
        self._state.last_document_sync = checkpoint.last_document_sync
        return self._legacy_result(canonical)

    def _poll_loop(self) -> None:
        """Main polling loop."""
        self._scheduler.run()

    def start(self, *, blocking: bool = False) -> None:
        """Start the background poller.

        Args:
            blocking: If True, run in the current thread (blocking).
                     If False, run in a background thread.
        """
        if self._state.is_running:
            return
        self._scheduler.start(blocking=blocking)

    def stop(self, *, timeout: float | None = None) -> None:
        """Stop the background poller.

        Args:
            timeout: Maximum time to wait for the poller to stop.
        """
        self._scheduler.stop(timeout=timeout)

    def poll_once(self) -> SyncResult:
        """Perform a single poll operation (for manual triggering).

        Returns:
            SyncResult with fetched data.
        """
        result = self._do_poll()
        self._state.last_poll_time = datetime.now(UTC)
        self._state.poll_count += 1
        self._save_state()
        self._notify_callbacks(result)
        return result

    def reset_errors(self) -> None:
        """Reset the error count and backoff."""
        self._scheduler.reset_errors()
        self._state.last_error = None
        self._save_state()

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown.

        Call this if running in blocking mode to handle SIGINT/SIGTERM.
        """

        def handler(signum: int, frame: object) -> None:
            self.stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    @property
    def _consecutive_errors(self) -> int:
        return self._scheduler.consecutive_errors

    @_consecutive_errors.setter
    def _consecutive_errors(self, value: int) -> None:
        self._scheduler.consecutive_errors = value

    @property
    def _current_backoff(self) -> float:
        return self._scheduler.current_backoff

    @_current_backoff.setter
    def _current_backoff(self, value: float) -> None:
        self._scheduler.current_backoff = value

    def _checkpoint(self) -> SyncCheckpoint:
        return SyncCheckpoint(
            last_highlight_sync=self._state.last_highlight_sync,
            last_document_sync=self._state.last_document_sync,
            last_sync_time=self._state.last_poll_time,
        )

    @staticmethod
    def _legacy_result(canonical: CanonicalSyncResult) -> SyncResult:
        return SyncResult(
            highlights=canonical.highlights,
            books=canonical.books,
            documents=canonical.documents,
            sync_time=canonical.checkpoint.last_sync_time or datetime.now(UTC),
        )

    def _handle_poll_success(self, result: object) -> None:
        self._state.last_poll_time = datetime.now(UTC)
        self._state.poll_count += 1
        self._save_state()
        self._notify_callbacks(cast(SyncResult, result))

    def _handle_poll_error(self, error: Exception) -> None:
        self._state.error_count += 1
        self._state.last_error = str(error)
        self._save_state()
        self._notify_error_callbacks(error)

    def _set_running(self, is_running: bool) -> None:
        self._state.is_running = is_running
        self._save_state()
