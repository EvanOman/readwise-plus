"""Legacy highlight-pushing compatibility shims."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk.operations.auth import AuthOperations
from readwise_sdk.operations.compat import (
    AsyncHighlightsResource,
    SyncHighlightsResource,
    run_sync,
)
from readwise_sdk.operations.highlights import (
    MAX_AUTHOR_LENGTH,
    MAX_NOTE_LENGTH,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    HighlightDeleteResult,
    HighlightOperations,
    HighlightPushInput,
    HighlightPushResult,
    HighlightUpdateInput,
    HighlightUpdateResult,
)
from readwise_sdk.operations.highlights import (
    TruncationInfo as OperationTruncationInfo,
)
from readwise_sdk.v2.models import BookCategory, Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import AsyncReadwiseClient, ReadwiseClient


@dataclass
class FieldTruncation:
    field_name: str
    original_length: int
    truncated_length: int

    @property
    def chars_removed(self) -> int:
        return self.original_length - self.truncated_length


@dataclass
class TruncationInfo:
    fields: list[FieldTruncation] = field(default_factory=list)

    @property
    def truncated_field_names(self) -> list[str]:
        return [item.field_name for item in self.fields]


@dataclass
class SimpleHighlight:
    text: str
    title: str
    author: str | None = None
    source_url: str | None = None
    source_type: str = "readwise_sdk"
    category: BookCategory | None = None
    note: str | None = None
    location: int | None = None
    location_type: str | None = None
    highlighted_at: datetime | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class PushResult:
    success: bool
    highlight_id: int | None = None
    book_id: int | None = None
    error: str | None = None
    original: SimpleHighlight | None = None
    was_truncated: bool = False
    truncation_info: TruncationInfo | None = None


@dataclass
class UpdateResult:
    success: bool
    highlight_id: int
    highlight: Highlight | None = None
    error: str | None = None
    was_truncated: bool = False
    truncation_info: TruncationInfo | None = None


@dataclass
class DeleteResult:
    success: bool
    highlight_id: int
    error: str | None = None


def _operation_input(highlight: SimpleHighlight) -> HighlightPushInput:
    return HighlightPushInput(
        text=highlight.text,
        title=highlight.title,
        author=highlight.author,
        source_url=highlight.source_url,
        source_type=highlight.source_type,
        category=highlight.category,
        note=highlight.note,
        location=highlight.location,
        location_type=highlight.location_type,
        highlighted_at=highlight.highlighted_at,
        tags=tuple(highlight.tags),
    )


def _legacy_truncation(info: OperationTruncationInfo | None) -> TruncationInfo | None:
    if info is None:
        return None
    return TruncationInfo(
        fields=[
            FieldTruncation(
                field_name=item.field_name,
                original_length=item.original_length,
                truncated_length=item.truncated_length,
            )
            for item in info.fields
        ]
    )


def _legacy_push(result: HighlightPushResult, original: SimpleHighlight) -> PushResult:
    return PushResult(
        success=result.success,
        highlight_id=result.highlight_id,
        book_id=None,
        error=result.error_message,
        original=original,
        was_truncated=result.was_truncated,
        truncation_info=_legacy_truncation(result.truncation_info),
    )


def _legacy_update(result: HighlightUpdateResult) -> UpdateResult:
    return UpdateResult(
        success=result.success,
        highlight_id=result.highlight_id,
        highlight=result.highlight,
        error=str(result.error) if result.error is not None else None,
        was_truncated=result.was_truncated,
        truncation_info=_legacy_truncation(result.truncation_info),
    )


def _legacy_delete(result: HighlightDeleteResult) -> DeleteResult:
    return DeleteResult(
        success=result.success,
        highlight_id=result.highlight_id,
        error=str(result.error) if result.error is not None else None,
    )


class HighlightPusher:
    """Synchronous compatibility wrapper over highlight operations."""

    def __init__(self, client: ReadwiseClient, *, auto_truncate: bool = True) -> None:
        self._client = client
        self._auto_truncate = auto_truncate
        resource = SyncHighlightsResource(client)
        self._operations = HighlightOperations(resource, resource, resource)
        self._auth = AuthOperations(resource)

    def push(
        self,
        text: str,
        title: str,
        *,
        author: str | None = None,
        source_url: str | None = None,
        source_type: str = "readwise_sdk",
        category: BookCategory | None = None,
        note: str | None = None,
        location: int | None = None,
        highlighted_at: datetime | None = None,
        tags: list[str] | None = None,
    ) -> PushResult:
        return self.push_highlight(
            SimpleHighlight(
                text=text,
                title=title,
                author=author,
                source_url=source_url,
                source_type=source_type,
                category=category,
                note=note,
                location=location,
                highlighted_at=highlighted_at,
                tags=tags or [],
            )
        )

    def push_highlight(self, highlight: SimpleHighlight) -> PushResult:
        return self.push_batch([highlight])[0]

    def push_batch(self, highlights: list[SimpleHighlight]) -> list[PushResult]:
        canonical = run_sync(
            self._operations.push_batch(
                [_operation_input(item) for item in highlights],
                auto_truncate=self._auto_truncate,
            )
        )
        return [_legacy_push(result, highlights[index]) for index, result in enumerate(canonical)]

    def validate_token(self) -> bool:
        return run_sync(self._auth.validate_token())

    def update(
        self,
        highlight_id: int,
        *,
        text: str | None = None,
        note: str | None = None,
        location: int | None = None,
        location_type: str | None = None,
    ) -> UpdateResult:
        return self.update_batch([(highlight_id, text, note, location, location_type)])[0]

    def update_batch(
        self,
        updates: list[tuple[int, str | None, str | None, int | None, str | None]],
    ) -> list[UpdateResult]:
        canonical = run_sync(
            self._operations.update_batch(
                [HighlightUpdateInput(*item) for item in updates],
                auto_truncate=self._auto_truncate,
            )
        )
        return [_legacy_update(result) for result in canonical]

    def delete(self, highlight_id: int) -> DeleteResult:
        return self.delete_batch([highlight_id])[0]

    def delete_batch(self, highlight_ids: list[int]) -> list[DeleteResult]:
        return [
            _legacy_delete(result)
            for result in run_sync(self._operations.delete_batch(highlight_ids))
        ]


class AsyncHighlightPusher:
    """Asynchronous compatibility wrapper over highlight operations."""

    def __init__(self, client: AsyncReadwiseClient, *, auto_truncate: bool = True) -> None:
        self._client = client
        self._auto_truncate = auto_truncate
        resource = AsyncHighlightsResource(client)
        self._operations = HighlightOperations(resource, resource, resource)
        self._auth = AuthOperations(resource)

    async def push(
        self,
        text: str,
        title: str,
        *,
        author: str | None = None,
        source_url: str | None = None,
        source_type: str = "readwise_sdk",
        category: BookCategory | None = None,
        note: str | None = None,
        location: int | None = None,
        highlighted_at: datetime | None = None,
        tags: list[str] | None = None,
    ) -> PushResult:
        return await self.push_highlight(
            SimpleHighlight(
                text=text,
                title=title,
                author=author,
                source_url=source_url,
                source_type=source_type,
                category=category,
                note=note,
                location=location,
                highlighted_at=highlighted_at,
                tags=tags or [],
            )
        )

    async def push_highlight(self, highlight: SimpleHighlight) -> PushResult:
        return (await self.push_batch([highlight]))[0]

    async def push_batch(self, highlights: list[SimpleHighlight]) -> list[PushResult]:
        canonical = await self._operations.push_batch(
            [_operation_input(item) for item in highlights],
            auto_truncate=self._auto_truncate,
        )
        return [_legacy_push(result, highlights[index]) for index, result in enumerate(canonical)]

    async def validate_token(self) -> bool:
        return await self._auth.validate_token()

    async def update(
        self,
        highlight_id: int,
        *,
        text: str | None = None,
        note: str | None = None,
        location: int | None = None,
        location_type: str | None = None,
    ) -> UpdateResult:
        return (await self.update_batch([(highlight_id, text, note, location, location_type)]))[0]

    async def update_batch(
        self,
        updates: list[tuple[int, str | None, str | None, int | None, str | None]],
    ) -> list[UpdateResult]:
        canonical = await self._operations.update_batch(
            [HighlightUpdateInput(*item) for item in updates],
            auto_truncate=self._auto_truncate,
        )
        return [_legacy_update(result) for result in canonical]

    async def delete(self, highlight_id: int) -> DeleteResult:
        return (await self.delete_batch([highlight_id]))[0]

    async def delete_batch(self, highlight_ids: list[int]) -> list[DeleteResult]:
        return [
            _legacy_delete(result) for result in await self._operations.delete_batch(highlight_ids)
        ]


__all__ = [
    "AsyncHighlightPusher",
    "DeleteResult",
    "FieldTruncation",
    "HighlightPusher",
    "MAX_AUTHOR_LENGTH",
    "MAX_NOTE_LENGTH",
    "MAX_TEXT_LENGTH",
    "MAX_TITLE_LENGTH",
    "PushResult",
    "SimpleHighlight",
    "TruncationInfo",
    "UpdateResult",
]
