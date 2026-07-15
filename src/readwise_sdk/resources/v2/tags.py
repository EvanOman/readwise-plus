"""Asynchronous access to Readwise v2 tag endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator

from readwise_sdk.models.readwise import Tag
from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.pagination import StandardV2Page, paginate_async


class AsyncTagsResource:
    """Build highlight/book tag requests and decode tag models."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def iter_highlight(self, highlight_id: int) -> AsyncIterator[Tag]:
        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/tags/",
            decoder=StandardV2Page(),
        ):
            yield Tag.model_validate(item)

    async def create_highlight(self, highlight_id: int, name: str) -> Tag:
        response = await self._transport.post(
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/tags/",
            json={"name": name[:127]},
        )
        return Tag.model_validate(response.json())

    async def update_highlight(self, highlight_id: int, tag_id: int, name: str) -> Tag:
        response = await self._transport.patch(
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/tags/{tag_id}/",
            json={"name": name[:127]},
        )
        return Tag.model_validate(response.json())

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None:
        await self._transport.delete(
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/tags/{tag_id}/"
        )

    async def iter_book(self, book_id: int) -> AsyncIterator[Tag]:
        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v2_base_url}/books/{book_id}/tags/",
            decoder=StandardV2Page(),
        ):
            yield Tag.model_validate(item)

    async def create_book(self, book_id: int, name: str) -> Tag:
        response = await self._transport.post(
            f"{self._transport.config.v2_base_url}/books/{book_id}/tags/",
            json={"name": name[:512]},
        )
        return Tag.model_validate(response.json())

    async def update_book(self, book_id: int, tag_id: int, name: str) -> Tag:
        response = await self._transport.patch(
            f"{self._transport.config.v2_base_url}/books/{book_id}/tags/{tag_id}/",
            json={"name": name[:512]},
        )
        return Tag.model_validate(response.json())

    async def delete_book(self, book_id: int, tag_id: int) -> None:
        await self._transport.delete(
            f"{self._transport.config.v2_base_url}/books/{book_id}/tags/{tag_id}/"
        )


__all__ = ["AsyncTagsResource"]
