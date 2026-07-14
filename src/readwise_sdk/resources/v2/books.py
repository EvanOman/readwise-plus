"""Asynchronous access to Readwise v2 book endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.pagination import StandardV2Page, paginate_async
from readwise_sdk.v2.models import Book, BookCategory


class AsyncBooksResource:
    """Build book requests and decode book models."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def iter(
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
        params: dict[str, Any] = {"page_size": min(page_size, 1000)}

        if category:
            params["category"] = category.value
        if source:
            params["source"] = source
        if updated_after:
            params["updated__gt"] = updated_after.isoformat()
        if updated_before:
            params["updated__lt"] = updated_before.isoformat()
        if last_highlight_after:
            params["last_highlight_at__gt"] = last_highlight_after.isoformat()
        if last_highlight_before:
            params["last_highlight_at__lt"] = last_highlight_before.isoformat()

        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v2_base_url}/books/",
            params=params,
            decoder=StandardV2Page(),
        ):
            yield Book.model_validate(item)

    async def get(self, book_id: int) -> Book:
        response = await self._transport.get(
            f"{self._transport.config.v2_base_url}/books/{book_id}/"
        )
        return Book.model_validate(response.json())


__all__ = ["AsyncBooksResource"]
