"""Tests for operation result and summary models."""

from datetime import UTC, datetime

from readwise_sdk.models.results import (
    BookSummary,
    BulkResult,
    DocumentSearchResult,
    DocumentSummary,
    HighlightSummary,
    OperationFailure,
    SyncCheckpoint,
    SyncResult,
)
from readwise_sdk.v2.models import Book, BookCategory, Highlight, HighlightColor
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation


def test_summary_models_hold_shared_adapter_projections() -> None:
    """Summary models declare the semantic fields shared by CLI and MCP output."""
    timestamp = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)

    document = DocumentSummary(
        id="doc-1",
        title="An article",
        author="An Author",
        url="https://example.com/article",
        category=DocumentCategory.ARTICLE,
        location=DocumentLocation.LATER,
        tags=("python", "sdk"),
        word_count=1200,
        reading_progress=0.25,
        site_name="Example",
        published_date=timestamp,
        saved_at=timestamp,
    )
    highlight = HighlightSummary(
        id=1,
        text="A useful passage",
        note="Remember this",
        book_id=2,
        color=HighlightColor.YELLOW,
        location=10,
        highlighted_at=timestamp,
        tags=("favorite",),
    )
    book = BookSummary(
        id=2,
        title="A Book",
        author="An Author",
        category=BookCategory.BOOKS,
        source="kindle",
        num_highlights=4,
        source_url="https://example.com/book",
        cover_image_url="https://example.com/cover.jpg",
        last_highlight_at=timestamp,
    )

    assert document.tags == ("python", "sdk")
    assert document.category is DocumentCategory.ARTICLE
    assert highlight.tags == ("favorite",)
    assert highlight.color is HighlightColor.YELLOW
    assert book.num_highlights == 4
    assert book.category is BookCategory.BOOKS


def test_document_search_result_reports_truncation() -> None:
    """Document search returns declared summaries plus a truncation signal."""
    summary = DocumentSummary(id="doc-1", url="https://example.com")

    result = DocumentSearchResult(items=[summary], truncated=True)

    assert result.items == [summary]
    assert result.truncated is True


def test_bulk_result_keeps_successes_and_original_failures() -> None:
    """Bulk failures identify their input and retain the original exception."""
    error = RuntimeError("archive failed")
    failure = OperationFailure(item="doc-2", error=error)

    result = BulkResult[str](succeeded=["doc-1"], failures=[failure])

    assert result.succeeded == ["doc-1"]
    assert result.failures == [failure]
    assert result.failures[0].error is error
    assert result.failures[0].message == "archive failed"


def test_sync_result_carries_data_and_unified_checkpoint() -> None:
    """A sync result returns all resource data with the checkpoint that follows it."""
    timestamp = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)
    checkpoint = SyncCheckpoint(
        last_highlight_sync=timestamp,
        last_book_sync=timestamp,
        last_document_sync=timestamp,
        last_sync_time=timestamp,
    )
    highlight = Highlight(id=1, text="Passage")
    book = Book(id=2, title="Book")
    document = Document(id="doc-1", url="https://example.com")

    result = SyncResult(
        highlights=[highlight],
        books=[book],
        documents=[document],
        checkpoint=checkpoint,
    )

    assert result.highlights == [highlight]
    assert result.books == [book]
    assert result.documents == [document]
    assert result.checkpoint is checkpoint
    assert result.is_empty is False


def test_sync_result_defaults_to_empty_collections() -> None:
    """An empty sync has independent resource lists and an empty checkpoint."""
    first = SyncResult()
    second = SyncResult()

    first.highlights.append(Highlight(id=1, text="Passage"))

    assert second.highlights == []
    assert second.is_empty is True
    assert second.checkpoint == SyncCheckpoint()
