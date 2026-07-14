"""Canonical async-first operations for Reader documents."""

from __future__ import annotations

from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from readwise_sdk.errors import NotFoundError
from readwise_sdk.models import BulkResult, DocumentSearch, DocumentSearchResult, DocumentSummary
from readwise_sdk.models.results import OperationFailure
from readwise_sdk.v3.models import (
    CreateDocumentResult,
    Document,
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentUpdate,
)


class DocumentsResource(Protocol):
    """The low-level document capabilities required by document operations."""

    def iter(
        self,
        *,
        location: DocumentLocation | None = None,
        category: DocumentCategory | None = None,
        updated_after: datetime | None = None,
        tags: list[str] | None = None,
        with_content: bool = False,
    ) -> AsyncIterator[Document]: ...

    async def get(self, document_id: str, *, with_content: bool = False) -> Document | None: ...

    async def create(self, document: DocumentCreate) -> CreateDocumentResult: ...

    async def update(
        self,
        document_id: str,
        update: DocumentUpdate,
    ) -> CreateDocumentResult: ...

    async def delete(self, document_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class DocumentStatistics:
    """The combined legacy inbox and reading-queue statistics projection."""

    inbox_count: int
    reading_list_count: int
    archive_count: int
    total_count: int
    total_unread: int
    by_category: dict[str, int]
    oldest_inbox_item: Document | None
    newest_inbox_item: Document | None
    oldest_item_age_days: int | None
    average_age_days: float | None
    items_older_than_30_days: int
    items_older_than_90_days: int


def _summary(document: Document) -> DocumentSummary:
    """Project a document into the fields shared by list adapters."""
    return DocumentSummary(
        id=document.id,
        title=document.title,
        author=document.author,
        url=document.source_url or document.url,
        category=document.category,
        location=document.location,
        tags=tuple(document.tags),
        word_count=document.word_count,
        reading_progress=document.reading_progress,
        site_name=document.site_name,
        published_date=document.published_date,
        saved_at=document.saved_at,
    )


class DocumentOperations:
    """Own filtering, composition, limits, and failure policy for documents."""

    def __init__(self, resource: DocumentsResource) -> None:
        self._resource = resource

    async def search(self, search: DocumentSearch) -> DocumentSearchResult:
        """Return a bounded summary search using the current MCP title filter."""
        query = search.query.lower() if search.query else None
        items: list[DocumentSummary] = []

        async for document in self._resource.iter(
            location=search.location,
            category=search.category,
            updated_after=search.updated_after,
            tags=list(search.tags) or None,
        ):
            # Characterizes current MCP behavior: query matches only a present title.
            # A document without a title is retained even when a query was supplied.
            if query and document.title and query not in document.title.lower():
                continue

            items.append(_summary(document))
            if len(items) >= search.limit:
                return DocumentSearchResult(items=items, truncated=True)

        return DocumentSearchResult(items=items, truncated=False)

    async def get(self, document_id: str, *, with_content: bool = False) -> Document | None:
        """Get one document, preserving the resource's nullable not-found result."""
        return await self._resource.get(document_id, with_content=with_content)

    async def save(self, document: DocumentCreate) -> CreateDocumentResult:
        """Save a document while preserving the current dropped-category bug."""
        # Characterizes current (buggy) save_to_reader behavior. A later stage
        # deliberately restores category after the operation contract is established.
        without_category = document.model_copy(update={"category": None})
        return await self._resource.create(without_category)

    async def update(
        self,
        document_id: str,
        update: DocumentUpdate,
    ) -> CreateDocumentResult:
        """Update document metadata with the resource's partial-field payload."""
        return await self._resource.update(document_id, update)

    async def delete(self, document_id: str) -> None:
        """Permanently delete one document."""
        await self._resource.delete(document_id)

    async def move(
        self,
        document_id: str,
        location: DocumentLocation,
    ) -> CreateDocumentResult:
        """Move one document by applying a location-only update."""
        return await self.update(document_id, DocumentUpdate(location=location))

    async def set_tags(self, document_id: str, tags: list[str]) -> CreateDocumentResult:
        """Replace all document tags without normalizing the supplied list."""
        return await self.update(document_id, DocumentUpdate(tags=tags))

    async def add_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        """Add a tag if absent, retaining existing tag order and duplicates."""
        document = await self.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        tags = list(document.tags)
        if tag not in tags:
            tags.append(tag)
        return await self.set_tags(document_id, tags)

    async def remove_tag(self, document_id: str, tag: str) -> CreateDocumentResult:
        """Remove every exact occurrence of a tag from a document."""
        document = await self.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        tags = [existing for existing in document.tags if existing != tag]
        return await self.set_tags(document_id, tags)

    async def inbox(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[Document]:
        """Materialize the Reader inbox view."""
        return await self._view(
            DocumentLocation.NEW,
            limit=limit,
            with_content=with_content,
        )

    async def later(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[Document]:
        """Materialize the Reader reading-list view."""
        return await self._view(
            DocumentLocation.LATER,
            limit=limit,
            with_content=with_content,
        )

    async def archive(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[Document]:
        """Materialize the Reader archive view."""
        return await self._view(
            DocumentLocation.ARCHIVE,
            limit=limit,
            with_content=with_content,
        )

    async def _view(
        self,
        location: DocumentLocation,
        *,
        limit: int | None,
        with_content: bool,
    ) -> list[Document]:
        documents: list[Document] = []
        async for document in self._resource.iter(
            location=location,
            with_content=with_content,
        ):
            if limit is not None and len(documents) >= limit:
                break
            documents.append(document)
        return documents

    async def statistics(self) -> DocumentStatistics:
        """Compose the exact legacy manager and reading-queue statistics."""
        inbox = await self.inbox()
        reading_list = await self.later()
        archive = await self.archive()
        unread = inbox + reading_list

        by_category: Counter[str] = Counter()
        for document in unread:
            category = document.category.value if document.category else "unknown"
            by_category[category] += 1

        oldest_inbox_item: Document | None = None
        newest_inbox_item: Document | None = None
        if inbox:
            sorted_inbox = sorted(
                inbox,
                key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC),
            )
            oldest_inbox_item = sorted_inbox[0]
            newest_inbox_item = sorted_inbox[-1]

        now = datetime.now(UTC)
        ages_days = [
            (now - document.created_at).days
            for document in unread
            if document.created_at is not None
        ]

        return DocumentStatistics(
            inbox_count=len(inbox),
            reading_list_count=len(reading_list),
            archive_count=len(archive),
            total_count=len(inbox) + len(reading_list) + len(archive),
            total_unread=len(unread),
            by_category=dict(by_category),
            oldest_inbox_item=oldest_inbox_item,
            newest_inbox_item=newest_inbox_item,
            oldest_item_age_days=max(ages_days) if ages_days else None,
            average_age_days=sum(ages_days) / len(ages_days) if ages_days else None,
            items_older_than_30_days=sum(age > 30 for age in ages_days),
            items_older_than_90_days=sum(age > 90 for age in ages_days),
        )

    async def bulk_move(
        self,
        document_ids: list[str],
        location: DocumentLocation,
    ) -> BulkResult[str]:
        """Move documents sequentially and retain every item-specific failure."""
        succeeded: list[str] = []
        failures: list[OperationFailure] = []
        for document_id in document_ids:
            try:
                await self.move(document_id, location)
                succeeded.append(document_id)
            except Exception as error:
                # Characterizes the managers' current broad partial-failure policy.
                failures.append(OperationFailure(item=document_id, error=error))
        return BulkResult[str](succeeded=succeeded, failures=failures)

    async def bulk_set_tags(
        self,
        document_ids: list[str],
        tags: list[str],
    ) -> BulkResult[str]:
        """Set tags sequentially and retain every item-specific failure."""
        succeeded: list[str] = []
        failures: list[OperationFailure] = []
        for document_id in document_ids:
            try:
                await self.set_tags(document_id, tags)
                succeeded.append(document_id)
            except Exception as error:
                # Characterizes the managers' current broad partial-failure policy.
                failures.append(OperationFailure(item=document_id, error=error))
        return BulkResult[str](succeeded=succeeded, failures=failures)


__all__ = ["DocumentOperations", "DocumentStatistics", "DocumentsResource"]
