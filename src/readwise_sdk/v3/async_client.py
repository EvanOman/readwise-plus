"""Async Readwise Reader API v3 client implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

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
    """Async client for Readwise Reader API v3 (documents, reading list).

    This class mirrors the synchronous ReadwiseV3Client but uses async/await
    for all I/O operations. Use this when your application is async-first
    or when you need to make concurrent API calls.

    Example:
        async with AsyncReadwiseClient() as client:
            # Iterate through documents asynchronously
            async for doc in client.v3.list_documents():
                print(doc.title)

            # Save multiple URLs concurrently
            import asyncio
            results = await asyncio.gather(
                client.v3.save_url("https://example.com/1"),
                client.v3.save_url("https://example.com/2"),
                client.v3.save_url("https://example.com/3"),
            )
    """

    def __init__(self, base_client: AsyncReadwiseClient) -> None:
        """Initialize the async v3 client.

        Args:
            base_client: The async base HTTP client for making requests.
        """
        self._client = base_client

    # ==================== Documents ====================

    async def list_documents(
        self,
        *,
        location: DocumentLocation | None = None,
        category: DocumentCategory | None = None,
        updated_after: datetime | None = None,
        tags: list[str] | None = None,
        with_content: bool = False,
    ) -> AsyncIterator[Document]:
        """List all documents with optional filtering.

        Args:
            location: Filter by location (new, later, archive, feed).
            category: Filter by category (article, email, pdf, etc.).
            updated_after: Only return documents updated after this datetime.
            tags: Filter by tags (up to 5).
            with_content: Whether to include HTML content in response.

        Yields:
            Document objects.
        """
        params: dict[str, Any] = {}

        if location:
            params["location"] = location.value
        if category:
            params["category"] = category.value
        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()
        if tags and len(tags) > 0:
            # Use first tag for filtering (API supports up to 5)
            params["tag"] = tags[0]
        if with_content:
            params["withHtmlContent"] = "true"

        async for item in self._client.paginate(
            f"{self._client.config.v3_base_url}/list/",
            params=params,
            cursor_key="nextPageCursor",
        ):
            yield Document.model_validate(item)

    async def get_document(
        self, document_id: str, *, with_content: bool = False
    ) -> Document | None:
        """Get a single document by ID.

        Args:
            document_id: The document ID.
            with_content: Whether to include HTML content.

        Returns:
            The Document object, or None if not found.
        """
        params: dict[str, Any] = {"id": document_id}
        if with_content:
            params["withHtmlContent"] = "true"

        response = await self._client.get(f"{self._client.config.v3_base_url}/list/", params=params)
        data = response.json()
        results = data.get("results", [])

        if results:
            return Document.model_validate(results[0])
        return None

    async def create_document(self, document: DocumentCreate) -> CreateDocumentResult:
        """Create a new document in Reader.

        Args:
            document: The document data to create.

        Returns:
            CreateDocumentResult with id and url.
        """
        response = await self._client.post(
            f"{self._client.config.v3_base_url}/save/",
            json=document.to_api_dict(),
        )
        return CreateDocumentResult.model_validate(response.json())

    async def save_url(
        self,
        url: str,
        *,
        location: DocumentLocation = DocumentLocation.NEW,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> CreateDocumentResult:
        """Convenience method to save a URL to Reader.

        Args:
            url: The URL to save.
            location: Where to save it (default: new/inbox).
            tags: Optional tags to add.
            notes: Optional notes to add.

        Returns:
            CreateDocumentResult with id and url.
        """
        doc = DocumentCreate(
            url=url,
            location=location,
            tags=tags,
            notes=notes,
        )
        return await self.create_document(doc)

    async def update_document(
        self, document_id: str, update: DocumentUpdate
    ) -> CreateDocumentResult:
        """Update an existing document.

        Args:
            document_id: The document ID to update.
            update: The fields to update.

        Returns:
            CreateDocumentResult with id and url.

        Raises:
            NotFoundError: If the document doesn't exist.
        """
        response = await self._client.patch(
            f"{self._client.config.v3_base_url}/update/{document_id}/",
            json=update.to_api_dict(),
        )
        return CreateDocumentResult.model_validate(response.json())

    async def delete_document(self, document_id: str) -> None:
        """Delete a document.

        Args:
            document_id: The document ID to delete.

        Raises:
            NotFoundError: If the document doesn't exist.
        """
        await self._client.delete(f"{self._client.config.v3_base_url}/delete/{document_id}/")

    async def move_to_later(self, document_id: str) -> CreateDocumentResult:
        """Move a document to the reading list (later).

        Args:
            document_id: The document ID to move.

        Returns:
            CreateDocumentResult with id and url.
        """
        update = DocumentUpdate(location=DocumentLocation.LATER)
        return await self.update_document(document_id, update)

    async def archive(self, document_id: str) -> CreateDocumentResult:
        """Archive a document.

        Args:
            document_id: The document ID to archive.

        Returns:
            CreateDocumentResult with id and url.
        """
        update = DocumentUpdate(location=DocumentLocation.ARCHIVE)
        return await self.update_document(document_id, update)

    async def move_to_inbox(self, document_id: str) -> CreateDocumentResult:
        """Move a document back to the inbox (new).

        Args:
            document_id: The document ID to move.

        Returns:
            CreateDocumentResult with id and url.
        """
        update = DocumentUpdate(location=DocumentLocation.NEW)
        return await self.update_document(document_id, update)

    # ==================== Tags ====================

    async def list_tags(self) -> AsyncIterator[DocumentTag]:
        """List all tags in Reader.

        Yields:
            DocumentTag objects with key and name.
        """
        async for item in self._client.paginate(
            f"{self._client.config.v3_base_url}/tags/",
            cursor_key="nextPageCursor",
        ):
            yield DocumentTag.model_validate(item)

    async def tag_document(self, document_id: str, tags: list[str]) -> CreateDocumentResult:
        """Set tags on a document.

        Note: This replaces all existing tags on the document.

        Args:
            document_id: The document ID to tag.
            tags: List of tag names to set.

        Returns:
            CreateDocumentResult with id and url.
        """
        update = DocumentUpdate(tags=tags)
        return await self.update_document(document_id, update)

    async def add_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        """Add a tag to a document (preserving existing tags).

        Args:
            document_id: The document ID.
            tag: The tag to add.

        Returns:
            CreateDocumentResult with id and url.
        """
        # First get the document to see existing tags
        doc = await self.get_document(document_id)
        if doc is None:
            from readwise_sdk.errors import NotFoundError

            raise NotFoundError(f"Document {document_id} not found")

        new_tags = list(doc.tags)
        if tag not in new_tags:
            new_tags.append(tag)

        return await self.tag_document(document_id, new_tags)

    async def remove_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        """Remove a tag from a document.

        Args:
            document_id: The document ID.
            tag: The tag to remove.

        Returns:
            CreateDocumentResult with id and url.
        """
        doc = await self.get_document(document_id)
        if doc is None:
            from readwise_sdk.errors import NotFoundError

            raise NotFoundError(f"Document {document_id} not found")

        new_tags = [t for t in doc.tags if t != tag]
        return await self.tag_document(document_id, new_tags)

    # ==================== Convenience Methods ====================

    def get_inbox(self) -> AsyncIterator[Document]:
        """Get all documents in the inbox (new).

        Returns:
            Async iterator of Document objects in the inbox.
        """
        return self.list_documents(location=DocumentLocation.NEW)

    def get_reading_list(self) -> AsyncIterator[Document]:
        """Get all documents in the reading list (later).

        Returns:
            Async iterator of Document objects in the reading list.
        """
        return self.list_documents(location=DocumentLocation.LATER)

    def get_archive(self) -> AsyncIterator[Document]:
        """Get all archived documents.

        Returns:
            Async iterator of archived Document objects.
        """
        return self.list_documents(location=DocumentLocation.ARCHIVE)

    def get_articles(self) -> AsyncIterator[Document]:
        """Get all article documents.

        Returns:
            Async iterator of Article Document objects.
        """
        return self.list_documents(category=DocumentCategory.ARTICLE)
