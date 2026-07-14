"""Asynchronous access to Readwise v2 highlight endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from readwise_sdk.models.readwise import Highlight, HighlightCreate, HighlightUpdate
from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.pagination import StandardV2Page, paginate_async


class AsyncHighlightsResource:
    """Build highlight requests and decode highlight models."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def iter(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> AsyncIterator[Highlight]:
        params: dict[str, Any] = {"page_size": min(page_size, 1000)}

        if book_id is not None:
            params["book_id"] = book_id
        if updated_after:
            params["updated__gt"] = updated_after.isoformat()
        if updated_before:
            params["updated__lt"] = updated_before.isoformat()
        if highlighted_after:
            params["highlighted_at__gt"] = highlighted_after.isoformat()
        if highlighted_before:
            params["highlighted_at__lt"] = highlighted_before.isoformat()

        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v2_base_url}/highlights/",
            params=params,
            decoder=StandardV2Page(),
        ):
            yield Highlight.model_validate(item)

    async def get(self, highlight_id: int) -> Highlight:
        response = await self._transport.get(
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/"
        )
        return Highlight.model_validate(response.json())

    async def create(self, highlights: list[HighlightCreate]) -> list[int]:
        payload = {"highlights": [highlight.to_api_dict() for highlight in highlights]}
        response = await self._transport.post(
            f"{self._transport.config.v2_base_url}/highlights/",
            json=payload,
        )

        highlight_ids: list[int] = []
        for book_data in response.json():
            modified = book_data.get("modified_highlights", [])
            highlight_ids.extend(modified)
        return highlight_ids

    async def update(self, highlight_id: int, update: HighlightUpdate) -> Highlight:
        response = await self._transport.patch(
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/",
            json=update.to_api_dict(),
        )
        return Highlight.model_validate(response.json())

    async def delete(self, highlight_id: int) -> None:
        await self._transport.delete(
            f"{self._transport.config.v2_base_url}/highlights/{highlight_id}/"
        )


__all__ = ["AsyncHighlightsResource"]
