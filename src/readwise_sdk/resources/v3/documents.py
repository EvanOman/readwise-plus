"""Asynchronous access to Reader v3 document endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.pagination import ReaderV3Page, paginate_async
from readwise_sdk.v3.models import (
    CreateDocumentResult,
    Document,
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentUpdate,
)


class AsyncDocumentsResource:
    """Build document requests and decode document API models."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def iter(
        self,
        *,
        location: DocumentLocation | None = None,
        category: DocumentCategory | None = None,
        updated_after: datetime | None = None,
        tags: list[str] | None = None,
        with_content: bool = False,
    ) -> AsyncIterator[Document]:
        params: dict[str, Any] = {}

        if location:
            params["location"] = location.value
        if category:
            params["category"] = category.value
        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()
        if tags and len(tags) > 0:
            # Characterizes the existing single-tag behavior.
            params["tag"] = tags[0]
        if with_content:
            params["withHtmlContent"] = "true"

        async for item in paginate_async(
            self._transport.get,
            f"{self._transport.config.v3_base_url}/list/",
            params=params,
            decoder=ReaderV3Page(),
        ):
            yield Document.model_validate(item)

    async def get(self, document_id: str, *, with_content: bool = False) -> Document | None:
        params: dict[str, Any] = {"id": document_id}
        if with_content:
            params["withHtmlContent"] = "true"

        response = await self._transport.get(
            f"{self._transport.config.v3_base_url}/list/",
            params=params,
        )
        results = response.json().get("results", [])
        if results:
            return Document.model_validate(results[0])
        return None

    async def create(self, document: DocumentCreate) -> CreateDocumentResult:
        response = await self._transport.post(
            f"{self._transport.config.v3_base_url}/save/",
            json=document.to_api_dict(),
        )
        return CreateDocumentResult.model_validate(response.json())

    async def update(
        self,
        document_id: str,
        update: DocumentUpdate,
    ) -> CreateDocumentResult:
        response = await self._transport.patch(
            f"{self._transport.config.v3_base_url}/update/{document_id}/",
            json=update.to_api_dict(),
        )
        return CreateDocumentResult.model_validate(response.json())

    async def delete(self, document_id: str) -> None:
        await self._transport.delete(f"{self._transport.config.v3_base_url}/delete/{document_id}/")


__all__ = ["AsyncDocumentsResource"]
