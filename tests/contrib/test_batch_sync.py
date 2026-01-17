"""Tests for BatchSync."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.contrib.batch_sync import (
    BatchSync,
    BatchSyncConfig,
    BatchSyncResult,
    SyncState,
)
from readwise_sdk.v2.models import Book, Highlight


class TestSyncState:
    """Tests for SyncState dataclass."""

    def test_empty_state(self) -> None:
        """Test creating empty sync state."""
        state = SyncState()

        assert state.last_highlight_sync is None
        assert state.last_book_sync is None
        assert state.total_highlights_synced == 0
        assert state.total_books_synced == 0
        assert state.errors == []

    def test_state_to_dict(self) -> None:
        """Test converting state to dictionary."""
        now = datetime.now(UTC)
        state = SyncState(
            last_highlight_sync=now,
            last_book_sync=now,
            total_highlights_synced=100,
            total_books_synced=50,
            last_sync_time=now,
            errors=["error1", "error2"],
        )

        data = state.to_dict()

        assert data["last_highlight_sync"] == now.isoformat()
        assert data["last_book_sync"] == now.isoformat()
        assert data["total_highlights_synced"] == 100
        assert data["total_books_synced"] == 50
        assert data["errors"] == ["error1", "error2"]

    def test_state_from_dict(self) -> None:
        """Test creating state from dictionary."""
        now = datetime.now(UTC)
        data = {
            "last_highlight_sync": now.isoformat(),
            "last_book_sync": now.isoformat(),
            "total_highlights_synced": 100,
            "total_books_synced": 50,
            "last_sync_time": now.isoformat(),
            "errors": ["error1"],
        }

        state = SyncState.from_dict(data)

        assert state.last_highlight_sync is not None
        assert state.total_highlights_synced == 100
        assert state.total_books_synced == 50
        assert state.errors == ["error1"]

    def test_state_from_dict_empty(self) -> None:
        """Test creating state from empty dictionary."""
        state = SyncState.from_dict({})

        assert state.last_highlight_sync is None
        assert state.total_highlights_synced == 0
        assert state.errors == []

    def test_state_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        now = datetime.now(UTC)
        original = SyncState(
            last_highlight_sync=now,
            last_book_sync=now,
            total_highlights_synced=42,
            total_books_synced=10,
            last_sync_time=now,
        )

        # Convert to dict and back
        data = original.to_dict()
        restored = SyncState.from_dict(data)

        assert restored.total_highlights_synced == 42
        assert restored.total_books_synced == 10

    def test_state_error_limit(self) -> None:
        """Test that errors are limited in to_dict."""
        # Create state with >100 errors
        state = SyncState(errors=[f"error{i}" for i in range(150)])

        data = state.to_dict()

        # Should only keep last 100
        assert len(data["errors"]) == 100


class TestBatchSyncConfig:
    """Tests for BatchSyncConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = BatchSyncConfig()

        assert config.batch_size == 100
        assert config.state_file is None
        assert config.continue_on_error is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = BatchSyncConfig(
            batch_size=50,
            state_file="sync.json",
            continue_on_error=False,
        )

        assert config.batch_size == 50
        assert config.state_file == "sync.json"
        assert config.continue_on_error is False


class TestBatchSyncResult:
    """Tests for BatchSyncResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful sync result."""
        result = BatchSyncResult(
            success=True,
            new_items=100,
            updated_items=10,
            failed_items=0,
        )

        assert result.success is True
        assert result.new_items == 100
        assert result.errors == []

    def test_failure_result(self) -> None:
        """Test failed sync result."""
        result = BatchSyncResult(
            success=False,
            new_items=50,
            failed_items=5,
            errors=["Error 1", "Error 2"],
        )

        assert result.success is False
        assert result.failed_items == 5
        assert len(result.errors) == 2


class TestBatchSync:
    """Tests for BatchSync class."""

    @respx.mock
    def test_sync_highlights(self, api_key: str) -> None:
        """Test syncing highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Highlight 1"},
                        {"id": 2, "text": "Highlight 2"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        result = sync.sync_highlights()

        assert result.success is True
        assert result.new_items == 2
        assert sync.state.total_highlights_synced == 2

    @respx.mock
    def test_sync_highlights_with_callback(self, api_key: str) -> None:
        """Test syncing highlights with item callback."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Highlight 1"},
                        {"id": 2, "text": "Highlight 2"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        received_highlights = []

        def on_item(h: Highlight) -> None:
            received_highlights.append(h)

        result = sync.sync_highlights(on_item=on_item)

        assert result.success is True
        assert len(received_highlights) == 2
        assert received_highlights[0].id == 1

    @respx.mock
    def test_sync_highlights_with_batch_callback(self, api_key: str) -> None:
        """Test syncing highlights with batch callback."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": i, "text": f"H{i}"} for i in range(150)],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        config = BatchSyncConfig(batch_size=50)
        sync = BatchSync(client, config=config)

        batches = []

        def on_batch(b: list[Highlight]) -> None:
            batches.append(len(b))

        result = sync.sync_highlights(on_batch=on_batch)

        assert result.success is True
        assert result.new_items == 150
        # Should have had batches of 50 + 50 + 50
        assert len(batches) == 3
        assert batches[0] == 50

    @respx.mock
    def test_sync_books(self, api_key: str) -> None:
        """Test syncing books."""
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "title": "Book 1"},
                        {"id": 2, "title": "Book 2"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        result = sync.sync_books()

        assert result.success is True
        assert result.new_items == 2
        assert sync.state.total_books_synced == 2

    @respx.mock
    def test_sync_books_with_callback(self, api_key: str) -> None:
        """Test syncing books with callback."""
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "title": "Book 1"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        received_books = []

        def on_item(b: Book) -> None:
            received_books.append(b)

        result = sync.sync_books(on_item=on_item)

        assert result.success is True
        assert len(received_books) == 1

    @respx.mock
    def test_sync_all(self, api_key: str) -> None:
        """Test syncing both highlights and books."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "text": "H1"}], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "title": "B1"}], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        h_result, b_result = sync.sync_all()

        assert h_result.success is True
        assert h_result.new_items == 1
        assert b_result.success is True
        assert b_result.new_items == 1

    @respx.mock
    def test_incremental_sync(self, api_key: str) -> None:
        """Test incremental sync uses last sync time."""
        route = respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "text": "H1"}], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        # First sync
        sync.sync_highlights()

        # Second sync should be incremental
        sync.sync_highlights()

        # Check that updated_after was used in second request
        last_request = route.calls.last.request
        assert "updated__gt" in str(last_request.url)

    @respx.mock
    def test_full_sync_ignores_last_sync(self, api_key: str) -> None:
        """Test full sync ignores last sync time."""
        route = respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "text": "H1"}], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        # First sync
        sync.sync_highlights()

        # Full sync should not use updated_after
        sync.sync_highlights(full_sync=True)

        # Check request
        last_request = route.calls.last.request
        assert "updated__gt" not in str(last_request.url)

    @respx.mock
    def test_state_persistence(self, api_key: str) -> None:
        """Test state is persisted to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sync_state.json"

            respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
                return_value=httpx.Response(
                    200,
                    json={"results": [{"id": 1, "text": "H1"}], "next": None},
                )
            )

            client = ReadwiseClient(api_key=api_key)
            config = BatchSyncConfig(state_file=state_file)
            sync = BatchSync(client, config=config)

            sync.sync_highlights()

            # Verify file was created
            assert state_file.exists()

            # Verify content
            data = json.loads(state_file.read_text())
            assert data["total_highlights_synced"] == 1

    @respx.mock
    def test_state_restoration(self, api_key: str) -> None:
        """Test state is restored from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sync_state.json"

            # Create existing state file
            existing_state = {
                "last_highlight_sync": datetime.now(UTC).isoformat(),
                "total_highlights_synced": 100,
                "total_books_synced": 50,
            }
            state_file.write_text(json.dumps(existing_state))

            client = ReadwiseClient(api_key=api_key)
            config = BatchSyncConfig(state_file=state_file)
            sync = BatchSync(client, config=config)

            assert sync.state.total_highlights_synced == 100
            assert sync.state.total_books_synced == 50

    @respx.mock
    def test_reset_state(self, api_key: str) -> None:
        """Test resetting sync state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sync_state.json"

            respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
                return_value=httpx.Response(
                    200,
                    json={"results": [{"id": 1, "text": "H1"}], "next": None},
                )
            )

            client = ReadwiseClient(api_key=api_key)
            config = BatchSyncConfig(state_file=state_file)
            sync = BatchSync(client, config=config)

            sync.sync_highlights()
            assert sync.state.total_highlights_synced == 1

            sync.reset_state()
            assert sync.state.total_highlights_synced == 0
            assert sync.state.last_highlight_sync is None

    @respx.mock
    def test_get_stats(self, api_key: str) -> None:
        """Test getting sync statistics."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": i, "text": f"H{i}"} for i in range(5)], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": i, "title": f"B{i}"} for i in range(3)], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        sync.sync_highlights()
        sync.sync_books()

        stats = sync.get_stats()

        assert stats["total_highlights_synced"] == 5
        assert stats["total_books_synced"] == 3
        assert stats["error_count"] == 0

    @respx.mock
    def test_sync_api_failure(self, api_key: str) -> None:
        """Test handling API failure during sync."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        result = sync.sync_highlights()

        assert result.success is False
        assert len(result.errors) > 0

    @respx.mock
    def test_callback_error_continues(self, api_key: str) -> None:
        """Test that callback errors don't stop sync when continue_on_error=True."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "H1"},
                        {"id": 2, "text": "H2"},
                        {"id": 3, "text": "H3"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        config = BatchSyncConfig(continue_on_error=True)
        sync = BatchSync(client, config=config)

        call_count = 0

        def on_item(h: Highlight) -> None:
            nonlocal call_count
            call_count += 1
            if h.id == 2:
                raise ValueError("Test error")

        result = sync.sync_highlights(on_item=on_item)

        # Should have processed all 3 items despite error
        assert call_count == 3
        assert result.success is True
        # Items that error during callback are counted as failed, not new
        assert result.new_items == 2
        assert result.failed_items == 1
        assert len(result.errors) == 1

    @respx.mock
    def test_callback_error_stops(self, api_key: str) -> None:
        """Test that callback errors stop sync when continue_on_error=False."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "H1"},
                        {"id": 2, "text": "H2"},
                        {"id": 3, "text": "H3"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        config = BatchSyncConfig(continue_on_error=False)
        sync = BatchSync(client, config=config)

        call_count = 0

        def on_item(h: Highlight) -> None:
            nonlocal call_count
            call_count += 1
            if h.id == 2:
                raise ValueError("Test error")

        result = sync.sync_highlights(on_item=on_item)

        # Should have stopped after error on item 2
        assert call_count == 2
        assert result.success is False
        assert result.new_items == 1  # Only first item counted before error
        assert result.failed_items == 1

    def test_state_property(self, api_key: str) -> None:
        """Test state property access."""
        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        state = sync.state

        assert isinstance(state, SyncState)
        assert state.total_highlights_synced == 0

    @respx.mock
    def test_sync_cumulative_counts(self, api_key: str) -> None:
        """Test that sync counts are cumulative across multiple syncs."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "text": "H1"}], "next": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        sync = BatchSync(client)

        # First sync
        sync.sync_highlights(full_sync=True)
        assert sync.state.total_highlights_synced == 1

        # Second sync
        sync.sync_highlights(full_sync=True)
        assert sync.state.total_highlights_synced == 2
