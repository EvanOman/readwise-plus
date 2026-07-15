"""Markdown digest presentation."""

from __future__ import annotations

from readwise_sdk.operations.digests import DigestData, DigestGrouping
from readwise_sdk.v2.models import Highlight


def _format_highlight(highlight: Highlight, *, include_book: bool = True) -> list[str]:
    lines = [f"> {highlight.text}", ""]
    metadata: list[str] = []
    if include_book and highlight.book_id:
        metadata.append(f"Book ID: {highlight.book_id}")
    if highlight.location:
        metadata.append(f"Location: {highlight.location}")
    if highlight.note:
        metadata.append(f"Note: {highlight.note}")
    if highlight.tags:
        metadata.append(f"Tags: {', '.join(tag.name for tag in highlight.tags)}")
    if metadata:
        lines.extend([f"*{' | '.join(metadata)}*", ""])
    return lines


def render(digest: DigestData) -> str:
    """Render digest data using the legacy Markdown contract."""
    lines = [f"# {digest.title}", "", f"*{len(digest.highlights)} highlights*", ""]
    if digest.grouping is DigestGrouping.DATE:
        for name, highlights in digest.groups:
            lines.extend([f"## {name}", ""])
            for highlight in highlights:
                lines.extend(_format_highlight(highlight))
    elif digest.grouping is DigestGrouping.BOOK:
        for name, highlights in digest.groups:
            lines.extend([f"## {name}", ""])
            for highlight in highlights:
                lines.extend(_format_highlight(highlight, include_book=False))
    else:
        for highlight in digest.highlights:
            lines.extend(_format_highlight(highlight))
    return "\n".join(lines)


__all__ = ["render"]
