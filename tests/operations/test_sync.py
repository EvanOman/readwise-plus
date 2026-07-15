"""Tests for canonical synchronization operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from readwise_sdk.models import SyncCheckpoint
from readwise_sdk.operations.sync import SyncOperations
from readwise_sdk.state import JsonFileStateStore
from readwise_sdk.v2.models import Book, Highlight
from readwise_sdk.v3.models import Document

STAMP = datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC)


class FakeAsyncResource[ItemT]:
    """Record incremental cursors while yielding fixed items."""

    def __init__(self, items: list[ItemT]) -> None:
        self.items = items
        self.updated_after_calls: list[datetime | None] = []

    async def iter(self, **kwargs: Any) -> AsyncIterator[ItemT]:
        self.updated_after_calls.append(kwargs.get("updated_after"))
        for item in self.items:
            yield item


@pytest.mark.asyncio
async def test_full_sync_fetches_all_resources_and_persists_checkpoint(tmp_path) -> None:
    """A full sync materializes all resource streams through one operation."""
    highlights = FakeAsyncResource([Highlight(id=1, text="Passage")])
    books = FakeAsyncResource([Book(id=2, title="Book")])
    documents = FakeAsyncResource([Document(id="doc-1", url="https://example.com")])
    store = JsonFileStateStore(tmp_path / "checkpoint.json")
    sync = SyncOperations(
        highlights=highlights,
        books=books,
        documents=documents,
        state_store=store,
    )

    result = await sync.full()

    assert [item.id for item in result.highlights] == [1]
    assert [item.id for item in result.books] == [2]
    assert [item.id for item in result.documents] == ["doc-1"]
    assert highlights.updated_after_calls == [None]
    assert books.updated_after_calls == [None]
    assert documents.updated_after_calls == [None]
    assert store.load() == result.checkpoint


@pytest.mark.asyncio
async def test_incremental_sync_uses_each_saved_resource_cursor(tmp_path) -> None:
    """Incremental sync reads the checkpoint and advances only included resources."""
    store = JsonFileStateStore(tmp_path / "checkpoint.json")
    store.save(
        SyncCheckpoint(
            last_highlight_sync=STAMP,
            last_book_sync=STAMP,
            last_document_sync=STAMP,
            last_sync_time=STAMP,
        )
    )
    highlights: FakeAsyncResource[Highlight] = FakeAsyncResource([])
    books: FakeAsyncResource[Book] = FakeAsyncResource([])
    documents: FakeAsyncResource[Document] = FakeAsyncResource([])
    sync = SyncOperations(
        highlights=highlights,
        books=books,
        documents=documents,
        state_store=store,
    )

    result = await sync.incremental(include_books=False)

    assert highlights.updated_after_calls == [STAMP]
    assert books.updated_after_calls == []
    assert documents.updated_after_calls == [STAMP]
    assert result.checkpoint.last_book_sync == STAMP
    assert result.checkpoint.last_highlight_sync is not None
    assert result.checkpoint.last_document_sync is not None
    assert result.checkpoint.last_highlight_sync > STAMP
    assert result.checkpoint.last_document_sync > STAMP


@pytest.mark.asyncio
async def test_poll_once_fetches_books_with_the_highlight_cursor(tmp_path) -> None:
    """Poll-once retains the poller's coupled highlight/book incremental behavior."""
    store = JsonFileStateStore(tmp_path / "checkpoint.json")
    store.save(SyncCheckpoint(last_highlight_sync=STAMP, last_document_sync=STAMP))
    highlights: FakeAsyncResource[Highlight] = FakeAsyncResource([])
    books: FakeAsyncResource[Book] = FakeAsyncResource([])
    documents: FakeAsyncResource[Document] = FakeAsyncResource([])
    sync = SyncOperations(
        highlights=highlights,
        books=books,
        documents=documents,
        state_store=store,
    )

    await sync.poll_once()

    assert highlights.updated_after_calls == [STAMP]
    assert books.updated_after_calls == [STAMP]
    assert documents.updated_after_calls == [STAMP]


@pytest.mark.asyncio
async def test_batch_callbacks_preserve_continue_on_error_semantics() -> None:
    """Item callback failures are counted and later items continue when configured."""
    highlights = FakeAsyncResource(
        [Highlight(id=1, text="one"), Highlight(id=2, text="two"), Highlight(id=3, text="three")]
    )
    sync = SyncOperations(highlights=highlights)
    received: list[int] = []

    async def on_item(highlight: Highlight) -> None:
        received.append(highlight.id)
        if highlight.id == 2:
            raise RuntimeError("callback failed")

    result = await sync.batch_highlights(on_item=on_item, continue_on_error=True)

    assert received == [1, 2, 3]
    assert result.success is True
    assert result.new_items == 2
    assert result.failed_items == 1
    assert result.errors == ["Error processing highlight 2: callback failed"]
