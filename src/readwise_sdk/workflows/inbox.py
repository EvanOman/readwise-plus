"""Reading inbox management workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from collections.abc import Callable

    from readwise_sdk.client import ReadwiseClient


@dataclass
class ArchiveRule:
    """A rule for auto-archiving documents."""

    name: str
    condition: Callable[[Document], bool]
    enabled: bool = True


@dataclass
class QueueStats:
    """Statistics about the reading queue."""

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
    """An action taken during triage."""

    document_id: str
    document_title: str | None
    action: str  # "archive", "later", "keep", "skip"
    reason: str | None = None


class ReadingInbox:
    """Workflow utilities for managing the reading inbox."""

    def __init__(self, client: ReadwiseClient) -> None:
        """Initialize the reading inbox workflow.

        Args:
            client: The Readwise client.
        """
        self._client = client
        self._archive_rules: list[ArchiveRule] = []

    def add_archive_rule(self, rule: ArchiveRule) -> None:
        """Add an auto-archive rule.

        Args:
            rule: The archive rule to add.
        """
        self._archive_rules.append(rule)

    def remove_archive_rule(self, name: str) -> bool:
        """Remove an archive rule by name.

        Args:
            name: Name of the rule to remove.

        Returns:
            True if the rule was found and removed.
        """
        for i, rule in enumerate(self._archive_rules):
            if rule.name == name:
                self._archive_rules.pop(i)
                return True
        return False

    def get_archive_rules(self) -> list[ArchiveRule]:
        """Get all configured archive rules.

        Returns:
            List of archive rules.
        """
        return list(self._archive_rules)

    def get_queue_stats(self) -> QueueStats:
        """Get statistics about the reading queue.

        Returns:
            QueueStats with queue information.
        """
        inbox = list(self._client.v3.get_inbox())
        reading_list = list(self._client.v3.get_reading_list())

        all_unread = inbox + reading_list
        now = datetime.now(UTC)

        # Calculate ages
        ages_days = []
        for doc in all_unread:
            if doc.created_at:
                age = (now - doc.created_at).days
                ages_days.append(age)

        oldest_age = max(ages_days) if ages_days else None
        average_age = sum(ages_days) / len(ages_days) if ages_days else None

        # Count by category
        by_category: dict[str, int] = {}
        for doc in all_unread:
            cat = doc.category.value if doc.category else "unknown"
            by_category[cat] = by_category.get(cat, 0) + 1

        # Count old items
        items_older_than_30 = sum(1 for age in ages_days if age > 30)
        items_older_than_90 = sum(1 for age in ages_days if age > 90)

        return QueueStats(
            inbox_count=len(inbox),
            reading_list_count=len(reading_list),
            total_unread=len(all_unread),
            oldest_item_age_days=oldest_age,
            average_age_days=average_age,
            by_category=by_category,
            items_older_than_30_days=items_older_than_30,
            items_older_than_90_days=items_older_than_90,
        )

    def smart_archive(
        self,
        *,
        dry_run: bool = False,
    ) -> list[TriageAction]:
        """Apply archive rules to inbox items.

        Args:
            dry_run: If True, don't actually archive, just report matches.

        Returns:
            List of actions taken/would be taken.
        """
        actions: list[TriageAction] = []
        inbox = list(self._client.v3.get_inbox())

        for doc in inbox:
            for rule in self._archive_rules:
                if not rule.enabled:
                    continue

                if rule.condition(doc):
                    actions.append(
                        TriageAction(
                            document_id=doc.id,
                            document_title=doc.title,
                            action="archive",
                            reason=f"Matched rule: {rule.name}",
                        )
                    )

                    if not dry_run:
                        try:
                            self._client.v3.archive(doc.id)
                        except Exception:
                            pass
                    break  # Only apply first matching rule

        return actions

    def get_stale_items(
        self,
        *,
        days: int = 30,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        """Get documents older than a specified number of days.

        Args:
            days: Age threshold in days.
            location: Optional location to filter by.

        Returns:
            List of stale documents.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        results = []

        docs = self._client.v3.list_documents(location=location)
        for doc in docs:
            if doc.created_at and doc.created_at < cutoff:
                results.append(doc)

        return results

    def batch_archive_stale(
        self,
        *,
        days: int = 90,
        dry_run: bool = False,
    ) -> list[TriageAction]:
        """Archive items older than a specified number of days.

        Args:
            days: Age threshold in days.
            dry_run: If True, don't actually archive.

        Returns:
            List of actions taken/would be taken.
        """
        stale = self.get_stale_items(days=days, location=DocumentLocation.NEW)
        stale.extend(self.get_stale_items(days=days, location=DocumentLocation.LATER))

        actions = []
        for doc in stale:
            actions.append(
                TriageAction(
                    document_id=doc.id,
                    document_title=doc.title,
                    action="archive",
                    reason=f"Older than {days} days",
                )
            )

            if not dry_run:
                try:
                    self._client.v3.archive(doc.id)
                except Exception:
                    pass

        return actions

    def move_to_reading_list(
        self,
        document_ids: list[str],
    ) -> dict[str, bool]:
        """Move documents to reading list.

        Args:
            document_ids: List of document IDs to move.

        Returns:
            Dict mapping document ID to success status.
        """
        results: dict[str, bool] = {}
        for doc_id in document_ids:
            try:
                self._client.v3.move_to_later(doc_id)
                results[doc_id] = True
            except Exception:
                results[doc_id] = False
        return results

    def get_inbox_by_priority(self) -> list[Document]:
        """Get inbox items sorted by a priority heuristic.

        Priority is based on:
        - Newer items first
        - Articles over other categories
        - Shorter content over longer (estimated by title length as proxy)

        Returns:
            Sorted list of inbox documents.
        """
        inbox = list(self._client.v3.get_inbox())

        def priority_key(doc: Document) -> tuple:
            # Category priority (lower is higher priority)
            category_priority = {
                DocumentCategory.ARTICLE: 0,
                DocumentCategory.EMAIL: 1,
                DocumentCategory.RSS: 2,
                DocumentCategory.PDF: 3,
                DocumentCategory.EPUB: 4,
                DocumentCategory.TWEET: 5,
                DocumentCategory.VIDEO: 6,
            }
            cat_pri = category_priority.get(doc.category, 99) if doc.category else 99

            # Age (newer is higher priority, so negative days)
            age_days = 0
            if doc.created_at:
                age_days = (datetime.now(UTC) - doc.created_at).days

            # Title length as proxy for complexity (shorter is higher priority)
            title_len = len(doc.title) if doc.title else 0

            return (cat_pri, age_days, title_len)

        return sorted(inbox, key=priority_key)

    def search_inbox(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Document]:
        """Search inbox documents by title, author, or summary.

        Args:
            query: Search query.
            case_sensitive: Whether to perform case-sensitive search.

        Returns:
            List of matching documents.
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        for doc in self._client.v3.get_inbox():
            title = (doc.title or "") if case_sensitive else (doc.title or "").lower()
            author = (doc.author or "") if case_sensitive else (doc.author or "").lower()
            summary = (doc.summary or "") if case_sensitive else (doc.summary or "").lower()

            if query in title or query in author or query in summary:
                results.append(doc)

        return results

    def get_inbox_categories(self) -> dict[DocumentCategory, list[Document]]:
        """Get inbox documents grouped by category.

        Returns:
            Dict mapping category to list of documents.
        """
        groups: dict[DocumentCategory, list[Document]] = {}

        for doc in self._client.v3.get_inbox():
            if doc.category:
                if doc.category not in groups:
                    groups[doc.category] = []
                groups[doc.category].append(doc)

        return groups


# Predefined archive rules
def create_old_item_rule(days: int = 90) -> ArchiveRule:
    """Create a rule to archive items older than N days."""

    def condition(doc: Document) -> bool:
        if not doc.created_at:
            return False
        age = (datetime.now(UTC) - doc.created_at).days
        return age > days

    return ArchiveRule(name=f"older_than_{days}_days", condition=condition)


def create_category_rule(category: DocumentCategory) -> ArchiveRule:
    """Create a rule to archive items of a specific category."""

    def condition(doc: Document) -> bool:
        return doc.category == category

    return ArchiveRule(name=f"category_{category.value}", condition=condition)


def create_title_pattern_rule(pattern: str, name: str) -> ArchiveRule:
    """Create a rule to archive items matching a title pattern."""

    def condition(doc: Document) -> bool:
        if not doc.title:
            return False
        return bool(re.search(pattern, doc.title, re.IGNORECASE))

    return ArchiveRule(name=name, condition=condition)


def create_domain_rule(domain: str) -> ArchiveRule:
    """Create a rule to archive items from a specific domain."""

    def condition(doc: Document) -> bool:
        if not doc.url:
            return False
        return domain.lower() in doc.url.lower()

    return ArchiveRule(name=f"domain_{domain}", condition=condition)
