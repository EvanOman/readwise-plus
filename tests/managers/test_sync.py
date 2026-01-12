"""Tests for SyncManager."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, READWISE_API_V3_BASE, ReadwiseClient
from readwise_sdk.managers.sync import SyncManager, SyncState


class TestSyncState:
    """Tests for SyncState."""

    def test_empty_state(self) -> None:
        """Test empty sync state."""
        state = SyncState()
        assert state.last_highlight_sync is None
        assert state.total_syncs == 0

    def test_state_serialization(self) -> None:
        """Test state serialization and deserialization."""
        state = SyncState(
            last_highlight_sync=datetime(2024, 1, 15, tzinfo=UTC),
            total_syncs=5,
        )

        data = state.to_dict()
        restored = SyncState.from_dict(data)

        assert restored.last_highlight_sync == state.last_highlight_sync
        assert restored.total_syncs == 5


class TestSyncManager:
    """Tests for SyncManager."""

    @respx.mock
    def test_full_sync(self, api_key: str) -> None:
        """Test full sync."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1, "text": "Test"}],
                    "next": None,
                },
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "title": "Book"}], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": "doc1", "url": "https://example.com"}],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = SyncManager(client)
        result = manager.full_sync()

        assert len(result.highlights) == 1
        assert len(result.books) == 1
        assert len(result.documents) == 1
        assert manager.state.total_syncs == 1

    @respx.mock
    def test_incremental_sync(self, api_key: str) -> None:
        """Test incremental sync uses timestamps."""
        route = respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = SyncManager(client)

        # First sync (should not have updated__gt)
        manager.incremental_sync()
        first_request = route.calls[0].request
        assert "updated__gt" not in str(first_request.url)

        # Second sync (should have updated__gt)
        manager.incremental_sync()
        second_request = route.calls[1].request
        assert "updated__gt" in str(second_request.url)

    @respx.mock
    def test_state_persistence(self, api_key: str) -> None:
        """Test state is persisted to file."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sync_state.json"

            client = ReadwiseClient(api_key=api_key)
            manager = SyncManager(client, state_file=state_file)
            manager.full_sync()

            assert state_file.exists()

            # Create new manager and verify state is loaded
            manager2 = SyncManager(client, state_file=state_file)
            assert manager2.state.total_syncs == 1

    @respx.mock
    def test_sync_callback(self, api_key: str) -> None:
        """Test sync callbacks are invoked."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"id": 1, "text": "Test"}], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        callback_results = []

        def callback(result):
            callback_results.append(result)

        client = ReadwiseClient(api_key=api_key)
        manager = SyncManager(client)
        manager.on_sync(callback)
        manager.full_sync()

        assert len(callback_results) == 1
        assert len(callback_results[0].highlights) == 1

    @respx.mock
    def test_reset_state(self, api_key: str) -> None:
        """Test resetting sync state."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "next": None},
            )
        )
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = SyncManager(client)
        manager.full_sync()

        assert manager.state.total_syncs == 1

        manager.reset_state()

        assert manager.state.total_syncs == 0
        assert manager.state.last_highlight_sync is None
