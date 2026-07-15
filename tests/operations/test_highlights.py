"""Unit tests for canonical highlight operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from readwise_sdk.models import HighlightSearch
from readwise_sdk.operations.highlights import (
    MAX_AUTHOR_LENGTH,
    MAX_NOTE_LENGTH,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    HighlightOperations,
    HighlightPushInput,
    HighlightUpdateInput,
)
from readwise_sdk.operations.service import ReadwiseService
from readwise_sdk.v2.models import (
    BookCategory,
    ExportBook,
    Highlight,
    HighlightColor,
    HighlightCreate,
    HighlightUpdate,
    Tag,
)


class FakeHighlightsResource:
    """In-memory seam matching the v2 highlight resource contract."""

    def __init__(self, highlights: list[Highlight] | None = None) -> None:
        self.highlights = highlights or []
        self.iter_calls: list[dict[str, object]] = []
        self.get_calls: list[int] = []
        self.create_calls: list[list[HighlightCreate]] = []
        self.update_calls: list[tuple[int, HighlightUpdate]] = []
        self.delete_calls: list[int] = []
        self.created_ids: list[int] = [101]
        self.create_error: Exception | None = None
        self.update_errors: dict[int, Exception] = {}
        self.delete_errors: dict[int, Exception] = {}

    async def iter(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> AsyncIterator[Highlight]:
        self.iter_calls.append(
            {
                "page_size": page_size,
                "book_id": book_id,
                "updated_after": updated_after,
                "updated_before": updated_before,
                "highlighted_after": highlighted_after,
                "highlighted_before": highlighted_before,
            }
        )
        for item in self.highlights:
            if book_id is not None and item.book_id != book_id:
                continue
            yield item

    async def get(self, highlight_id: int) -> Highlight:
        self.get_calls.append(highlight_id)
        return next(item for item in self.highlights if item.id == highlight_id)

    async def create(self, highlights: list[HighlightCreate]) -> list[int]:
        self.create_calls.append(highlights)
        if self.create_error is not None:
            raise self.create_error
        return self.created_ids

    async def update(self, highlight_id: int, update: HighlightUpdate) -> Highlight:
        self.update_calls.append((highlight_id, update))
        if error := self.update_errors.get(highlight_id):
            raise error
        return Highlight(id=highlight_id, text=update.text or "unchanged", note=update.note)

    async def delete(self, highlight_id: int) -> None:
        self.delete_calls.append(highlight_id)
        if error := self.delete_errors.get(highlight_id):
            raise error


class FakeHighlightTagsResource:
    """In-memory seam for highlight tag composition and failures."""

    def __init__(self) -> None:
        self.tags: dict[int, list[Tag]] = {}
        self.create_calls: list[tuple[int, str]] = []
        self.delete_calls: list[tuple[int, int]] = []
        self.create_errors: dict[int, Exception] = {}
        self.iter_errors: dict[int, Exception] = {}
        self.delete_errors: dict[int, Exception] = {}

    async def iter_highlight(self, highlight_id: int) -> AsyncIterator[Tag]:
        if error := self.iter_errors.get(highlight_id):
            raise error
        for tag in self.tags.get(highlight_id, []):
            yield tag

    async def create_highlight(self, highlight_id: int, name: str) -> Tag:
        self.create_calls.append((highlight_id, name))
        if error := self.create_errors.get(highlight_id):
            raise error
        return Tag(id=highlight_id * 10, name=name)

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None:
        self.delete_calls.append((highlight_id, tag_id))
        if error := self.delete_errors.get(highlight_id):
            raise error


class FakeExportResource:
    """In-memory seam for already-grouped v2 export results."""

    def __init__(self, books: list[ExportBook] | None = None) -> None:
        self.books = books or []
        self.iter_calls: list[dict[str, object]] = []

    async def iter(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: list[int] | None = None,
        include_deleted: bool = False,
    ) -> AsyncIterator[ExportBook]:
        self.iter_calls.append(
            {
                "updated_after": updated_after,
                "book_ids": book_ids,
                "include_deleted": include_deleted,
            }
        )
        for book in self.books:
            yield book


def highlight(
    highlight_id: int,
    text: str,
    *,
    note: str | None = None,
    book_id: int | None = None,
    tags: list[Tag] | None = None,
) -> Highlight:
    """Build a compact highlight fixture."""
    return Highlight(
        id=highlight_id,
        text=text,
        note=note,
        book_id=book_id,
        color=HighlightColor.YELLOW,
        location=0,
        tags=tags or [],
    )


def operations(
    highlights: FakeHighlightsResource | None = None,
    tags: FakeHighlightTagsResource | None = None,
    export: FakeExportResource | None = None,
) -> HighlightOperations:
    """Compose the three resource seams needed by highlight operations."""
    return HighlightOperations(
        highlights or FakeHighlightsResource(),
        tags or FakeHighlightTagsResource(),
        export or FakeExportResource(),
    )


@pytest.mark.asyncio
async def test_search_ports_mcp_text_filter_projection_limit_and_resource_arguments() -> None:
    """Canonical search is text-only, case-insensitive, bounded, and projected."""
    updated_after = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)
    resource = FakeHighlightsResource(
        [
            highlight(1, "A PYTHON insight", book_id=7, tags=[Tag(id=1, name="sdk")]),
            highlight(2, "Unrelated", note="python note", book_id=7),
            highlight(3, "python second", book_id=7),
        ]
    )

    result = await operations(resource).search(
        HighlightSearch(book_id=7, updated_after=updated_after, query="python", limit=2)
    )

    assert [item.id for item in result.items] == [1, 3]
    assert result.items[0].tags == ("sdk",)
    assert result.items[0].color is HighlightColor.YELLOW
    assert result.items[0].location == 0
    assert result.truncated is True
    assert resource.iter_calls == [
        {
            "page_size": 100,
            "book_id": 7,
            "updated_after": updated_after,
            "updated_before": None,
            "highlighted_after": None,
            "highlighted_before": None,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("provided", "expected"), [(0, 1), (1000, 200)])
async def test_search_uses_stage_five_limit_clamping(provided: int, expected: int) -> None:
    """Highlight searches retain MCP's inclusive 1..200 clamp."""
    resource = FakeHighlightsResource([highlight(index, f"match-{index}") for index in range(201)])

    result = await operations(resource).search(HighlightSearch(query="match", limit=provided))

    assert len(result.items) == expected


@pytest.mark.asyncio
async def test_list_get_create_update_and_delete_delegate_raw_models() -> None:
    """Raw CRUD remains available without imposing adapter projections."""
    existing = highlight(1, "Existing")
    resource = FakeHighlightsResource([existing])
    resource.created_ids = [8, 9]
    operation = operations(resource)
    create = HighlightCreate(text="New")
    update = HighlightUpdate(note="Remember")

    assert await operation.list(limit=1) == [existing]
    assert await operation.list(limit=0) == []
    assert await operation.get(1) is existing
    assert await operation.create(create) == [8, 9]
    updated = await operation.update(1, update)
    await operation.delete(1)

    assert updated.note == "Remember"
    assert resource.create_calls == [[create]]
    assert resource.update_calls == [(1, update)]
    assert resource.delete_calls == [1]


@pytest.mark.asyncio
async def test_manager_search_and_collection_variants_preserve_legacy_semantics() -> None:
    """Manager-compatible helpers retain note search, case mode, time precedence, and counts."""
    explicit_since = datetime(2024, 1, 1, tzinfo=UTC)
    noted = highlight(1, "Alpha", note="Needle")
    lower = highlight(2, "needle", note=None)
    resource = FakeHighlightsResource([noted, lower])
    operation = operations(resource)

    assert await operation.search_items("needle") == [noted, lower]
    assert await operation.search_items("Needle", case_sensitive=True) == [noted]
    assert await operation.with_notes() == [noted]
    assert await operation.count() == 2
    assert [item async for item in operation.filter(lambda item: item.id == 2)] == [lower]
    assert await operation.since(days=99, hours=99, since=explicit_since) == [noted, lower]
    assert resource.iter_calls[-1]["updated_after"] is explicit_since

    with pytest.raises(ValueError, match="Must specify days, hours, or since"):
        await operation.since()


@pytest.mark.asyncio
async def test_create_from_fields_preserves_mcp_category_and_raw_slice_policy() -> None:
    """MCP creation accepts enum values (including supplementals) and slices text without ellipsis."""
    resource = FakeHighlightsResource()
    resource.created_ids = [77]
    operation = operations(resource)
    long_text = "x" * (MAX_TEXT_LENGTH + 10)

    result = await operation.create_from_fields(
        text=long_text,
        title="Title",
        category="supplementals",
    )

    sent = resource.create_calls[0][0]
    assert result.ids == [77]
    assert result.was_truncated is True
    assert sent.text == "x" * MAX_TEXT_LENGTH
    assert not sent.text.endswith("...")
    assert sent.category is BookCategory.SUPPLEMENTALS

    with pytest.raises(ValueError, match="Invalid category 'invalid'"):
        await operation.create_from_fields(text="text", category="invalid")
    assert len(resource.create_calls) == 1


@pytest.mark.asyncio
async def test_push_batch_preserves_pusher_truncation_order_and_missing_id_shape() -> None:
    """Pusher batches use ellipses, report all truncated fields, and retain input ordering."""
    resource = FakeHighlightsResource()
    resource.created_ids = [501]
    operation = operations(resource)
    first = HighlightPushInput(
        text="t" * (MAX_TEXT_LENGTH + 4),
        title="y" * (MAX_TITLE_LENGTH + 4),
        author="a" * (MAX_AUTHOR_LENGTH + 4),
        note="n" * (MAX_NOTE_LENGTH + 4),
        tags=("ignored",),
    )
    second = HighlightPushInput(text="short", title="Second")

    results = await operation.push_batch([first, second])

    sent = resource.create_calls[0]
    assert sent[0].text.endswith("...") and len(sent[0].text) == MAX_TEXT_LENGTH
    assert sent[0].title is not None and sent[0].title.endswith("...")
    assert sent[0].author is not None and sent[0].author.endswith("...")
    assert sent[0].note is not None and sent[0].note.endswith("...")
    assert "tags" not in sent[0].to_api_dict()
    assert results[0].success is True
    assert results[0].highlight_id == 501
    assert results[0].original is first
    assert results[0].truncation_info is not None
    assert results[0].truncation_info.truncated_field_names == [
        "text",
        "note",
        "title",
        "author",
    ]
    assert results[1].success is False
    assert results[1].error_message == "No API result returned"
    assert results[1].original is second


@pytest.mark.asyncio
async def test_push_batch_marks_every_input_failed_when_the_single_api_batch_fails() -> None:
    """One create request failure is retained against every batch input."""
    resource = FakeHighlightsResource()
    error = RuntimeError("batch failed")
    resource.create_error = error
    inputs = [
        HighlightPushInput(text="one", title="One"),
        HighlightPushInput(text="two", title="Two"),
    ]

    results = await operations(resource).push_batch(inputs)

    assert [result.original for result in results] == inputs
    assert all(result.success is False for result in results)
    assert all(result.error is error for result in results)


@pytest.mark.asyncio
async def test_update_and_delete_batches_continue_and_retain_ordered_failures() -> None:
    """Pusher mutation batches isolate each item and retain truncation metadata."""
    resource = FakeHighlightsResource()
    update_error = RuntimeError("update failed")
    delete_error = RuntimeError("delete failed")
    resource.update_errors[2] = update_error
    resource.delete_errors[2] = delete_error
    operation = operations(resource)

    updates = await operation.update_batch(
        [
            HighlightUpdateInput(1, text="x" * (MAX_TEXT_LENGTH + 5)),
            HighlightUpdateInput(2, note="note"),
        ]
    )
    deletes = await operation.delete_batch([1, 2, 3])

    assert updates[0].success is True
    assert updates[0].truncation_info is not None
    assert updates[0].truncation_info.truncated_field_names == ["text"]
    assert updates[1].success is False and updates[1].error is update_error
    assert [result.success for result in deletes] == [True, False, True]
    assert deletes[1].error is delete_error


@pytest.mark.asyncio
async def test_bulk_tag_and_untag_preserve_broad_partial_failure_policy() -> None:
    """Manager bool-map semantics can be reconstructed from successes and failures."""
    tags = FakeHighlightTagsResource()
    tag_error = RuntimeError("tag failed")
    untag_error = RuntimeError("list failed")
    tags.create_errors[2] = tag_error
    tags.tags = {
        1: [Tag(id=10, name="other"), Tag(id=11, name="target"), Tag(id=12, name="target")],
        2: [Tag(id=20, name="other")],
    }
    tags.iter_errors[3] = untag_error
    operation = operations(tags=tags)

    tagged = await operation.bulk_tag([1, 2, 3], "target")
    untagged = await operation.bulk_untag([1, 2, 3], "target")

    assert tagged.succeeded == [1, 3]
    assert tagged.failures[0].item == 2 and tagged.failures[0].error is tag_error
    assert untagged.succeeded == [1, 2]
    assert untagged.failures[0].item == 3 and untagged.failures[0].error is untag_error
    assert tags.delete_calls == [(1, 11)]


@pytest.mark.asyncio
async def test_export_preserves_grouping_projection_filters_and_limit_clamping() -> None:
    """Export remains grouped by book and bounded over books, not nested highlights."""
    timestamp = datetime(2025, 2, 3, tzinfo=UTC)
    books = [
        ExportBook(
            user_book_id=index,
            title=f"Book {index}",
            author=None,
            category=BookCategory.BOOKS,
            highlights=[highlight(index, f"Insight {index}", tags=[Tag(id=1, name="tag")])],
        )
        for index in range(101)
    ]
    resource = FakeExportResource(books)

    result = await operations(export=resource).export(
        updated_after=timestamp,
        book_ids=[3, 4],
        limit=1000,
    )

    assert len(result.items) == 100
    assert result.truncated is True
    assert result.items[0].book_id == 0
    assert result.items[0].highlights[0].tags == ("tag",)
    assert resource.iter_calls == [
        {"updated_after": timestamp, "book_ids": [3, 4], "include_deleted": False}
    ]


def test_service_wires_canonical_highlight_operations() -> None:
    """The service composes highlights from highlight, tag, and export resources."""
    service = ReadwiseService(
        documents=None,
        highlights=FakeHighlightsResource(),
        highlight_tags=FakeHighlightTagsResource(),
        export=FakeExportResource(),
    )

    assert isinstance(service.highlights, HighlightOperations)
