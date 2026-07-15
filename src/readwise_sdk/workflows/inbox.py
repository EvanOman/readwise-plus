"""Legacy reading-inbox workflow compatibility shim."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from readwise_sdk.operations.compat import SyncDocumentsResource, bulk_result_map, run_sync
from readwise_sdk.operations.documents import DocumentOperations
from readwise_sdk.operations.inbox import InboxTriageAction, ReadingInboxOperations
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from collections.abc import Callable

    from readwise_sdk.client import ReadwiseClient


@dataclass
class ArchiveRule:
    name: str
    condition: Callable[[Document], bool]
    enabled: bool = True


@dataclass
class QueueStats:
    inbox_count: int
    reading_list_count: int
    total_unread: int
    oldest_item_age_days: int | None
    average_age_days: float | None
    by_category: dict[str, int]
    items_older_than_30_days: int
    items_older_than_90_days: int


@dataclass
class TriageAction:
    document_id: str
    document_title: str | None
    action: str
    reason: str | None = None


def _legacy_action(action: InboxTriageAction) -> TriageAction:
    return TriageAction(action.document_id, action.document_title, action.action, action.reason)


class ReadingInbox:
    """Compatibility wrapper over canonical reading-inbox operations."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client
        documents = DocumentOperations(SyncDocumentsResource(client, manager_compat=True))
        self._operations = ReadingInboxOperations(documents)

    def add_archive_rule(self, rule: ArchiveRule) -> None:
        self._operations.add_archive_rule(rule)

    def remove_archive_rule(self, name: str) -> bool:
        return self._operations.remove_archive_rule(name)

    def get_archive_rules(self) -> list[ArchiveRule]:
        return cast(list[ArchiveRule], self._operations.get_archive_rules())

    def get_queue_stats(self) -> QueueStats:
        result = run_sync(self._operations.queue_statistics())
        return QueueStats(
            result.inbox_count,
            result.reading_list_count,
            result.total_unread,
            result.oldest_item_age_days,
            result.average_age_days,
            result.by_category,
            result.items_older_than_30_days,
            result.items_older_than_90_days,
        )

    def smart_archive(self, *, dry_run: bool = False) -> list[TriageAction]:
        return [
            _legacy_action(item)
            for item in run_sync(self._operations.smart_archive(dry_run=dry_run))
        ]

    def get_stale_items(
        self,
        *,
        days: int = 30,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        return run_sync(self._operations.stale_items(days=days, location=location))

    def batch_archive_stale(
        self,
        *,
        days: int = 90,
        dry_run: bool = False,
    ) -> list[TriageAction]:
        return [
            _legacy_action(item)
            for item in run_sync(self._operations.archive_stale(days=days, dry_run=dry_run))
        ]

    def move_to_reading_list(self, document_ids: list[str]) -> dict[str, bool]:
        result = run_sync(self._operations.move_to_reading_list(document_ids))
        return bulk_result_map(document_ids, result)

    def get_inbox_by_priority(self) -> list[Document]:
        return run_sync(self._operations.inbox_by_priority())

    def search_inbox(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Document]:
        return run_sync(self._operations.search_inbox(query, case_sensitive=case_sensitive))

    def get_inbox_categories(self) -> dict[DocumentCategory, list[Document]]:
        return run_sync(self._operations.inbox_categories())


def create_old_item_rule(days: int = 90) -> ArchiveRule:
    def condition(doc: Document) -> bool:
        if not doc.created_at:
            return False
        return (datetime.now(UTC) - doc.created_at).days > days

    return ArchiveRule(name=f"older_than_{days}_days", condition=condition)


def create_category_rule(category: DocumentCategory) -> ArchiveRule:
    return ArchiveRule(
        name=f"category_{category.value}",
        condition=lambda doc: doc.category == category,
    )


def create_title_pattern_rule(pattern: str, name: str) -> ArchiveRule:
    def condition(doc: Document) -> bool:
        return bool(doc.title and re.search(pattern, doc.title, re.IGNORECASE))

    return ArchiveRule(name=name, condition=condition)


def create_domain_rule(domain: str) -> ArchiveRule:
    def condition(doc: Document) -> bool:
        return bool(doc.url and domain.lower() in doc.url.lower())

    return ArchiveRule(name=f"domain_{domain}", condition=condition)
