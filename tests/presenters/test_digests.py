"""Exact rendering contracts for digest presenters."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from readwise_sdk.operations.digests import DigestData, DigestGrouping
from readwise_sdk.presenters import DigestFormat, render_digest
from readwise_sdk.v2.models import Highlight, Tag


def _digest(grouping: DigestGrouping) -> DigestData:
    highlight = Highlight(
        id=1,
        text="A useful idea",
        note="Remember it",
        location=7,
        book_id=42,
        highlighted_at=datetime(2025, 1, 2, 3, 4, tzinfo=UTC),
        tags=[Tag(id=9, name="favorite")],
    )
    groups = [("Book 42", [highlight])] if grouping is DigestGrouping.BOOK else []
    return DigestData(
        title="Custom Digest",
        highlights=[highlight],
        grouping=grouping,
        groups=groups,
    )


def test_markdown_presenter_preserves_exact_grouped_output() -> None:
    assert render_digest(_digest(DigestGrouping.BOOK), DigestFormat.MARKDOWN) == (
        "# Custom Digest\n\n"
        "*1 highlights*\n\n"
        "## Book 42\n\n"
        "> A useful idea\n\n"
        "*Location: 7 | Note: Remember it | Tags: favorite*\n"
    )


def test_text_presenter_preserves_exact_ungrouped_output() -> None:
    assert render_digest(_digest(DigestGrouping.NONE), DigestFormat.TEXT) == (
        "Custom Digest\n=============\n\n1 highlights\n\nA useful idea\nNote: Remember it\n"
    )


def test_json_presenter_preserves_fields_and_values() -> None:
    data = json.loads(render_digest(_digest(DigestGrouping.NONE), DigestFormat.JSON))

    assert data["title"] == "Custom Digest"
    assert data["count"] == 1
    assert datetime.fromisoformat(data["generated_at"]).tzinfo is UTC
    assert data["highlights"] == [
        {
            "id": 1,
            "text": "A useful idea",
            "note": "Remember it",
            "location": 7,
            "book_id": 42,
            "highlighted_at": "2025-01-02T03:04:00+00:00",
            "tags": ["favorite"],
        }
    ]


def test_csv_presenter_preserves_exact_output() -> None:
    assert render_digest(_digest(DigestGrouping.NONE), DigestFormat.CSV) == (
        "id,text,note,location,book_id,highlighted_at,tags\r\n"
        "1,A useful idea,Remember it,7,42,2025-01-02T03:04:00+00:00,favorite\r\n"
    )
