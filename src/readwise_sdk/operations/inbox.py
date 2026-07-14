"""Canonical reading-inbox workflow operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from readwise_sdk.models import BulkResult
from readwise_sdk.operations.documents import DocumentOperations
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation


class ArchiveRuleLike(Protocol):
    name: str
    condition: Callable[[Document], bool]
    enabled: bool


@dataclass(frozen=True, slots=True)
class QueueStatistics:
    inbox_count: int
    reading_list_count: int
    total_unread: int
    oldest_item_age_days: int | None
    average_age_days: float | None
    by_category: dict[str, int]
    items_older_than_30_days: int
    items_older_than_90_days: int


@dataclass(frozen=True, slots=True)
class InboxTriageAction:
    document_id: str
    document_title: str | None
    action: str
    reason: str | None = None


class ReadingInboxOperations:
    """Own rules, queue selection, triage, and suppression semantics."""

    def __init__(self, documents: DocumentOperations) -> None:
        self._documents = documents
        self._archive_rules: list[ArchiveRuleLike] = []

    def add_archive_rule(self, rule: ArchiveRuleLike) -> None:
        self._archive_rules.append(rule)

    def remove_archive_rule(self, name: str) -> bool:
        for index, rule in enumerate(self._archive_rules):
            if rule.name == name:
                self._archive_rules.pop(index)
                return True
        return False

    def get_archive_rules(self) -> list[ArchiveRuleLike]:
        return list(self._archive_rules)

    async def queue_statistics(self) -> QueueStatistics:
        statistics = await self._documents.statistics()
        return QueueStatistics(
            inbox_count=statistics.inbox_count,
            reading_list_count=statistics.reading_list_count,
            total_unread=statistics.total_unread,
            oldest_item_age_days=statistics.oldest_item_age_days,
            average_age_days=statistics.average_age_days,
            by_category=statistics.by_category,
            items_older_than_30_days=statistics.items_older_than_30_days,
            items_older_than_90_days=statistics.items_older_than_90_days,
        )

    async def smart_archive(self, *, dry_run: bool = False) -> list[InboxTriageAction]:
        actions: list[InboxTriageAction] = []
        for document in await self._documents.inbox():
            for rule in self._archive_rules:
                if not rule.enabled:
                    continue
                if rule.condition(document):
                    actions.append(
                        InboxTriageAction(
                            document.id,
                            document.title,
                            "archive",
                            f"Matched rule: {rule.name}",
                        )
                    )
                    if not dry_run:
                        try:
                            await self._documents.move(document.id, DocumentLocation.ARCHIVE)
                        except Exception:
                            pass
                    break
        return actions

    async def stale_items(
        self,
        *,
        days: int = 30,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return [
            document
            async for document in self._documents.filter(
                lambda item: item.created_at is not None and item.created_at < cutoff,
                location=location,
            )
        ]

    async def archive_stale(
        self,
        *,
        days: int = 90,
        dry_run: bool = False,
    ) -> list[InboxTriageAction]:
        stale = await self.stale_items(days=days, location=DocumentLocation.NEW)
        stale.extend(await self.stale_items(days=days, location=DocumentLocation.LATER))
        actions: list[InboxTriageAction] = []
        for document in stale:
            actions.append(
                InboxTriageAction(
                    document.id,
                    document.title,
                    "archive",
                    f"Older than {days} days",
                )
            )
            if not dry_run:
                try:
                    await self._documents.move(document.id, DocumentLocation.ARCHIVE)
                except Exception:
                    pass
        return actions

    async def move_to_reading_list(self, document_ids: list[str]) -> BulkResult[str]:
        return await self._documents.bulk_move(document_ids, DocumentLocation.LATER)

    async def inbox_by_priority(self) -> list[Document]:
        documents = await self._documents.inbox()

        def priority_key(document: Document) -> tuple[int, int, int]:
            category_priority = {
                DocumentCategory.ARTICLE: 0,
                DocumentCategory.EMAIL: 1,
                DocumentCategory.RSS: 2,
                DocumentCategory.PDF: 3,
                DocumentCategory.EPUB: 4,
                DocumentCategory.TWEET: 5,
                DocumentCategory.VIDEO: 6,
            }
            category = category_priority.get(document.category, 99) if document.category else 99
            age = (datetime.now(UTC) - document.created_at).days if document.created_at else 0
            title_length = len(document.title) if document.title else 0
            return category, age, title_length

        return sorted(documents, key=priority_key)

    async def search_inbox(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Document]:
        return await self._documents.search_items(
            query,
            case_sensitive=case_sensitive,
            location=DocumentLocation.NEW,
        )

    async def inbox_categories(self) -> dict[DocumentCategory, list[Document]]:
        groups: dict[DocumentCategory, list[Document]] = {}
        for document in await self._documents.inbox():
            if document.category:
                groups.setdefault(document.category, []).append(document)
        return groups


__all__ = ["InboxTriageAction", "QueueStatistics", "ReadingInboxOperations"]
