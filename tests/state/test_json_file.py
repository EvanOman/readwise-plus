"""Tests for the canonical JSON synchronization state store."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from readwise_sdk.models import SyncCheckpoint
from readwise_sdk.state import JsonFileStateStore, StateStore

STAMP = datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC)


def test_json_file_state_store_writes_a_versioned_checkpoint(tmp_path) -> None:
    """New canonical writes are versioned without changing ISO formatting."""
    path = tmp_path / "checkpoint.json"
    store = JsonFileStateStore(path)
    checkpoint = SyncCheckpoint(
        last_highlight_sync=STAMP,
        last_book_sync=None,
        last_document_sync=STAMP,
        last_sync_time=STAMP,
    )

    store.save(checkpoint)

    assert isinstance(store, StateStore)
    assert json.loads(path.read_text()) == {
        "version": 1,
        "last_highlight_sync": "2025-02-03T04:05:06+00:00",
        "last_book_sync": None,
        "last_document_sync": "2025-02-03T04:05:06+00:00",
        "last_sync_time": "2025-02-03T04:05:06+00:00",
    }
    assert store.load() == checkpoint


@pytest.mark.parametrize(
    ("legacy_state", "expected"),
    [
        pytest.param(
            {
                "last_highlight_sync": STAMP.isoformat(),
                "last_book_sync": None,
                "last_document_sync": STAMP.isoformat(),
                "total_syncs": 7,
                "last_sync_time": STAMP.isoformat(),
            },
            SyncCheckpoint(
                last_highlight_sync=STAMP,
                last_document_sync=STAMP,
                last_sync_time=STAMP,
            ),
            id="sync-manager",
        ),
        pytest.param(
            {
                "last_highlight_sync": STAMP.isoformat(),
                "last_book_sync": STAMP.isoformat(),
                "last_document_sync": None,
                "total_highlights_synced": 11,
                "total_books_synced": 12,
                "total_documents_synced": 13,
                "last_sync_time": STAMP.isoformat(),
                "errors": ["first"],
            },
            SyncCheckpoint(
                last_highlight_sync=STAMP,
                last_book_sync=STAMP,
                last_sync_time=STAMP,
            ),
            id="batch-sync",
        ),
        pytest.param(
            {
                "last_poll_time": STAMP.isoformat(),
                "last_highlight_sync": STAMP.isoformat(),
                "last_document_sync": None,
                "poll_count": 9,
                "error_count": 2,
                "last_error": "boom",
            },
            SyncCheckpoint(last_highlight_sync=STAMP, last_sync_time=STAMP),
            id="background-poller",
        ),
    ],
)
def test_json_file_state_store_loads_each_legacy_schema(
    tmp_path,
    legacy_state: dict[str, object],
    expected: SyncCheckpoint,
) -> None:
    """Every current persisted schema migrates to one checkpoint model."""
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy_state))

    assert JsonFileStateStore(path).load() == expected


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param("not valid json {{{", id="malformed-json"),
        pytest.param('{"version": 999}', id="unknown-version"),
        pytest.param('{"unrecognized": true}', id="unknown-schema"),
    ],
)
def test_json_file_state_store_rejects_and_preserves_bad_state(tmp_path, contents: str) -> None:
    """Malformed or unknown state is never silently reset or overwritten while loading."""
    path = tmp_path / "bad.json"
    path.write_text(contents)

    with pytest.raises(ValueError):
        JsonFileStateStore(path).load()

    assert path.read_text() == contents
