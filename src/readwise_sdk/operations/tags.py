"""Canonical tag selection, reporting, and mutation operations."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from readwise_sdk.models.readwise import Highlight, Tag


class TagHighlightsResource(Protocol):
    """Highlight iteration required by canonical tag operations."""

    def iter(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> AsyncIterator[Highlight]: ...


class HighlightTagsResource(Protocol):
    """Highlight-tag mutations required by canonical tag operations."""

    async def create_highlight(self, highlight_id: int, name: str) -> Tag: ...

    async def update_highlight(self, highlight_id: int, tag_id: int, name: str) -> Tag: ...

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None: ...


class SyncTagClient(Protocol):
    """Legacy synchronous capabilities used by the workflow compatibility shim."""

    def list_highlights(self) -> Iterator[Highlight]: ...

    def create_highlight_tag(self, highlight_id: int, name: str) -> Tag: ...

    def update_highlight_tag(self, highlight_id: int, tag_id: int, name: str) -> Tag: ...

    def delete_highlight_tag(self, highlight_id: int, tag_id: int) -> None: ...


@dataclass
class TagPattern:
    """A regular-expression rule for auto-tagging highlights."""

    pattern: str
    tag: str
    case_sensitive: bool = False
    match_in_notes: bool = True
    match_in_text: bool = True

    def matches(self, highlight: Highlight) -> bool:
        """Return whether this pattern matches the configured highlight fields."""
        flags = 0 if self.case_sensitive else re.IGNORECASE
        targets: list[str] = []
        if self.match_in_text:
            targets.append(highlight.text)
        if self.match_in_notes and highlight.note:
            targets.append(highlight.note)
        return any(re.search(self.pattern, target, flags) is not None for target in targets)


@dataclass
class TagReport:
    """Tag usage statistics with legacy-compatible fields."""

    total_tags: int
    total_usages: int
    tags_by_usage: list[tuple[str, int]]
    unused_tags: list[str]
    duplicate_candidates: list[list[str]]


@dataclass
class TagCleanupResult:
    """Legacy result model retained for import compatibility."""

    merged_tags: list[tuple[list[str], str]]
    deleted_tags: list[str]
    renamed_tags: list[tuple[str, str]]
    errors: list[str]


def normalize_tag(tag: str) -> str:
    """Normalize a tag using the legacy duplicate-candidate rule."""
    return re.sub(r"[^a-z0-9]", "", tag.lower())


def find_similar_tags(tags: list[str]) -> list[list[str]]:
    """Group tag spellings that normalize to the same value."""
    groups: list[list[str]] = []
    processed: set[str] = set()

    for tag in tags:
        if tag in processed:
            continue
        similar = [tag]
        normalized = normalize_tag(tag)
        for other in tags:
            if other == tag or other in processed:
                continue
            if normalize_tag(other) == normalized:
                similar.append(other)
        if len(similar) > 1:
            groups.append(similar)
            processed.update(similar)
        else:
            processed.add(tag)
    return groups


def build_tag_report(highlights: list[Highlight]) -> TagReport:
    """Aggregate tag usage with the exact legacy counting policy."""
    tag_usage: Counter[str] = Counter()
    all_tags: set[str] = set()
    for highlight in highlights:
        for tag in highlight.tags or []:
            tag_usage[tag.name] += 1
            all_tags.add(tag.name)
    tags_by_usage = tag_usage.most_common()
    return TagReport(
        total_tags=len(all_tags),
        total_usages=sum(tag_usage.values()),
        tags_by_usage=tags_by_usage,
        unused_tags=[tag for tag, count in tags_by_usage if count == 0],
        duplicate_candidates=find_similar_tags(list(all_tags)),
    )


def matching_auto_tags(highlight: Highlight, patterns: list[TagPattern]) -> list[str]:
    """Return missing matching tags in pattern order."""
    existing = {tag.name.lower() for tag in (highlight.tags or [])}
    return [
        pattern.tag
        for pattern in patterns
        if pattern.matches(highlight) and pattern.tag.lower() not in existing
    ]


def matching_source_tags(highlight: Highlight, source_tags: set[str]) -> list[Tag]:
    """Return source tags using the legacy set-intersection iteration order."""
    tag_map = {tag.name.lower(): tag for tag in (highlight.tags or [])}
    matching_names = source_tags & set(tag_map)
    return [tag_map[name] for name in matching_names]


class TagOperations:
    """Own async tag search, reporting, auto-tagging, and cleanup semantics."""

    def __init__(
        self,
        highlights: TagHighlightsResource,
        tags: HighlightTagsResource,
    ) -> None:
        self._highlights = highlights
        self._tags = tags

    async def _all_highlights(self) -> list[Highlight]:
        return [highlight async for highlight in self._highlights.iter()]

    async def auto_tag_highlights(
        self,
        patterns: list[TagPattern],
        *,
        dry_run: bool = False,
    ) -> dict[int, list[str]]:
        """Apply missing tags to highlights matched by the supplied patterns."""
        results: dict[int, list[str]] = {}
        async for highlight in self._highlights.iter():
            matching_tags = matching_auto_tags(highlight, patterns)
            if not matching_tags:
                continue
            results[highlight.id] = matching_tags
            if not dry_run:
                for tag in matching_tags:
                    try:
                        await self._tags.create_highlight(highlight.id, tag)
                    except Exception:
                        pass  # Characterizes current workflow behavior.
        return results

    async def get_tag_report(self) -> TagReport:
        """Return usage and duplicate-candidate statistics."""
        return build_tag_report(await self._all_highlights())

    async def merge_tags(
        self,
        source_tags: list[str],
        target_tag: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Merge source tag spellings into a target tag."""
        affected: list[int] = []
        sources = {tag.lower() for tag in source_tags}
        async for highlight in self._highlights.iter():
            matching = matching_source_tags(highlight, sources)
            if not matching:
                continue
            affected.append(highlight.id)
            if dry_run:
                continue
            existing = {tag.name.lower() for tag in (highlight.tags or [])}
            if target_tag.lower() not in existing:
                try:
                    await self._tags.create_highlight(highlight.id, target_tag)
                except Exception:
                    pass  # Characterizes current workflow behavior.
            for tag in matching:
                if tag.id:
                    try:
                        await self._tags.delete_highlight(highlight.id, tag.id)
                    except Exception:
                        pass  # Characterizes current workflow behavior.
        return affected

    async def rename_tag(
        self,
        old_name: str,
        new_name: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        """Rename a tag across all highlights."""
        affected: list[int] = []
        old_name_lower = old_name.lower()
        async for highlight in self._highlights.iter():
            tag_map = {tag.name.lower(): tag for tag in (highlight.tags or [])}
            if old_name_lower not in tag_map:
                continue
            affected.append(highlight.id)
            tag = tag_map[old_name_lower]
            if not dry_run and tag.id:
                try:
                    await self._tags.update_highlight(highlight.id, tag.id, new_name)
                except Exception:
                    pass  # Characterizes current workflow behavior.
        return affected

    async def delete_tag(self, tag_name: str, *, dry_run: bool = False) -> list[int]:
        """Delete a named tag from every highlight that has it."""
        affected: list[int] = []
        tag_name_lower = tag_name.lower()
        async for highlight in self._highlights.iter():
            tag_map = {tag.name.lower(): tag for tag in (highlight.tags or [])}
            if tag_name_lower not in tag_map:
                continue
            affected.append(highlight.id)
            tag = tag_map[tag_name_lower]
            if not dry_run and tag.id:
                try:
                    await self._tags.delete_highlight(highlight.id, tag.id)
                except Exception:
                    pass  # Characterizes current workflow behavior.
        return affected

    async def get_highlights_by_tag(self, tag_name: str) -> list[Highlight]:
        """Return highlights containing a case-insensitive tag name."""
        tag_name_lower = tag_name.lower()
        return [
            highlight
            async for highlight in self._highlights.iter()
            if tag_name_lower in {tag.name.lower() for tag in (highlight.tags or [])}
        ]

    async def get_untagged_highlights(self) -> list[Highlight]:
        """Return highlights with no tags."""
        return [highlight async for highlight in self._highlights.iter() if not highlight.tags]


class SyncTagOperations:
    """Synchronous operation adapter used solely by the legacy workflow shim."""

    def __init__(self, client: SyncTagClient) -> None:
        self._client = client

    def auto_tag_highlights(
        self,
        patterns: list[TagPattern],
        *,
        dry_run: bool = False,
    ) -> dict[int, list[str]]:
        results: dict[int, list[str]] = {}
        for highlight in self._client.list_highlights():
            matching_tags = matching_auto_tags(highlight, patterns)
            if not matching_tags:
                continue
            results[highlight.id] = matching_tags
            if not dry_run:
                for tag in matching_tags:
                    try:
                        self._client.create_highlight_tag(highlight.id, tag)
                    except Exception:
                        pass  # Characterizes current workflow behavior.
        return results

    def get_tag_report(self) -> TagReport:
        return build_tag_report(list(self._client.list_highlights()))

    def merge_tags(
        self,
        source_tags: list[str],
        target_tag: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        affected: list[int] = []
        sources = {tag.lower() for tag in source_tags}
        for highlight in self._client.list_highlights():
            matching = matching_source_tags(highlight, sources)
            if not matching:
                continue
            affected.append(highlight.id)
            if dry_run:
                continue
            existing = {tag.name.lower() for tag in (highlight.tags or [])}
            if target_tag.lower() not in existing:
                try:
                    self._client.create_highlight_tag(highlight.id, target_tag)
                except Exception:
                    pass  # Characterizes current workflow behavior.
            for tag in matching:
                if tag.id:
                    try:
                        self._client.delete_highlight_tag(highlight.id, tag.id)
                    except Exception:
                        pass  # Characterizes current workflow behavior.
        return affected

    def rename_tag(
        self,
        old_name: str,
        new_name: str,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        affected: list[int] = []
        old_name_lower = old_name.lower()
        for highlight in self._client.list_highlights():
            tag_map = {tag.name.lower(): tag for tag in (highlight.tags or [])}
            if old_name_lower not in tag_map:
                continue
            affected.append(highlight.id)
            tag = tag_map[old_name_lower]
            if not dry_run and tag.id:
                try:
                    self._client.update_highlight_tag(highlight.id, tag.id, new_name)
                except Exception:
                    pass  # Characterizes current workflow behavior.
        return affected

    def delete_tag(self, tag_name: str, *, dry_run: bool = False) -> list[int]:
        affected: list[int] = []
        tag_name_lower = tag_name.lower()
        for highlight in self._client.list_highlights():
            tag_map = {tag.name.lower(): tag for tag in (highlight.tags or [])}
            if tag_name_lower not in tag_map:
                continue
            affected.append(highlight.id)
            tag = tag_map[tag_name_lower]
            if not dry_run and tag.id:
                try:
                    self._client.delete_highlight_tag(highlight.id, tag.id)
                except Exception:
                    pass  # Characterizes current workflow behavior.
        return affected

    def get_highlights_by_tag(self, tag_name: str) -> list[Highlight]:
        tag_name_lower = tag_name.lower()
        return [
            highlight
            for highlight in self._client.list_highlights()
            if tag_name_lower in {tag.name.lower() for tag in (highlight.tags or [])}
        ]

    def get_untagged_highlights(self) -> list[Highlight]:
        return [highlight for highlight in self._client.list_highlights() if not highlight.tags]


__all__ = [
    "SyncTagOperations",
    "TagCleanupResult",
    "TagOperations",
    "TagPattern",
    "TagReport",
    "find_similar_tags",
    "normalize_tag",
]
