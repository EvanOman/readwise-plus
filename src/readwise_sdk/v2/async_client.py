"""Compatibility facade for asynchronous Readwise API v2 resources."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk.resources.v2.books import AsyncBooksResource
from readwise_sdk.resources.v2.export import AsyncExportResource
from readwise_sdk.resources.v2.highlights import AsyncHighlightsResource
from readwise_sdk.resources.v2.review import AsyncReviewResource
from readwise_sdk.resources.v2.tags import AsyncTagsResource
from readwise_sdk.v2.models import (
    Book,
    BookCategory,
    DailyReview,
    ExportBook,
    Highlight,
    HighlightCreate,
    HighlightUpdate,
    Tag,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from readwise_sdk.client import AsyncReadwiseClient


class AsyncReadwiseV2Client:
    """Preserve the public async v2 API while delegating to resources."""

    def __init__(self, base_client: AsyncReadwiseClient) -> None:
        self._client = base_client
        self._highlights = AsyncHighlightsResource(base_client._transport)
        self._books = AsyncBooksResource(base_client._transport)
        self._tags = AsyncTagsResource(base_client._transport)
        self._export = AsyncExportResource(base_client._transport)
        self._review = AsyncReviewResource(base_client._transport)

    async def list_highlights(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> AsyncIterator[Highlight]:
        async for highlight in self._highlights.iter(
            page_size=page_size,
            book_id=book_id,
            updated_after=updated_after,
            updated_before=updated_before,
            highlighted_after=highlighted_after,
            highlighted_before=highlighted_before,
        ):
            yield highlight

    async def get_highlight(self, highlight_id: int) -> Highlight:
        return await self._highlights.get(highlight_id)

    async def create_highlights(self, highlights: list[HighlightCreate]) -> list[int]:
        return await self._highlights.create(highlights)

    async def update_highlight(self, highlight_id: int, update: HighlightUpdate) -> Highlight:
        return await self._highlights.update(highlight_id, update)

    async def delete_highlight(self, highlight_id: int) -> None:
        await self._highlights.delete(highlight_id)

    async def list_books(
        self,
        *,
        page_size: int = 100,
        category: BookCategory | None = None,
        source: str | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        last_highlight_after: datetime | None = None,
        last_highlight_before: datetime | None = None,
    ) -> AsyncIterator[Book]:
        async for book in self._books.iter(
            page_size=page_size,
            category=category,
            source=source,
            updated_after=updated_after,
            updated_before=updated_before,
            last_highlight_after=last_highlight_after,
            last_highlight_before=last_highlight_before,
        ):
            yield book

    async def get_book(self, book_id: int) -> Book:
        return await self._books.get(book_id)

    async def list_highlight_tags(self, highlight_id: int) -> AsyncIterator[Tag]:
        async for tag in self._tags.iter_highlight(highlight_id):
            yield tag

    async def create_highlight_tag(self, highlight_id: int, name: str) -> Tag:
        return await self._tags.create_highlight(highlight_id, name)

    async def update_highlight_tag(self, highlight_id: int, tag_id: int, name: str) -> Tag:
        return await self._tags.update_highlight(highlight_id, tag_id, name)

    async def delete_highlight_tag(self, highlight_id: int, tag_id: int) -> None:
        await self._tags.delete_highlight(highlight_id, tag_id)

    async def list_book_tags(self, book_id: int) -> AsyncIterator[Tag]:
        async for tag in self._tags.iter_book(book_id):
            yield tag

    async def create_book_tag(self, book_id: int, name: str) -> Tag:
        return await self._tags.create_book(book_id, name)

    async def update_book_tag(self, book_id: int, tag_id: int, name: str) -> Tag:
        return await self._tags.update_book(book_id, tag_id, name)

    async def delete_book_tag(self, book_id: int, tag_id: int) -> None:
        await self._tags.delete_book(book_id, tag_id)

    async def export_highlights(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: list[int] | None = None,
        include_deleted: bool = False,
    ) -> AsyncIterator[ExportBook]:
        async for book in self._export.iter(
            updated_after=updated_after,
            book_ids=book_ids,
            include_deleted=include_deleted,
        ):
            yield book

    async def get_daily_review(self) -> DailyReview:
        return await self._review.get()
