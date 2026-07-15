"""Lock the incompatible state-file schemas written by current sync helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

from readwise_sdk.contrib.batch_sync import BatchSync, BatchSyncConfig
from readwise_sdk.managers.async_managers import AsyncSyncManager
from readwise_sdk.managers.sync import SyncManager, SyncResult
from readwise_sdk.workflows.poller import BackgroundPoller, PollerConfig

STAMP = datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC)


def test_sync_manager_writes_its_exact_json_schema(tmp_path) -> None:
    """SyncManager persists five fields with ISO strings and nulls."""
    state_file = tmp_path / "sync-manager.json"
    client: Any = Mock()
    manager = SyncManager(client, state_file=state_file)
    manager.state.last_highlight_sync = STAMP
    manager.state.last_book_sync = None
    manager.state.last_document_sync = STAMP
    manager.state.total_syncs = 7
    manager.state.last_sync_time = STAMP

    manager._save_state()

    assert json.loads(state_file.read_text()) == {
        "last_highlight_sync": "2025-02-03T04:05:06+00:00",
        "last_book_sync": None,
        "last_document_sync": "2025-02-03T04:05:06+00:00",
        "total_syncs": 7,
        "last_sync_time": "2025-02-03T04:05:06+00:00",
    }


def test_batch_sync_writes_its_exact_json_schema(tmp_path) -> None:
    """BatchSync uses per-resource totals and a bounded errors list."""
    state_file = tmp_path / "batch-sync.json"
    client: Any = Mock()
    sync = BatchSync(client, config=BatchSyncConfig(state_file=state_file))
    sync.state.last_highlight_sync = STAMP
    sync.state.last_book_sync = None
    sync.state.last_document_sync = STAMP
    sync.state.total_highlights_synced = 11
    sync.state.total_books_synced = 12
    sync.state.total_documents_synced = 13
    sync.state.last_sync_time = STAMP
    sync.state.errors = ["first", "second"]

    sync._save_state()

    assert json.loads(state_file.read_text()) == {
        "last_highlight_sync": "2025-02-03T04:05:06+00:00",
        "last_book_sync": None,
        "last_document_sync": "2025-02-03T04:05:06+00:00",
        "total_highlights_synced": 11,
        "total_books_synced": 12,
        "total_documents_synced": 13,
        "last_sync_time": "2025-02-03T04:05:06+00:00",
        "errors": ["first", "second"],
    }


def test_background_poller_writes_its_exact_json_schema(tmp_path) -> None:
    """Poller state omits its in-memory is_running flag from disk."""
    state_file = tmp_path / "poller.json"
    client: Any = Mock()
    poller = BackgroundPoller(client, config=PollerConfig(state_file=state_file))
    poller.state.last_poll_time = STAMP
    poller.state.last_highlight_sync = STAMP
    poller.state.last_document_sync = None
    poller.state.poll_count = 9
    poller.state.error_count = 2
    poller.state.last_error = "boom"
    poller.state.is_running = True

    poller._save_state()

    # NOTE: characterizes current behavior: is_running is deliberately absent on disk.
    assert json.loads(state_file.read_text()) == {
        "last_poll_time": "2025-02-03T04:05:06+00:00",
        "last_highlight_sync": "2025-02-03T04:05:06+00:00",
        "last_document_sync": None,
        "poll_count": 9,
        "error_count": 2,
        "last_error": "boom",
    }


def test_sync_manager_suppresses_callback_exceptions_and_continues() -> None:
    """One broken callback does not prevent later callbacks from running."""
    client: Any = Mock()
    manager = SyncManager(client)
    received: list[SyncResult] = []

    def broken(_result: SyncResult) -> None:
        raise RuntimeError("callback failed")

    manager.on_sync(broken)
    manager.on_sync(received.append)
    result = SyncResult(sync_time=STAMP)

    # NOTE: characterizes current callback-exception suppression.
    manager._notify_callbacks(result)
    assert received == [result]


def test_async_sync_manager_suppresses_callback_exceptions_and_continues() -> None:
    """AsyncSyncManager callbacks are synchronous and suppress exceptions too."""
    client: Any = Mock()
    manager = AsyncSyncManager(client)
    received: list[SyncResult] = []

    def broken(_result: SyncResult) -> None:
        raise RuntimeError("callback failed")

    manager.on_sync(broken)
    manager.on_sync(received.append)
    result = SyncResult(sync_time=STAMP)

    # NOTE: characterizes current callback-exception suppression.
    manager._notify_callbacks(result)
    assert received == [result]


def test_poller_suppresses_both_sync_and_error_callback_exceptions() -> None:
    """Poller continues through failures in both callback registries."""
    client: Any = Mock()
    poller = BackgroundPoller(client)
    sync_received: list[SyncResult] = []
    errors_received: list[Exception] = []

    def broken(_value: object) -> None:
        raise RuntimeError("callback failed")

    result = SyncResult(sync_time=STAMP)
    error = ValueError("poll failed")
    poller.on_sync(broken)
    poller.on_sync(sync_received.append)
    poller.on_error(broken)
    poller.on_error(errors_received.append)

    # NOTE: characterizes current callback-exception suppression.
    poller._notify_callbacks(result)
    poller._notify_error_callbacks(error)
    assert sync_received == [result]
    assert errors_received == [error]
