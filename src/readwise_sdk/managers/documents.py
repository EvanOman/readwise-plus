"""High-level document management operations for Reader."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from readwise_sdk.client import ReadwiseClient


@dataclass
class InboxStats:
    """Statistics about the reading inbox."""

    inbox_count: int
    reading_list_count: int
    archive_count: int
    total_count: int
    by_category: dict[str, int]
    oldest_inbox_item: Document | None
    newest_inbox_item: Document | None


class DocumentManager:
    """High-level operations for managing Reader documents."""

    def __init__(self, client: ReadwiseClient) -> None:
        """Initialize the document manager.

        Args:
            client: The Readwise client.
        """
        self._client = client

    def get_inbox(self) -> list[Document]:
        """Get all documents in the inbox.

        Returns:
            List of inbox documents.
        """
        return list(self._client.v3.get_inbox())

    def get_reading_list(self) -> list[Document]:
        """Get all documents in the reading list.

        Returns:
            List of reading list documents.
        """
        return list(self._client.v3.get_reading_list())

    def get_archive(self) -> list[Document]:
        """Get all archived documents.

        Returns:
            List of archived documents.
        """
        return list(self._client.v3.get_archive())

    def get_documents_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Document]:
        """Get documents updated since a given time.

        Args:
            days: Number of days to look back.
            hours: Number of hours to look back.
            since: Specific datetime to look back to.

        Returns:
            List of documents updated since the given time.
        """
        if since is None:
            if days is not None:
                since = datetime.now(UTC) - timedelta(days=days)
            elif hours is not None:
                since = datetime.now(UTC) - timedelta(hours=hours)
            else:
                raise ValueError("Must specify days, hours, or since")

        return list(self._client.v3.list_documents(updated_after=since))

    def move_to_later(self, document_id: str) -> None:
        """Move a document to the reading list.

        Args:
            document_id: The document ID.
        """
        self._client.v3.move_to_later(document_id)

    def archive(self, document_id: str) -> None:
        """Archive a document.

        Args:
            document_id: The document ID.
        """
        self._client.v3.archive(document_id)

    def move_to_inbox(self, document_id: str) -> None:
        """Move a document back to the inbox.

        Args:
            document_id: The document ID.
        """
        self._client.v3.move_to_inbox(document_id)

    def bulk_archive(self, document_ids: list[str]) -> dict[str, bool]:
        """Archive multiple documents.

        Args:
            document_ids: List of document IDs.

        Returns:
            Dict mapping document ID to success status.
        """
        results: dict[str, bool] = {}
        for doc_id in document_ids:
            try:
                self._client.v3.archive(doc_id)
                results[doc_id] = True
            except Exception:
                results[doc_id] = False
        return results

    def bulk_tag_documents(
        self,
        document_ids: list[str],
        tags: list[str],
    ) -> dict[str, bool]:
        """Set tags on multiple documents.

        Args:
            document_ids: List of document IDs.
            tags: Tags to set on all documents.

        Returns:
            Dict mapping document ID to success status.
        """
        results: dict[str, bool] = {}
        for doc_id in document_ids:
            try:
                self._client.v3.tag_document(doc_id, tags)
                results[doc_id] = True
            except Exception:
                results[doc_id] = False
        return results

    def filter_documents(
        self,
        predicate: Callable[[Document], bool],
        *,
        location: DocumentLocation | None = None,
    ) -> Iterator[Document]:
        """Filter documents using a custom predicate.

        Args:
            predicate: A function that returns True for documents to include.
            location: Optional location to filter by first.

        Yields:
            Documents that match the predicate.
        """
        for doc in self._client.v3.list_documents(location=location):
            if predicate(doc):
                yield doc

    def search_documents(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        """Search documents by title, author, or summary.

        Args:
            query: The search query.
            case_sensitive: Whether to perform case-sensitive search.
            location: Optional location to filter by.

        Returns:
            List of matching documents.
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        for doc in self._client.v3.list_documents(location=location):
            title = (doc.title or "") if case_sensitive else (doc.title or "").lower()
            author = (doc.author or "") if case_sensitive else (doc.author or "").lower()
            summary = (doc.summary or "") if case_sensitive else (doc.summary or "").lower()

            if query in title or query in author or query in summary:
                results.append(doc)

        return results

    def get_inbox_stats(self) -> InboxStats:
        """Get statistics about the reading inbox.

        Returns:
            InboxStats with counts and oldest/newest items.
        """
        inbox = list(self._client.v3.get_inbox())
        reading_list = list(self._client.v3.get_reading_list())
        archive = list(self._client.v3.get_archive())

        # Count by category
        by_category: Counter[str] = Counter()
        for doc in inbox + reading_list:
            cat = doc.category.value if doc.category else "unknown"
            by_category[cat] += 1

        # Find oldest/newest inbox items
        oldest = None
        newest = None
        if inbox:
            sorted_inbox = sorted(
                inbox,
                key=lambda d: d.created_at or datetime.min.replace(tzinfo=UTC),
            )
            oldest = sorted_inbox[0]
            newest = sorted_inbox[-1]

        return InboxStats(
            inbox_count=len(inbox),
            reading_list_count=len(reading_list),
            archive_count=len(archive),
            total_count=len(inbox) + len(reading_list) + len(archive),
            by_category=dict(by_category),
            oldest_inbox_item=oldest,
            newest_inbox_item=newest,
        )

    def get_documents_by_category(
        self,
        category: DocumentCategory,
    ) -> list[Document]:
        """Get all documents of a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of documents in the category.
        """
        return list(self._client.v3.list_documents(category=category))

    def get_unread_count(self) -> int:
        """Get the count of unread documents (inbox + reading list).

        Returns:
            Count of unread documents.
        """
        inbox = len(list(self._client.v3.get_inbox()))
        reading_list = len(list(self._client.v3.get_reading_list()))
        return inbox + reading_list
