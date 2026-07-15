"""Presentation helpers for the MCP wire protocol."""

from __future__ import annotations

import json
from typing import Any


def _doc_summary(doc: Any) -> dict[str, Any]:
    """Compact summary of a Document for listing results."""
    return {
        k: v
        for k, v in {
            "id": doc.id,
            "title": doc.title,
            "author": doc.author,
            "url": getattr(doc, "source_url", None) or doc.url,
            "category": doc.category.value if doc.category else None,
            "location": doc.location.value if doc.location else None,
            "tags": doc.tags or None,
            "word_count": doc.word_count,
            "reading_progress": doc.reading_progress,
            "site_name": doc.site_name,
            "published_date": doc.published_date.isoformat() if doc.published_date else None,
            "saved_at": doc.saved_at.isoformat() if doc.saved_at else None,
        }.items()
        if v is not None
    }


def _doc_full(doc: Any) -> dict[str, Any]:
    """Full document representation including content."""
    result = _doc_summary(doc)
    if doc.content:
        result["content"] = doc.content
    if doc.summary:
        result["summary"] = doc.summary
    if doc.notes:
        result["notes"] = doc.notes
    return result


def _highlight_summary(highlight: Any) -> dict[str, Any]:
    """Compact summary of a Highlight."""
    tags = None
    if highlight.tags:
        tags = [tag if isinstance(tag, str) else tag.name for tag in highlight.tags]
    return {
        k: v
        for k, v in {
            "id": highlight.id,
            "text": highlight.text,
            "note": highlight.note,
            "book_id": highlight.book_id,
            "color": highlight.color.value if highlight.color else None,
            "location": highlight.location,
            "highlighted_at": (
                highlight.highlighted_at.isoformat() if highlight.highlighted_at else None
            ),
            "tags": tags,
        }.items()
        if v is not None
    }


def _book_summary(book: Any) -> dict[str, Any]:
    """Compact summary of a Book."""
    return {
        k: v
        for k, v in {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "category": book.category.value if book.category else None,
            "source": book.source,
            "num_highlights": book.num_highlights,
            "source_url": book.source_url,
            "cover_image_url": book.cover_image_url,
            "last_highlight_at": (
                book.last_highlight_at.isoformat() if book.last_highlight_at else None
            ),
        }.items()
        if v is not None
    }


def _export_summary(book: Any) -> dict[str, Any]:
    """Compact exported-book representation with nested highlights."""
    book_data: dict[str, Any] = {
        "book_id": book.book_id,
        "title": book.title,
        "author": book.author,
        "category": book.category.value if book.category else None,
        "source": book.source,
        "source_url": book.source_url,
        "highlights": [_highlight_summary(highlight) for highlight in book.highlights],
    }
    return {key: value for key, value in book_data.items() if value is not None}


def _json_result(data: Any) -> str:
    """Serialize a result to a compact JSON string."""
    return json.dumps(data, ensure_ascii=False, default=str)


def _error_result(error: Exception | str) -> str:
    """Render an SDK or adapter error in the existing MCP envelope."""
    return _json_result({"error": str(error)})


def _document_not_found(document_id: str) -> str:
    """Render the existing quoted document-not-found message."""
    return _error_result(f"Document '{document_id}' not found.")


__all__ = [
    "_book_summary",
    "_doc_full",
    "_doc_summary",
    "_document_not_found",
    "_error_result",
    "_export_summary",
    "_highlight_summary",
    "_json_result",
]
