"""Characterize manager result containers and partial-failure behavior."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from readwise_sdk.managers import (
    AsyncDocumentManager,
    AsyncHighlightManager,
    BookManager,
    DocumentManager,
    HighlightManager,
)
from readwise_sdk.managers.books import BookWithHighlights
from readwise_sdk.v2.models import Book, Highlight, Tag
from readwise_sdk.v3.models import Document


def test_sync_manager_collection_methods_materialize_lists() -> None:
    """The three manager families return lists rather than raw iterators."""
    highlight = Highlight(id=1, text="one")
    book = Book(id=2, title="two")
    document = Document(id="three", url="https://example.com/three")
    client: Any = Mock()
    client.v2.list_highlights.return_value = iter([highlight])
    client.v2.list_books.return_value = iter([book])
    client.v3.get_inbox.return_value = iter([document])

    assert HighlightManager(client).get_all_highlights() == [highlight]
    assert BookManager(client).get_all_books() == [book]
    assert DocumentManager(client).get_inbox() == [document]


def test_filter_methods_remain_lazy_iterators_while_search_is_a_list() -> None:
    """Predicate filters are lazy, while manager search eagerly materializes."""
    highlight = Highlight(id=1, text="matching highlight")
    document = Document(id="doc", url="https://example.com", title="Matching document")
    client: Any = Mock()
    client.v2.list_highlights.side_effect = lambda **_kwargs: iter([highlight])
    client.v3.list_documents.side_effect = lambda **_kwargs: iter([document])

    highlight_manager = HighlightManager(client)
    document_manager = DocumentManager(client)
    highlight_filter = highlight_manager.filter_highlights(lambda _item: True)
    document_filter = document_manager.filter_documents(lambda _item: True)

    assert isinstance(highlight_filter, Iterator)
    assert isinstance(document_filter, Iterator)
    assert list(highlight_filter) == [highlight]
    assert list(document_filter) == [document]
    assert highlight_manager.search_highlights("matching") == [highlight]
    assert document_manager.search_documents("matching") == [document]


def test_book_with_highlights_return_shape_is_a_dataclass_with_a_list() -> None:
    """The composed book result retains its named fields and list shape."""
    highlight = Highlight(id=1, text="one")
    book = Book(id=2, title="two")
    client: Any = Mock()
    client.v2.get_book.return_value = book
    client.v2.list_highlights.return_value = iter([highlight])

    result = BookManager(client).get_book_with_highlights(2)

    assert isinstance(result, BookWithHighlights)
    assert result.book is book
    assert isinstance(result.highlights, list)
    assert result.highlights == [highlight]


def test_sync_bulk_operations_return_complete_partial_failure_maps() -> None:
    """Every requested ID is mapped to bool even when individual calls fail."""
    client: Any = Mock()
    client.v2.create_highlight_tag.side_effect = [Tag(id=1, name="tag"), RuntimeError("no")]
    client.v3.archive.side_effect = [None, RuntimeError("no")]
    client.v3.tag_document.side_effect = [RuntimeError("no"), None]

    # NOTE: characterizes current (possibly overly broad) exception suppression.
    assert HighlightManager(client).bulk_tag([1, 2], "tag") == {1: True, 2: False}
    assert DocumentManager(client).bulk_archive(["a", "b"]) == {"a": True, "b": False}
    assert DocumentManager(client).bulk_tag_documents(["a", "b"], ["tag"]) == {
        "a": False,
        "b": True,
    }


@pytest.mark.asyncio
async def test_async_manager_lists_iterators_and_partial_failure_maps() -> None:
    """Async managers preserve list, async-iterator, and bool-map shapes."""
    highlight = Highlight(id=1, text="one")
    document = Document(id="doc", url="https://example.com")
    client: Any = Mock()

    async def highlights() -> AsyncIterator[Highlight]:
        yield highlight

    async def documents(**_kwargs: Any) -> AsyncIterator[Document]:
        yield document

    client.v2.list_highlights = highlights
    client.v3.list_documents = documents
    client.v3.archive = AsyncMock(side_effect=[None, RuntimeError("no")])

    highlight_manager = AsyncHighlightManager(client)
    document_manager = AsyncDocumentManager(client)
    assert await highlight_manager.get_all_highlights() == [highlight]
    filtered = document_manager.filter_documents(lambda _item: True)
    assert isinstance(filtered, AsyncIterator)
    assert [item async for item in filtered] == [document]
    # NOTE: characterizes current (possibly overly broad) exception suppression.
    assert await document_manager.bulk_archive(["a", "b"]) == {"a": True, "b": False}
