"""Asynchronous access to the Readwise v2 export endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.pagination import ExportV2Page, paginate_async
from readwise_sdk.v2.models import ExportBook


class AsyncExportResource:
    """Build export requests and decode nested export books."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def iter(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: list[int] | None = None,
        include_deleted: bool = False,
    ) -> AsyncIterator[ExportBook]:
        params: dict[str, Any] = {}

        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()
        if book_ids:
            params["ids"] = ",".join(str(book_id) for book_id in book_ids)
        if include_deleted:
            params["includeDeleted"] = "true"

        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v2_base_url}/export/",
            params=params,
            decoder=ExportV2Page(),
        ):
            yield ExportBook.model_validate(item)


__all__ = ["AsyncExportResource"]
