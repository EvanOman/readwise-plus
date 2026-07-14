"""Compatibility shims for legacy tag workflow imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from readwise_sdk.operations.tags import (
    SyncTagOperations,
    TagCleanupResult,
    TagPattern,
    TagReport,
    find_similar_tags,
    normalize_tag,
)
from readwise_sdk.v2.models import Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import ReadwiseClient


class TagWorkflow:
    """Legacy blocking wrapper over operation-owned tag behavior."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client
        self._operations = SyncTagOperations(client.v2)

    def auto_tag_highlights(
        self,
        patterns: list[TagPattern],
        *,
        dry_run: bool = False,
    ) -> dict[int, list[str]]:
        """Apply automatic tagging based on patterns."""
        return self._operations.auto_tag_highlights(patterns, dry_run=dry_run)

    def get_tag_report(self) -> TagReport:
        """Generate a report of tag usage statistics."""
        return self._operations.get_tag_report()

    def _find_similar_tags(self, tags: list[str]) -> list[list[str]]:
        """Preserve the existing private compatibility seam."""
        return find_similar_tags(tags)

    def _normalize_tag(self, tag: str) -> str:
        """Preserve the existing private compatibility seam."""
        return normalize_tag(tag)

    def merge_tags(
        self,
        source_tags: list[str],
        target_tag: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Merge multiple tags into one."""
        return self._operations.merge_tags(source_tags, target_tag, dry_run=dry_run)

    def rename_tag(
        self,
        old_name: str,
        new_name: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Rename a tag across all highlights."""
        return self._operations.rename_tag(old_name, new_name, dry_run=dry_run)

    def delete_tag(self, tag_name: str, *, dry_run: bool = False) -> list[int]:
        """Delete a tag from all highlights."""
        return self._operations.delete_tag(tag_name, dry_run=dry_run)

    def get_highlights_by_tag(self, tag_name: str) -> list[Highlight]:
        """Get all highlights with a specific tag."""
        return self._operations.get_highlights_by_tag(tag_name)

    def get_untagged_highlights(self) -> list[Highlight]:
        """Get all highlights without any tags."""
        return self._operations.get_untagged_highlights()


__all__ = ["TagCleanupResult", "TagPattern", "TagReport", "TagWorkflow"]
