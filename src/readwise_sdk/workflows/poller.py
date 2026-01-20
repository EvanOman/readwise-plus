"""Background poller for continuous sync operations."""

from __future__ import annotations

import json
import signal
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from readwise_sdk._utils import parse_datetime_string
from readwise_sdk.managers.sync import SyncResult

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
        self._state = self._load_state()
        self._callbacks: list[Callable[[SyncResult], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._consecutive_errors = 0
        self._current_backoff = self._config.poll_interval
        self._lock = threading.Lock()

    def _load_state(self) -> PollerState:
        """Load state from file if it exists."""
        if self._config.state_file and self._config.state_file.exists():
            try:
                data = json.loads(self._config.state_file.read_text())
                return PollerState.from_dict(data)
            except Exception:
                pass
        return PollerState()

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if self._config.state_file:
            self._config.state_file.parent.mkdir(parents=True, exist_ok=True)
            self._config.state_file.write_text(json.dumps(self._state.to_dict(), indent=2))

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
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass

    def _notify_error_callbacks(self, error: Exception) -> None:
        """Notify all error callbacks."""
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception:
                pass

    def _do_poll(self) -> SyncResult:
        """Perform a single poll operation."""
        from readwise_sdk.managers.sync import SyncResult as SR

        now = datetime.now(UTC)
        result = SR(sync_time=now)

        if self._config.include_highlights:
            since = self._state.last_highlight_sync
            if since:
                result.highlights = list(self._client.v2.list_highlights(updated_after=since))
            else:
                result.highlights = list(self._client.v2.list_highlights())

            # Also fetch books if we're fetching highlights
            if since:
                result.books = list(self._client.v2.list_books(updated_after=since))
            else:
                result.books = list(self._client.v2.list_books())

            self._state.last_highlight_sync = now

        if self._config.include_documents:
            since = self._state.last_document_sync
            if since:
                result.documents = list(self._client.v3.list_documents(updated_after=since))
            else:
                result.documents = list(self._client.v3.list_documents())
            self._state.last_document_sync = now

        return result

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_event.is_set():
            try:
                result = self._do_poll()

                with self._lock:
                    self._state.last_poll_time = datetime.now(UTC)
                    self._state.poll_count += 1
                    self._consecutive_errors = 0
                    self._current_backoff = self._config.poll_interval

                self._save_state()
                self._notify_callbacks(result)

            except Exception as e:
                with self._lock:
                    self._state.error_count += 1
                    self._state.last_error = str(e)
                    self._consecutive_errors += 1

                    # Calculate backoff
                    self._current_backoff = min(
                        self._current_backoff * self._config.backoff_multiplier,
                        self._config.max_backoff,
                    )

                self._save_state()
                self._notify_error_callbacks(e)

                # Check if we should stop due to too many errors
                if self._consecutive_errors >= self._config.max_consecutive_errors:
                    self._state.is_running = False
                    self._save_state()
                    return

            # Wait for next poll or stop event
            wait_time = (
                self._current_backoff
                if self._consecutive_errors > 0
                else self._config.poll_interval
            )
            self._stop_event.wait(wait_time)

        self._state.is_running = False
        self._save_state()

    def start(self, *, blocking: bool = False) -> None:
        """Start the background poller.

        Args:
            blocking: If True, run in the current thread (blocking).
                     If False, run in a background thread.
        """
        if self._state.is_running:
            return

        self._stop_event.clear()
        self._state.is_running = True
        self._save_state()

        if blocking:
            self._poll_loop()
        else:
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()

    def stop(self, *, timeout: float | None = None) -> None:
        """Stop the background poller.

        Args:
            timeout: Maximum time to wait for the poller to stop.
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._state.is_running = False
        self._save_state()

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
        with self._lock:
            self._consecutive_errors = 0
            self._current_backoff = self._config.poll_interval
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
