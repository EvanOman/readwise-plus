"""Legacy Reader document manager compatibility shim."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk.operations.compat import (
    SyncDocumentsResource,
    bulk_result_map,
    iter_sync,
    run_sync,
)
from readwise_sdk.operations.documents import DocumentOperations
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from readwise_sdk.client import ReadwiseClient


@dataclass
class InboxStats:
    inbox_count: int
    reading_list_count: int
    archive_count: int
    total_count: int
    by_category: dict[str, int]
    oldest_inbox_item: Document | None
    newest_inbox_item: Document | None


class DocumentManager:
    """Compatibility wrapper over canonical document operations."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client
        self._operations = DocumentOperations(SyncDocumentsResource(client, manager_compat=True))

    def get_inbox(self) -> list[Document]:
        return run_sync(self._operations.inbox())

    def get_reading_list(self) -> list[Document]:
        return run_sync(self._operations.later())

    def get_archive(self) -> list[Document]:
        return run_sync(self._operations.archive())

    def get_documents_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Document]:
        return run_sync(self._operations.since(days=days, hours=hours, since=since))

    def move_to_later(self, document_id: str) -> None:
        run_sync(self._operations.move(document_id, DocumentLocation.LATER))

    def archive(self, document_id: str) -> None:
        run_sync(self._operations.move(document_id, DocumentLocation.ARCHIVE))

    def move_to_inbox(self, document_id: str) -> None:
        run_sync(self._operations.move(document_id, DocumentLocation.NEW))

    def bulk_archive(self, document_ids: list[str]) -> dict[str, bool]:
        result = run_sync(self._operations.bulk_move(document_ids, DocumentLocation.ARCHIVE))
        return bulk_result_map(document_ids, result)

    def bulk_tag_documents(self, document_ids: list[str], tags: list[str]) -> dict[str, bool]:
        result = run_sync(self._operations.bulk_set_tags(document_ids, tags))
        return bulk_result_map(document_ids, result)

    def filter_documents(
        self,
        predicate: Callable[[Document], bool],
        *,
        location: DocumentLocation | None = None,
    ) -> Iterator[Document]:
        return iter_sync(self._operations.filter(predicate, location=location))

    def search_documents(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        return run_sync(
            self._operations.search_items(
                query,
                case_sensitive=case_sensitive,
                location=location,
            )
        )

    def get_inbox_stats(self) -> InboxStats:
        result = run_sync(self._operations.statistics())
        return InboxStats(
            inbox_count=result.inbox_count,
            reading_list_count=result.reading_list_count,
            archive_count=result.archive_count,
            total_count=result.total_count,
            by_category=result.by_category,
            oldest_inbox_item=result.oldest_inbox_item,
            newest_inbox_item=result.newest_inbox_item,
        )

    def get_documents_by_category(self, category: DocumentCategory) -> list[Document]:
        return run_sync(self._operations.by_category(category))

    def get_unread_count(self) -> int:
        return run_sync(self._operations.unread_count())
