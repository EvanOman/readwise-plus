"""Compatibility adapters that let legacy clients use canonical operations.

The canonical operation classes are async-first.  These adapters expose the
existing sync and async versioned clients through the resource protocols those
operations consume.  Sync adapters deliberately never suspend, which lets the
legacy synchronous shims drive them in the caller's thread.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Iterator
from typing import Any, cast

from readwise_sdk.models import BulkResult
from readwise_sdk.models.reader import DocumentCreate, DocumentLocation, DocumentUpdate
from readwise_sdk.models.readwise import HighlightCreate, HighlightUpdate


def run_sync[ResultT](awaitable: Awaitable[ResultT]) -> ResultT:
    """Drive a non-suspending compatibility coroutine in the current thread."""
    iterator = awaitable.__await__()
    try:
        next(iterator)
    except StopIteration as completed:
        return cast(ResultT, completed.value)
    finally:
        iterator.close()
    raise RuntimeError("A synchronous compatibility resource unexpectedly suspended")


def iter_sync[ItemT](iterator: AsyncIterator[ItemT]) -> Iterator[ItemT]:
    """Adapt a non-suspending async iterator without sacrificing laziness."""
    while True:
        try:
            yield run_sync(iterator.__anext__())
        except StopAsyncIteration:
            return


def bulk_result_map[ItemT](items: list[ItemT], result: BulkResult[ItemT]) -> dict[ItemT, bool]:
    """Convert a typed bulk result to the complete ordered legacy bool map."""
    failed = {cast(ItemT, failure.item) for failure in result.failures}
    return {item: item not in failed for item in items}


class SyncHighlightsResource:
    """Expose a synchronous legacy v2 client as async-first resources."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def iter(self, **kwargs: Any) -> AsyncIterator[Any]:
        kwargs.pop("page_size", None)
        for item in self._client.v2.list_highlights(**_without_none(kwargs)):
            yield item

    async def get(self, highlight_id: int) -> Any:
        return self._client.v2.get_highlight(highlight_id)

    async def create(self, highlights: list[HighlightCreate]) -> list[int]:
        return self._client.v2.create_highlights(highlights)

    async def update(self, highlight_id: int, update: HighlightUpdate) -> Any:
        return self._client.v2.update_highlight(highlight_id, update)

    async def delete(self, highlight_id: int) -> None:
        self._client.v2.delete_highlight(highlight_id)

    async def iter_highlight(self, highlight_id: int) -> AsyncIterator[Any]:
        for item in self._client.v2.list_highlight_tags(highlight_id):
            yield item

    async def create_highlight(self, highlight_id: int, name: str) -> Any:
        return self._client.v2.create_highlight_tag(highlight_id, name)

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None:
        self._client.v2.delete_highlight_tag(highlight_id, tag_id)

    async def export(self, **kwargs: Any) -> AsyncIterator[Any]:
        for item in self._client.v2.export_highlights(**_without_none(kwargs)):
            yield item

    async def validate_token(self) -> bool:
        return self._client.validate_token()


class AsyncHighlightsResource:
    """Expose an asynchronous legacy v2 client as canonical resources."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def iter(self, **kwargs: Any) -> AsyncIterator[Any]:
        kwargs.pop("page_size", None)
        async for item in self._client.v2.list_highlights(**_without_none(kwargs)):
            yield item

    async def get(self, highlight_id: int) -> Any:
        return await self._client.v2.get_highlight(highlight_id)

    async def create(self, highlights: list[HighlightCreate]) -> list[int]:
        return await self._client.v2.create_highlights(highlights)

    async def update(self, highlight_id: int, update: HighlightUpdate) -> Any:
        return await self._client.v2.update_highlight(highlight_id, update)

    async def delete(self, highlight_id: int) -> None:
        await self._client.v2.delete_highlight(highlight_id)

    async def iter_highlight(self, highlight_id: int) -> AsyncIterator[Any]:
        async for item in self._client.v2.list_highlight_tags(highlight_id):
            yield item

    async def create_highlight(self, highlight_id: int, name: str) -> Any:
        return await self._client.v2.create_highlight_tag(highlight_id, name)

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None:
        await self._client.v2.delete_highlight_tag(highlight_id, tag_id)

    async def export(self, **kwargs: Any) -> AsyncIterator[Any]:
        async for item in self._client.v2.export_highlights(**_without_none(kwargs)):
            yield item

    async def validate_token(self) -> bool:
        return await self._client.validate_token()


class SyncBooksResource:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def iter(self, **kwargs: Any) -> AsyncIterator[Any]:
        kwargs.pop("page_size", None)
        for item in self._client.v2.list_books(**_without_none(kwargs)):
            yield item

    async def get(self, book_id: int) -> Any:
        return self._client.v2.get_book(book_id)


class AsyncBooksResource:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def iter(self, **kwargs: Any) -> AsyncIterator[Any]:
        kwargs.pop("page_size", None)
        async for item in self._client.v2.list_books(**_without_none(kwargs)):
            yield item

    async def get(self, book_id: int) -> Any:
        return await self._client.v2.get_book(book_id)


class SyncDocumentsResource:
    def __init__(self, client: Any, *, manager_compat: bool = False) -> None:
        self._client = client
        self._manager_compat = manager_compat

    async def iter(self, **kwargs: Any) -> AsyncIterator[Any]:
        source = self._document_iterator(kwargs)
        for item in source:
            yield item

    def _document_iterator(self, kwargs: dict[str, Any]) -> Iterator[Any]:
        location = kwargs.get("location")
        if self._manager_compat and _is_plain_view(kwargs):
            if location == DocumentLocation.NEW:
                return self._client.v3.get_inbox()
            if location == DocumentLocation.LATER:
                return self._client.v3.get_reading_list()
            if location == DocumentLocation.ARCHIVE:
                return self._client.v3.get_archive()
        return self._client.v3.list_documents(**_without_none(kwargs))

    async def get(self, document_id: str, *, with_content: bool = False) -> Any:
        return self._client.v3.get_document(document_id, with_content=with_content)

    async def create(self, document: DocumentCreate) -> Any:
        return self._client.v3.create_document(document)

    async def save_url(self, url: str, **kwargs: Any) -> Any:
        return self._client.v3.save_url(url, **kwargs)

    async def update(self, document_id: str, update: DocumentUpdate) -> Any:
        if self._manager_compat:
            fields = update.model_dump(exclude_none=True)
            if set(fields) == {"location"}:
                location = update.location
                if location == DocumentLocation.NEW:
                    return self._client.v3.move_to_inbox(document_id)
                if location == DocumentLocation.LATER:
                    return self._client.v3.move_to_later(document_id)
                if location == DocumentLocation.ARCHIVE:
                    return self._client.v3.archive(document_id)
            if set(fields) == {"tags"}:
                return self._client.v3.tag_document(document_id, update.tags or [])
        return self._client.v3.update_document(document_id, update)

    async def delete(self, document_id: str) -> None:
        self._client.v3.delete_document(document_id)


class AsyncDocumentsResource:
    def __init__(self, client: Any, *, manager_compat: bool = False) -> None:
        self._client = client
        self._manager_compat = manager_compat

    async def iter(self, **kwargs: Any) -> AsyncIterator[Any]:
        source = self._document_iterator(kwargs)
        async for item in source:
            yield item

    def _document_iterator(self, kwargs: dict[str, Any]) -> AsyncIterator[Any]:
        location = kwargs.get("location")
        if self._manager_compat and _is_plain_view(kwargs):
            if location == DocumentLocation.NEW:
                return self._client.v3.get_inbox()
            if location == DocumentLocation.LATER:
                return self._client.v3.get_reading_list()
            if location == DocumentLocation.ARCHIVE:
                return self._client.v3.get_archive()
        return self._client.v3.list_documents(**_without_none(kwargs))

    async def get(self, document_id: str, *, with_content: bool = False) -> Any:
        return await self._client.v3.get_document(document_id, with_content=with_content)

    async def create(self, document: DocumentCreate) -> Any:
        return await self._client.v3.create_document(document)

    async def save_url(self, url: str, **kwargs: Any) -> Any:
        return await self._client.v3.save_url(url, **kwargs)

    async def update(self, document_id: str, update: DocumentUpdate) -> Any:
        if self._manager_compat:
            fields = update.model_dump(exclude_none=True)
            if set(fields) == {"location"}:
                location = update.location
                if location == DocumentLocation.NEW:
                    return await self._client.v3.move_to_inbox(document_id)
                if location == DocumentLocation.LATER:
                    return await self._client.v3.move_to_later(document_id)
                if location == DocumentLocation.ARCHIVE:
                    return await self._client.v3.archive(document_id)
            if set(fields) == {"tags"}:
                return await self._client.v3.tag_document(document_id, update.tags or [])
        return await self._client.v3.update_document(document_id, update)

    async def delete(self, document_id: str) -> None:
        await self._client.v3.delete_document(document_id)


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _is_plain_view(kwargs: dict[str, Any]) -> bool:
    return (
        kwargs.get("location") is not None
        and kwargs.get("category") is None
        and kwargs.get("updated_after") is None
        and kwargs.get("tags") is None
        and not kwargs.get("with_content", False)
    )


__all__ = [
    "AsyncBooksResource",
    "AsyncDocumentsResource",
    "AsyncHighlightsResource",
    "SyncBooksResource",
    "SyncDocumentsResource",
    "SyncHighlightsResource",
    "bulk_result_map",
    "iter_sync",
    "run_sync",
]
