"""Direct contracts for canonical tag operations."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from readwise_sdk.operations.tags import TagOperations, TagPattern
from readwise_sdk.v2.models import Highlight, Tag


class HighlightResource:
    def __init__(self, highlights: list[Highlight]) -> None:
        self.highlights = highlights

    async def iter(self, **kwargs: object) -> AsyncIterator[Highlight]:
        assert kwargs == {}
        for highlight in self.highlights:
            yield highlight


class TagResource:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def create_highlight(self, highlight_id: int, name: str) -> Tag:
        self.calls.append(("create", highlight_id, name))
        if name == "fails":
            raise RuntimeError("characterizes suppressed tag failures")
        return Tag(id=99, name=name)

    async def update_highlight(self, highlight_id: int, tag_id: int, name: str) -> Tag:
        self.calls.append(("update", highlight_id, tag_id, name))
        return Tag(id=tag_id, name=name)

    async def delete_highlight(self, highlight_id: int, tag_id: int) -> None:
        self.calls.append(("delete", highlight_id, tag_id))


def _highlight(
    highlight_id: int,
    text: str,
    *tags: tuple[int, str],
    note: str | None = None,
) -> Highlight:
    return Highlight(
        id=highlight_id,
        text=text,
        note=note,
        tags=[Tag(id=tag_id, name=name) for tag_id, name in tags],
    )


@pytest.mark.asyncio
async def test_tag_search_report_and_untagged_selection_match_workflow_semantics() -> None:
    highlights = [
        _highlight(1, "One", (10, "Python"), (11, "python!")),
        _highlight(2, "Two", (12, "Python")),
        _highlight(3, "Three"),
    ]
    operations = TagOperations(HighlightResource(highlights), TagResource())

    report = await operations.get_tag_report()

    assert report.total_tags == 2
    assert report.total_usages == 3
    assert report.tags_by_usage == [("Python", 2), ("python!", 1)]
    assert len(report.duplicate_candidates) == 1
    assert set(report.duplicate_candidates[0]) == {"Python", "python!"}
    assert [item.id for item in await operations.get_highlights_by_tag("PYTHON")] == [1, 2]
    assert [item.id for item in await operations.get_untagged_highlights()] == [3]


@pytest.mark.asyncio
async def test_auto_tag_preserves_matching_order_and_suppresses_apply_failures() -> None:
    tags = TagResource()
    operations = TagOperations(
        HighlightResource([_highlight(1, "Python and Rust", note="important")]),
        tags,
    )
    patterns = [
        TagPattern("python", "language"),
        TagPattern("important", "fails", match_in_text=False),
        TagPattern("rust", "systems"),
    ]

    result = await operations.auto_tag_highlights(patterns)

    assert result == {1: ["language", "fails", "systems"]}
    assert tags.calls == [
        ("create", 1, "language"),
        ("create", 1, "fails"),
        ("create", 1, "systems"),
    ]


@pytest.mark.asyncio
async def test_merge_rename_and_delete_preserve_legacy_mutation_semantics() -> None:
    highlight = _highlight(1, "One", (10, "Old"), (11, "Keep"))
    tags = TagResource()
    operations = TagOperations(HighlightResource([highlight]), tags)

    assert await operations.merge_tags(["old"], "New") == [1]
    assert await operations.rename_tag("OLD", "Renamed") == [1]
    assert await operations.delete_tag("old") == [1]
    assert tags.calls == [
        ("create", 1, "New"),
        ("delete", 1, 10),
        ("update", 1, 10, "Renamed"),
        ("delete", 1, 10),
    ]
