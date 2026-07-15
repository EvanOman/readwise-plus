"""Direct contracts for canonical digest selection and grouping."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from readwise_sdk.operations.digests import DigestGrouping, DigestOperations
from readwise_sdk.v2.models import Book, Highlight


class HighlightResource:
    def __init__(self, highlights: list[Highlight]) -> None:
        self.highlights = highlights
        self.calls: list[dict[str, object]] = []

    async def iter(self, **kwargs: object) -> AsyncIterator[Highlight]:
        self.calls.append(kwargs)
        for highlight in self.highlights:
            yield highlight


class BookResource:
    async def get(self, book_id: int) -> Book:
        assert book_id == 42
        return Book(id=42, title="The Book")


@pytest.mark.asyncio
async def test_custom_digest_owns_filtering_and_date_grouping() -> None:
    now = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)
    highlights = [
        Highlight(id=1, text="Known", book_id=42, highlighted_at=now),
        Highlight(id=2, text="Unknown", book_id=42),
    ]
    resource = HighlightResource(highlights)
    operations = DigestOperations(resource, BookResource())
    since = now - timedelta(days=3)

    digest = await operations.custom(
        since=since,
        book_id=42,
        group_by_book=False,
        group_by_date=True,
    )

    assert resource.calls == [{"updated_after": since, "book_id": 42}]
    assert digest.title == "Custom Digest"
    assert digest.grouping is DigestGrouping.DATE
    assert [(name, [item.id for item in items]) for name, items in digest.groups] == [
        ("Unknown Date", [2]),
        ("2025-01-02", [1]),
    ]


@pytest.mark.asyncio
async def test_book_digest_uses_book_title_and_disables_grouping() -> None:
    resource = HighlightResource([Highlight(id=1, text="Book highlight", book_id=42)])
    operations = DigestOperations(resource, BookResource())

    digest = await operations.book(42)

    assert resource.calls == [{"book_id": 42}]
    assert digest.title == "Highlights from: The Book"
    assert digest.grouping is DigestGrouping.NONE
    assert digest.groups == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "days"), [("daily", 1), ("weekly", 7)])
async def test_relative_digests_select_the_expected_time_window(method: str, days: int) -> None:
    resource = HighlightResource([])
    operations = DigestOperations(resource, BookResource())
    before = datetime.now(UTC) - timedelta(days=days, seconds=1)

    await getattr(operations, method)()

    updated_after = resource.calls[0]["updated_after"]
    assert isinstance(updated_after, datetime)
    assert before < updated_after <= datetime.now(UTC) - timedelta(days=days)
