"""Compatibility facade for asynchronous Reader API v3 resources."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk.resources.v3.documents import AsyncDocumentsResource
from readwise_sdk.resources.v3.tags import AsyncTagsResource
from readwise_sdk.v3.models import (
    CreateDocumentResult,
    Document,
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentTag,
    DocumentUpdate,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from readwise_sdk.client import AsyncReadwiseClient


class AsyncReadwiseV3Client:
    """Preserve the public async v3 API while delegating to resources."""

    def __init__(self, base_client: AsyncReadwiseClient) -> None:
        self._client = base_client
        self._documents = AsyncDocumentsResource(base_client._transport)
        self._tags = AsyncTagsResource(base_client._transport)

    async def list_documents(
        self,
        *,
        location: DocumentLocation | None = None,
        category: DocumentCategory | None = None,
        updated_after: datetime | None = None,
        tags: list[str] | None = None,
        with_content: bool = False,
    ) -> AsyncIterator[Document]:
        async for document in self._documents.iter(
            location=location,
            category=category,
            updated_after=updated_after,
            tags=tags,
            with_content=with_content,
        ):
            yield document

    async def get_document(
        self, document_id: str, *, with_content: bool = False
    ) -> Document | None:
        return await self._documents.get(document_id, with_content=with_content)

    async def create_document(self, document: DocumentCreate) -> CreateDocumentResult:
        return await self._documents.create(document)

    async def save_url(
        self,
        url: str,
        *,
        location: DocumentLocation = DocumentLocation.NEW,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> CreateDocumentResult:
        document = DocumentCreate(url=url, location=location, tags=tags, notes=notes)
        return await self.create_document(document)

    async def update_document(
        self, document_id: str, update: DocumentUpdate
    ) -> CreateDocumentResult:
        return await self._documents.update(document_id, update)

    async def delete_document(self, document_id: str) -> None:
        await self._documents.delete(document_id)

    async def move_to_later(self, document_id: str) -> CreateDocumentResult:
        update = DocumentUpdate(location=DocumentLocation.LATER)
        return await self.update_document(document_id, update)

    async def archive(self, document_id: str) -> CreateDocumentResult:
        update = DocumentUpdate(location=DocumentLocation.ARCHIVE)
        return await self.update_document(document_id, update)

    async def move_to_inbox(self, document_id: str) -> CreateDocumentResult:
        update = DocumentUpdate(location=DocumentLocation.NEW)
        return await self.update_document(document_id, update)

    async def list_tags(self) -> AsyncIterator[DocumentTag]:
        async for tag in self._tags.iter():
            yield tag

    async def tag_document(self, document_id: str, tags: list[str]) -> CreateDocumentResult:
        update = DocumentUpdate(tags=tags)
        return await self.update_document(document_id, update)

    async def add_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        document = await self.get_document(document_id)
        if document is None:
            from readwise_sdk.errors import NotFoundError

            raise NotFoundError(f"Document {document_id} not found")

        new_tags = list(document.tags)
        if tag not in new_tags:
            new_tags.append(tag)
        return await self.tag_document(document_id, new_tags)

    async def remove_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        document = await self.get_document(document_id)
        if document is None:
            from readwise_sdk.errors import NotFoundError

            raise NotFoundError(f"Document {document_id} not found")

        new_tags = [existing_tag for existing_tag in document.tags if existing_tag != tag]
        return await self.tag_document(document_id, new_tags)

    def get_inbox(self) -> AsyncIterator[Document]:
        return self.list_documents(location=DocumentLocation.NEW)

    def get_reading_list(self) -> AsyncIterator[Document]:
        return self.list_documents(location=DocumentLocation.LATER)

    def get_archive(self) -> AsyncIterator[Document]:
        return self.list_documents(location=DocumentLocation.ARCHIVE)

    def get_articles(self) -> AsyncIterator[Document]:
        return self.list_documents(category=DocumentCategory.ARTICLE)
