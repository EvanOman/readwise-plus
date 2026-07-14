"""Asynchronous access to the Reader v3 tags endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator

from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.pagination import ReaderV3Page, paginate_async
from readwise_sdk.v3.models import DocumentTag


class AsyncTagsResource:
    """Build Reader tag requests and decode tag models."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def iter(self) -> AsyncIterator[DocumentTag]:
        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v3_base_url}/tags/",
            decoder=ReaderV3Page(),
        ):
            yield DocumentTag.model_validate(item)


__all__ = ["AsyncTagsResource"]
