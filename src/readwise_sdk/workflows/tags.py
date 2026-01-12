"""Tag workflow utilities for automated tagging and cleanup."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from readwise_sdk.v2.models import Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import ReadwiseClient


@dataclass
class TagPattern:
    """A pattern for auto-tagging highlights."""

    pattern: str
    tag: str
    case_sensitive: bool = False
    match_in_notes: bool = True
    match_in_text: bool = True

    def matches(self, highlight: Highlight) -> bool:
        """Check if a highlight matches this pattern."""
        flags = 0 if self.case_sensitive else re.IGNORECASE

        targets = []
        if self.match_in_text:
            targets.append(highlight.text)
        if self.match_in_notes and highlight.note:
            targets.append(highlight.note)

        for target in targets:
            if re.search(self.pattern, target, flags):
                return True
        return False


@dataclass
class TagReport:
    """Report of tag usage statistics."""

    total_tags: int
    total_usages: int
    tags_by_usage: list[tuple[str, int]]
    unused_tags: list[str]
    duplicate_candidates: list[list[str]]


@dataclass
class TagCleanupResult:
    """Result of a tag cleanup operation."""

    merged_tags: list[tuple[list[str], str]]
    deleted_tags: list[str]
    renamed_tags: list[tuple[str, str]]
    errors: list[str]


class TagWorkflow:
    """Workflow utilities for tag management."""

    def __init__(self, client: ReadwiseClient) -> None:
        """Initialize the tag workflow.

        Args:
            client: The Readwise client.
        """
        self._client = client

    def auto_tag_highlights(
        self,
        patterns: list[TagPattern],
        *,
        dry_run: bool = False,
    ) -> dict[int, list[str]]:
        """Apply automatic tagging based on patterns.

        Args:
            patterns: List of TagPattern rules to apply.
            dry_run: If True, don't actually apply tags, just report matches.

        Returns:
            Dict mapping highlight ID to list of tags that were/would be applied.
        """
        results: dict[int, list[str]] = {}

        for highlight in self._client.v2.list_highlights():
            matching_tags = []
            existing_tag_names = {t.name.lower() for t in (highlight.tags or [])}

            for pattern in patterns:
                if pattern.matches(highlight):
                    # Only add if not already tagged
                    if pattern.tag.lower() not in existing_tag_names:
                        matching_tags.append(pattern.tag)

            if matching_tags:
                results[highlight.id] = matching_tags
                if not dry_run:
                    for tag in matching_tags:
                        try:
                            self._client.v2.create_highlight_tag(highlight.id, tag)
                        except Exception:
                            pass  # Tag may already exist

        return results

    def get_tag_report(self) -> TagReport:
        """Generate a report of tag usage statistics.

        Returns:
            TagReport with usage statistics.
        """
        # Get all highlights to count tag usage
        tag_usage: Counter[str] = Counter()
        all_tags: set[str] = set()

        for highlight in self._client.v2.list_highlights():
            for tag in highlight.tags or []:
                tag_usage[tag.name] += 1
                all_tags.add(tag.name)

        # Sort by usage
        tags_by_usage = tag_usage.most_common()

        # Find unused tags (tags that exist but have no highlights)
        # Note: This requires knowing all defined tags, which may not be fully accurate
        unused_tags = [tag for tag, count in tags_by_usage if count == 0]

        # Find potential duplicates (similar names)
        duplicate_candidates = self._find_similar_tags(list(all_tags))

        return TagReport(
            total_tags=len(all_tags),
            total_usages=sum(tag_usage.values()),
            tags_by_usage=tags_by_usage,
            unused_tags=unused_tags,
            duplicate_candidates=duplicate_candidates,
        )

    def _find_similar_tags(self, tags: list[str]) -> list[list[str]]:
        """Find tags that might be duplicates based on similarity."""
        groups: list[list[str]] = []
        processed: set[str] = set()

        for tag in tags:
            if tag in processed:
                continue

            similar = [tag]
            normalized = self._normalize_tag(tag)

            for other in tags:
                if other == tag or other in processed:
                    continue
                if self._normalize_tag(other) == normalized:
                    similar.append(other)

            if len(similar) > 1:
                groups.append(similar)
                processed.update(similar)
            else:
                processed.add(tag)

        return groups

    def _normalize_tag(self, tag: str) -> str:
        """Normalize a tag for comparison."""
        # Remove special characters, lowercase, strip whitespace
        normalized = re.sub(r"[^a-z0-9]", "", tag.lower())
        return normalized

    def merge_tags(
        self,
        source_tags: list[str],
        target_tag: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Merge multiple tags into one.

        Args:
            source_tags: Tags to merge from (will be removed).
            target_tag: Tag to merge into.
            dry_run: If True, don't actually merge, just report affected highlights.

        Returns:
            List of highlight IDs that were affected.
        """
        affected_highlights: list[int] = []
        source_tags_lower = {t.lower() for t in source_tags}

        for highlight in self._client.v2.list_highlights():
            highlight_tag_names = {t.name.lower(): t for t in (highlight.tags or [])}

            # Check if this highlight has any of the source tags
            matching_source_tags = source_tags_lower & set(highlight_tag_names.keys())

            if matching_source_tags:
                affected_highlights.append(highlight.id)

                if not dry_run:
                    # Add the target tag if not present
                    if target_tag.lower() not in highlight_tag_names:
                        try:
                            self._client.v2.create_highlight_tag(highlight.id, target_tag)
                        except Exception:
                            pass

                    # Remove the source tags
                    for source_tag_name in matching_source_tags:
                        tag = highlight_tag_names.get(source_tag_name)
                        if tag and tag.id:
                            try:
                                self._client.v2.delete_highlight_tag(highlight.id, tag.id)
                            except Exception:
                                pass

        return affected_highlights

    def rename_tag(
        self,
        old_name: str,
        new_name: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Rename a tag across all highlights.

        Args:
            old_name: Current tag name.
            new_name: New tag name.
            dry_run: If True, don't actually rename, just report affected highlights.

        Returns:
            List of highlight IDs that were affected.
        """
        affected_highlights: list[int] = []
        old_name_lower = old_name.lower()

        for highlight in self._client.v2.list_highlights():
            highlight_tag_map = {t.name.lower(): t for t in (highlight.tags or [])}

            if old_name_lower in highlight_tag_map:
                affected_highlights.append(highlight.id)

                if not dry_run:
                    tag = highlight_tag_map[old_name_lower]
                    if tag.id:
                        try:
                            self._client.v2.update_highlight_tag(highlight.id, tag.id, new_name)
                        except Exception:
                            pass

        return affected_highlights

    def delete_tag(
        self,
        tag_name: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Delete a tag from all highlights.

        Args:
            tag_name: Tag to delete.
            dry_run: If True, don't actually delete, just report affected highlights.

        Returns:
            List of highlight IDs that were affected.
        """
        affected_highlights: list[int] = []
        tag_name_lower = tag_name.lower()

        for highlight in self._client.v2.list_highlights():
            highlight_tag_map = {t.name.lower(): t for t in (highlight.tags or [])}

            if tag_name_lower in highlight_tag_map:
                affected_highlights.append(highlight.id)

                if not dry_run:
                    tag = highlight_tag_map[tag_name_lower]
                    if tag.id:
                        try:
                            self._client.v2.delete_highlight_tag(highlight.id, tag.id)
                        except Exception:
                            pass

        return affected_highlights

    def get_highlights_by_tag(self, tag_name: str) -> list[Highlight]:
        """Get all highlights with a specific tag.

        Args:
            tag_name: The tag name to filter by.

        Returns:
            List of highlights with the tag.
        """
        tag_name_lower = tag_name.lower()
        results = []

        for highlight in self._client.v2.list_highlights():
            tag_names = {t.name.lower() for t in (highlight.tags or [])}
            if tag_name_lower in tag_names:
                results.append(highlight)

        return results

    def get_untagged_highlights(self) -> list[Highlight]:
        """Get all highlights without any tags.

        Returns:
            List of untagged highlights.
        """
        return [h for h in self._client.v2.list_highlights() if not h.tags]
