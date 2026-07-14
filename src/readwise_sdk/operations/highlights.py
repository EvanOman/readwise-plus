"""Canonical async-first operations for Readwise highlights."""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

from readwise_sdk.models import BulkResult, HighlightSearch, HighlightSummary
from readwise_sdk.models.readwise import (
    BookCategory,
    ExportBook,
    Highlight,
    HighlightCreate,
    HighlightUpdate,
    Tag,
)
from readwise_sdk.models.results import OperationFailure

MAX_TEXT_LENGTH = 8191
MAX_NOTE_LENGTH = 8191
MAX_TITLE_LENGTH = 511
MAX_AUTHOR_LENGTH = 1024


class HighlightsResource(Protocol):
    """Low-level highlight capabilities required by highlight operations."""

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

    async def get(self, highlight_id: int) -> Highlight: ...

    async def create(self, highlights: list[HighlightCreate]) -> list[int]: ...

    async def update(self, highlight_id: int, update: HighlightUpdate) -> Highlight: ...

    async def delete(self, highlight_id: int) -> None: ...


class HighlightTagsResource(Protocol):
    """Low-level highlight-tag capabilities required by bulk operations."""

    def iter_highlight(self, highlight_id: int) -> AsyncIterator[Tag]: ...

    async def create_highlight(self, highlight_id: int, name: str) -> Tag: ...

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None: ...


class ExportResource(Protocol):
    """Low-level grouped-export capability required by highlight export."""

    def iter(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: list[int] | None = None,
        include_deleted: bool = False,
    ) -> AsyncIterator[ExportBook]: ...


@dataclass(frozen=True, slots=True)
class FieldTruncation:
    """One field shortened by an operation-owned input policy."""

    field_name: str
    original_length: int
    truncated_length: int

    @property
    def chars_removed(self) -> int:
        """Return the number of characters removed."""
        return self.original_length - self.truncated_length


@dataclass(frozen=True, slots=True)
class TruncationInfo:
    """Ordered details for every field shortened in one request."""

    fields: tuple[FieldTruncation, ...] = ()

    @property
    def truncated_field_names(self) -> list[str]:
        """Return field names in the legacy reporting order."""
        return [item.field_name for item in self.fields]


@dataclass(frozen=True, slots=True)
class HighlightPushInput:
    """Pusher-compatible input retained independently from protocol models."""

    text: str | None
    title: str | None
    author: str | None = None
    source_url: str | None = None
    source_type: str = "readwise_sdk"
    category: BookCategory | None = None
    note: str | None = None
    location: int | None = None
    location_type: str | None = None
    highlighted_at: datetime | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HighlightUpdateInput:
    """One pusher-compatible update request."""

    highlight_id: int
    text: str | None = None
    note: str | None = None
    location: int | None = None
    location_type: str | None = None


@dataclass(frozen=True, slots=True)
class HighlightCreateResult:
    """Created IDs plus operation-owned truncation metadata."""

    ids: list[int]
    was_truncated: bool = False
    truncation_info: TruncationInfo | None = None


@dataclass(frozen=True, slots=True)
class HighlightPushResult:
    """One ordered result from the pusher-compatible batch policy."""

    original: HighlightPushInput
    highlight_id: int | None = None
    error: Exception | str | None = None
    was_truncated: bool = False
    truncation_info: TruncationInfo | None = None

    @property
    def success(self) -> bool:
        """Return whether an ID was produced without an error."""
        return self.error is None and self.highlight_id is not None

    @property
    def error_message(self) -> str | None:
        """Return adapter-ready error text without discarding exceptions."""
        return str(self.error) if self.error is not None else None


@dataclass(frozen=True, slots=True)
class HighlightUpdateResult:
    """One ordered result from the pusher-compatible update policy."""

    highlight_id: int
    highlight: Highlight | None = None
    error: Exception | None = None
    was_truncated: bool = False
    truncation_info: TruncationInfo | None = None

    @property
    def success(self) -> bool:
        """Return whether the update produced a highlight."""
        return self.error is None and self.highlight is not None


@dataclass(frozen=True, slots=True)
class HighlightDeleteResult:
    """One ordered result from the pusher-compatible delete policy."""

    highlight_id: int
    error: Exception | None = None

    @property
    def success(self) -> bool:
        """Return whether deletion completed without an exception."""
        return self.error is None


@dataclass(frozen=True, slots=True)
class HighlightSearchResult:
    """Bounded semantic highlight summaries."""

    items: list[HighlightSummary] = field(default_factory=list)
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class HighlightExportGroup:
    """One exported book with its projected highlights nested inside."""

    book_id: int
    title: str
    author: str | None = None
    category: BookCategory | None = None
    source: str | None = None
    source_url: str | None = None
    highlights: list[HighlightSummary] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class HighlightExportResult:
    """A bounded number of grouped export books."""

    items: list[HighlightExportGroup] = field(default_factory=list)
    truncated: bool = False


def _summary(highlight: Highlight) -> HighlightSummary:
    """Project the fields shared by current CLI and MCP adapters."""
    return HighlightSummary(
        id=highlight.id,
        text=highlight.text,
        note=highlight.note,
        book_id=highlight.book_id,
        color=highlight.color,
        location=highlight.location,
        highlighted_at=highlight.highlighted_at,
        tags=tuple(tag.name for tag in highlight.tags),
    )


def _truncate_with_ellipsis(value: str | None, maximum: int) -> tuple[str | None, bool]:
    """Reproduce HighlightPusher's maximum-length ellipsis policy."""
    if value is None or len(value) <= maximum:
        return value, False
    return value[: maximum - 3] + "...", True


def _truncation(
    field_name: str,
    original: str | None,
    truncated: bool,
    maximum: int,
) -> FieldTruncation | None:
    if not truncated or original is None:
        return None
    return FieldTruncation(field_name, len(original), maximum)


def _prepare_push(
    item: HighlightPushInput,
    *,
    auto_truncate: bool,
) -> tuple[HighlightCreate, TruncationInfo | None]:
    text = item.text
    note = item.note
    title = item.title
    author = item.author
    details: list[FieldTruncation] = []

    if auto_truncate:
        original_text, original_note = text, note
        original_title, original_author = title, author
        text, text_cut = _truncate_with_ellipsis(text, MAX_TEXT_LENGTH)
        note, note_cut = _truncate_with_ellipsis(note, MAX_NOTE_LENGTH)
        title, title_cut = _truncate_with_ellipsis(title, MAX_TITLE_LENGTH)
        author, author_cut = _truncate_with_ellipsis(author, MAX_AUTHOR_LENGTH)
        for detail in (
            _truncation("text", original_text, text_cut, MAX_TEXT_LENGTH),
            _truncation("note", original_note, note_cut, MAX_NOTE_LENGTH),
            _truncation("title", original_title, title_cut, MAX_TITLE_LENGTH),
            _truncation("author", original_author, author_cut, MAX_AUTHOR_LENGTH),
        ):
            if detail is not None:
                details.append(detail)
        if text is None:
            # Characterizes the current pusher's type-bypassing None quirk.
            text = ""

    request = HighlightCreate(
        # The cast preserves HighlightPusher's runtime validation when
        # auto-truncation is disabled and a caller bypasses the declared type.
        text=cast(str, text),
        title=title,
        author=author,
        source_url=item.source_url,
        source_type=item.source_type,
        category=item.category,
        note=note,
        location=item.location,
        location_type=item.location_type,
        highlighted_at=item.highlighted_at,
    )
    return request, TruncationInfo(tuple(details)) if details else None


def _prepare_update(
    item: HighlightUpdateInput,
    *,
    auto_truncate: bool,
) -> tuple[HighlightUpdate, TruncationInfo | None]:
    text = item.text
    note = item.note
    details: list[FieldTruncation] = []
    if auto_truncate:
        original_text, original_note = text, note
        text, text_cut = _truncate_with_ellipsis(text, MAX_TEXT_LENGTH)
        note, note_cut = _truncate_with_ellipsis(note, MAX_NOTE_LENGTH)
        for detail in (
            _truncation("text", original_text, text_cut, MAX_TEXT_LENGTH),
            _truncation("note", original_note, note_cut, MAX_NOTE_LENGTH),
        ):
            if detail is not None:
                details.append(detail)

    request = HighlightUpdate(
        text=text,
        note=note,
        location=item.location,
        location_type=item.location_type,
    )
    return request, TruncationInfo(tuple(details)) if details else None


def _parse_category(category: str | BookCategory | None) -> BookCategory | None:
    if category is None or isinstance(category, BookCategory):
        return category
    try:
        return BookCategory(category)
    except ValueError:
        raise ValueError(f"Invalid category '{category}'") from None


class HighlightOperations:
    """Own highlight filtering, limits, truncation, and partial-failure policy."""

    def __init__(
        self,
        resource: HighlightsResource,
        tags: HighlightTagsResource,
        export_resource: ExportResource,
    ) -> None:
        self._resource = resource
        self._tags = tags
        self._export = export_resource

    async def search(self, search: HighlightSearch) -> HighlightSearchResult:
        """Return bounded MCP-compatible summaries using text-only matching."""
        query = search.query.lower() if search.query else None
        items: list[HighlightSummary] = []
        async for highlight in self._resource.iter(
            book_id=search.book_id,
            updated_after=search.updated_after,
        ):
            if query and query not in highlight.text.lower():
                continue
            items.append(_summary(highlight))
            if len(items) >= search.limit:
                return HighlightSearchResult(items=items, truncated=True)
        return HighlightSearchResult(items=items, truncated=False)

    async def list(
        self,
        *,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
        limit: int | None = None,
    ) -> builtins.list[Highlight]:
        """Materialize raw highlights with the CLI's un-clamped limit behavior."""
        items: list[Highlight] = []
        async for highlight in self._resource.iter(
            book_id=book_id,
            updated_after=updated_after,
            updated_before=updated_before,
            highlighted_after=highlighted_after,
            highlighted_before=highlighted_before,
        ):
            if limit is not None and len(items) >= limit:
                break
            items.append(highlight)
        return items

    async def get(self, highlight_id: int) -> Highlight:
        """Get one highlight."""
        return await self._resource.get(highlight_id)

    async def create(self, highlight: HighlightCreate) -> builtins.list[int]:
        """Create one typed highlight and retain every ID returned by v2."""
        return await self._resource.create([highlight])

    async def create_from_fields(
        self,
        *,
        text: str,
        title: str | None = None,
        author: str | None = None,
        source_url: str | None = None,
        note: str | None = None,
        category: str | BookCategory | None = None,
        highlighted_at: datetime | None = None,
    ) -> HighlightCreateResult:
        """Create with MCP's raw 8191-character text slice and enum validation."""
        truncated = len(text) > MAX_TEXT_LENGTH
        request = HighlightCreate(
            text=text[:MAX_TEXT_LENGTH],
            title=title,
            author=author,
            source_url=source_url,
            note=note,
            category=_parse_category(category),
            highlighted_at=highlighted_at,
        )
        ids = await self.create(request)
        info = None
        if truncated:
            info = TruncationInfo((FieldTruncation("text", len(text), MAX_TEXT_LENGTH),))
        return HighlightCreateResult(ids=ids, was_truncated=truncated, truncation_info=info)

    async def push_batch(
        self,
        highlights: builtins.list[HighlightPushInput],
        *,
        auto_truncate: bool = True,
    ) -> builtins.list[HighlightPushResult]:
        """Apply the pusher's one-request batch and all-input failure policy."""
        if not highlights:
            return []

        requests: list[HighlightCreate] = []
        infos: list[TruncationInfo | None] = []
        # Conversion intentionally precedes the API try block, matching HighlightPusher.
        for item in highlights:
            request, info = _prepare_push(item, auto_truncate=auto_truncate)
            requests.append(request)
            infos.append(info)

        try:
            ids = await self._resource.create(requests)
        except Exception as error:
            # Characterizes current broad, whole-batch pusher failure handling.
            return [
                HighlightPushResult(
                    original=item,
                    error=error,
                    was_truncated=infos[index] is not None,
                    truncation_info=infos[index],
                )
                for index, item in enumerate(highlights)
            ]

        results: list[HighlightPushResult] = []
        for index, item in enumerate(highlights):
            highlight_id = ids[index] if index < len(ids) else None
            results.append(
                HighlightPushResult(
                    original=item,
                    highlight_id=highlight_id,
                    error=None if highlight_id is not None else "No API result returned",
                    was_truncated=infos[index] is not None,
                    truncation_info=infos[index],
                )
            )
        return results

    async def update(self, highlight_id: int, update: HighlightUpdate) -> Highlight:
        """Update one typed highlight."""
        return await self._resource.update(highlight_id, update)

    async def update_batch(
        self,
        updates: builtins.list[HighlightUpdateInput],
        *,
        auto_truncate: bool = True,
    ) -> builtins.list[HighlightUpdateResult]:
        """Update sequentially and isolate every pusher-compatible failure."""
        results: list[HighlightUpdateResult] = []
        for item in updates:
            try:
                request, info = _prepare_update(item, auto_truncate=auto_truncate)
                highlight = await self.update(item.highlight_id, request)
                results.append(
                    HighlightUpdateResult(
                        highlight_id=item.highlight_id,
                        highlight=highlight,
                        was_truncated=info is not None,
                        truncation_info=info,
                    )
                )
            except Exception as error:
                # Characterizes current broad per-update pusher failure handling.
                results.append(HighlightUpdateResult(highlight_id=item.highlight_id, error=error))
        return results

    async def delete(self, highlight_id: int) -> None:
        """Delete one highlight."""
        await self._resource.delete(highlight_id)

    async def delete_batch(
        self, highlight_ids: builtins.list[int]
    ) -> builtins.list[HighlightDeleteResult]:
        """Delete sequentially and isolate every pusher-compatible failure."""
        results: list[HighlightDeleteResult] = []
        for highlight_id in highlight_ids:
            try:
                await self.delete(highlight_id)
                results.append(HighlightDeleteResult(highlight_id))
            except Exception as error:
                # Characterizes current broad per-delete pusher failure handling.
                results.append(HighlightDeleteResult(highlight_id, error))
        return results

    async def search_items(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> builtins.list[Highlight]:
        """Reproduce manager search across highlight text and notes."""
        normalized = query if case_sensitive else query.lower()
        results: list[Highlight] = []
        async for highlight in self._resource.iter():
            text = highlight.text if case_sensitive else highlight.text.lower()
            note = highlight.note or ""
            if not case_sensitive:
                note = note.lower()
            if normalized in text or normalized in note:
                results.append(highlight)
        return results

    async def since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> builtins.list[Highlight]:
        """Reproduce manager time-window precedence and validation."""
        if since is None:
            if days is not None:
                since = datetime.now(UTC) - timedelta(days=days)
            elif hours is not None:
                since = datetime.now(UTC) - timedelta(hours=hours)
            else:
                raise ValueError("Must specify days, hours, or since")
        return await self.list(updated_after=since)

    async def with_notes(self) -> builtins.list[Highlight]:
        """Materialize highlights whose note is truthy."""
        return [highlight async for highlight in self._resource.iter() if highlight.note]

    async def filter(
        self,
        predicate: Callable[[Highlight], bool],
    ) -> AsyncIterator[Highlight]:
        """Retain manager-compatible lazy predicate filtering."""
        async for highlight in self._resource.iter():
            if predicate(highlight):
                yield highlight

    async def count(self) -> int:
        """Count every highlight without materializing them."""
        count = 0
        async for _ in self._resource.iter():
            count += 1
        return count

    async def bulk_tag(self, highlight_ids: builtins.list[int], tag: str) -> BulkResult[int]:
        """Tag sequentially and retain every manager-compatible failure."""
        succeeded: list[int] = []
        failures: list[OperationFailure] = []
        for highlight_id in highlight_ids:
            try:
                await self._tags.create_highlight(highlight_id, tag)
                succeeded.append(highlight_id)
            except Exception as error:
                # Characterizes current broad per-item manager failure handling.
                failures.append(OperationFailure(item=highlight_id, error=error))
        return BulkResult[int](succeeded=succeeded, failures=failures)

    async def bulk_untag(self, highlight_ids: builtins.list[int], tag: str) -> BulkResult[int]:
        """Delete only the first exact tag match; missing tags count as success."""
        succeeded: list[int] = []
        failures: list[OperationFailure] = []
        for highlight_id in highlight_ids:
            try:
                match = None
                async for existing in self._tags.iter_highlight(highlight_id):
                    if existing.name == tag:
                        match = existing
                        break
                if match is not None:
                    await self._tags.delete_highlight(highlight_id, match.id)
                succeeded.append(highlight_id)
            except Exception as error:
                # Characterizes current broad per-item manager failure handling.
                failures.append(OperationFailure(item=highlight_id, error=error))
        return BulkResult[int](succeeded=succeeded, failures=failures)

    async def export(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: builtins.list[int] | None = None,
        limit: int = 20,
    ) -> HighlightExportResult:
        """Return MCP-compatible grouped summaries with a 1..100 book limit."""
        bounded_limit = min(max(limit, 1), 100)
        items: list[HighlightExportGroup] = []
        async for book in self._export.iter(
            updated_after=updated_after,
            book_ids=book_ids,
        ):
            items.append(
                HighlightExportGroup(
                    book_id=book.user_book_id,
                    title=book.title,
                    author=book.author,
                    category=book.category,
                    source=book.source,
                    source_url=book.source_url,
                    highlights=[_summary(highlight) for highlight in book.highlights],
                )
            )
            if len(items) >= bounded_limit:
                return HighlightExportResult(items=items, truncated=True)
        return HighlightExportResult(items=items, truncated=False)


__all__ = [
    "ExportResource",
    "FieldTruncation",
    "HighlightCreateResult",
    "HighlightDeleteResult",
    "HighlightExportGroup",
    "HighlightExportResult",
    "HighlightOperations",
    "HighlightPushInput",
    "HighlightPushResult",
    "HighlightSearchResult",
    "HighlightTagsResource",
    "HighlightUpdateInput",
    "HighlightUpdateResult",
    "HighlightsResource",
    "MAX_AUTHOR_LENGTH",
    "MAX_NOTE_LENGTH",
    "MAX_TEXT_LENGTH",
    "MAX_TITLE_LENGTH",
    "TruncationInfo",
]
