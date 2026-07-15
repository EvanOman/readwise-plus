"""Lock the complete public surface of the versioned async clients."""

from __future__ import annotations

import inspect
from typing import Any

from readwise_sdk.v2.async_client import AsyncReadwiseV2Client
from readwise_sdk.v3.async_client import AsyncReadwiseV3Client

V2_SIGNATURES = {
    "list_highlights": "(self, *, page_size: 'int' = 100, book_id: 'int | None' = None, updated_after: 'datetime | None' = None, updated_before: 'datetime | None' = None, highlighted_after: 'datetime | None' = None, highlighted_before: 'datetime | None' = None) -> 'AsyncIterator[Highlight]'",
    "get_highlight": "(self, highlight_id: 'int') -> 'Highlight'",
    "create_highlights": "(self, highlights: 'list[HighlightCreate]') -> 'list[int]'",
    "update_highlight": "(self, highlight_id: 'int', update: 'HighlightUpdate') -> 'Highlight'",
    "delete_highlight": "(self, highlight_id: 'int') -> 'None'",
    "list_books": "(self, *, page_size: 'int' = 100, category: 'BookCategory | None' = None, source: 'str | None' = None, updated_after: 'datetime | None' = None, updated_before: 'datetime | None' = None, last_highlight_after: 'datetime | None' = None, last_highlight_before: 'datetime | None' = None) -> 'AsyncIterator[Book]'",
    "get_book": "(self, book_id: 'int') -> 'Book'",
    "list_highlight_tags": "(self, highlight_id: 'int') -> 'AsyncIterator[Tag]'",
    "create_highlight_tag": "(self, highlight_id: 'int', name: 'str') -> 'Tag'",
    "update_highlight_tag": "(self, highlight_id: 'int', tag_id: 'int', name: 'str') -> 'Tag'",
    "delete_highlight_tag": "(self, highlight_id: 'int', tag_id: 'int') -> 'None'",
    "list_book_tags": "(self, book_id: 'int') -> 'AsyncIterator[Tag]'",
    "create_book_tag": "(self, book_id: 'int', name: 'str') -> 'Tag'",
    "update_book_tag": "(self, book_id: 'int', tag_id: 'int', name: 'str') -> 'Tag'",
    "delete_book_tag": "(self, book_id: 'int', tag_id: 'int') -> 'None'",
    "export_highlights": "(self, *, updated_after: 'datetime | None' = None, book_ids: 'list[int] | None' = None, include_deleted: 'bool' = False) -> 'AsyncIterator[ExportBook]'",
    "get_daily_review": "(self) -> 'DailyReview'",
}

V3_SIGNATURES = {
    "list_documents": "(self, *, location: 'DocumentLocation | None' = None, category: 'DocumentCategory | None' = None, updated_after: 'datetime | None' = None, tags: 'list[str] | None' = None, with_content: 'bool' = False) -> 'AsyncIterator[Document]'",
    "get_document": "(self, document_id: 'str', *, with_content: 'bool' = False) -> 'Document | None'",
    "create_document": "(self, document: 'DocumentCreate') -> 'CreateDocumentResult'",
    "save_url": "(self, url: 'str', *, location: 'DocumentLocation' = <DocumentLocation.NEW: 'new'>, tags: 'list[str] | None' = None, notes: 'str | None' = None) -> 'CreateDocumentResult'",
    "update_document": "(self, document_id: 'str', update: 'DocumentUpdate') -> 'CreateDocumentResult'",
    "delete_document": "(self, document_id: 'str') -> 'None'",
    "move_to_later": "(self, document_id: 'str') -> 'CreateDocumentResult'",
    "archive": "(self, document_id: 'str') -> 'CreateDocumentResult'",
    "move_to_inbox": "(self, document_id: 'str') -> 'CreateDocumentResult'",
    "list_tags": "(self) -> 'AsyncIterator[DocumentTag]'",
    "tag_document": "(self, document_id: 'str', tags: 'list[str]') -> 'CreateDocumentResult'",
    "add_tag": "(self, document_id: 'str', tag: 'str') -> 'CreateDocumentResult'",
    "remove_tag": "(self, document_id: 'str', tag: 'str') -> 'CreateDocumentResult'",
    "get_inbox": "(self) -> 'AsyncIterator[Document]'",
    "get_reading_list": "(self) -> 'AsyncIterator[Document]'",
    "get_archive": "(self) -> 'AsyncIterator[Document]'",
    "get_articles": "(self) -> 'AsyncIterator[Document]'",
}


def _public_methods(client_type: type[Any]) -> dict[str, Any]:
    return {
        name: value
        for name, value in client_type.__dict__.items()
        if not name.startswith("_") and callable(value)
    }


def test_async_v2_public_methods_signatures_and_callable_kinds() -> None:
    methods = _public_methods(AsyncReadwiseV2Client)

    assert {
        name: str(inspect.signature(method)) for name, method in methods.items()
    } == V2_SIGNATURES
    assert {name for name, method in methods.items() if inspect.isasyncgenfunction(method)} == {
        "list_highlights",
        "list_books",
        "list_highlight_tags",
        "list_book_tags",
        "export_highlights",
    }


def test_async_v3_public_methods_signatures_and_callable_kinds() -> None:
    methods = _public_methods(AsyncReadwiseV3Client)

    assert {
        name: str(inspect.signature(method)) for name, method in methods.items()
    } == V3_SIGNATURES
    assert {name for name, method in methods.items() if inspect.isasyncgenfunction(method)} == {
        "list_documents",
        "list_tags",
    }
    assert {
        name
        for name, method in methods.items()
        if not inspect.isasyncgenfunction(method) and not inspect.iscoroutinefunction(method)
    } == {"get_inbox", "get_reading_list", "get_archive", "get_articles"}
