"""Digest builder for creating highlight summaries."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from enum import Enum
from io import StringIO
from typing import TYPE_CHECKING

from readwise_sdk.v2.models import Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import ReadwiseClient


class DigestFormat(str, Enum):
    """Output format for digests."""

    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"
    TEXT = "text"


class DigestBuilder:
    """Builder for creating highlight digests in various formats."""

    def __init__(self, client: ReadwiseClient) -> None:
        """Initialize the digest builder.

        Args:
            client: The Readwise client.
        """
        self._client = client

    def _get_highlights_since(self, since: datetime) -> list[Highlight]:
        """Get highlights updated since a given time."""
        return list(self._client.v2.list_highlights(updated_after=since))

    def create_daily_digest(
        self,
        *,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
        group_by_book: bool = True,
    ) -> str:
        """Create a digest of highlights from the last 24 hours.

        Args:
            output_format: The output format.
            group_by_book: Whether to group highlights by book.

        Returns:
            Formatted digest string.
        """
        since = datetime.now(UTC) - timedelta(days=1)
        highlights = self._get_highlights_since(since)
        return self._format_digest(
            highlights,
            title="Daily Digest",
            output_format=output_format,
            group_by_book=group_by_book,
        )

    def create_weekly_digest(
        self,
        *,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
        group_by_book: bool = True,
    ) -> str:
        """Create a digest of highlights from the last 7 days.

        Args:
            output_format: The output format.
            group_by_book: Whether to group highlights by book.

        Returns:
            Formatted digest string.
        """
        since = datetime.now(UTC) - timedelta(days=7)
        highlights = self._get_highlights_since(since)
        return self._format_digest(
            highlights,
            title="Weekly Digest",
            output_format=output_format,
            group_by_book=group_by_book,
        )

    def create_book_digest(
        self,
        book_id: int,
        *,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
    ) -> str:
        """Create a digest of all highlights for a specific book.

        Args:
            book_id: The book ID.
            output_format: The output format.

        Returns:
            Formatted digest string.
        """
        book = self._client.v2.get_book(book_id)
        highlights = list(self._client.v2.list_highlights(book_id=book_id))
        return self._format_digest(
            highlights,
            title=f"Highlights from: {book.title}",
            output_format=output_format,
            group_by_book=False,
        )

    def create_custom_digest(
        self,
        *,
        since: datetime | None = None,
        book_id: int | None = None,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
        group_by_book: bool = True,
        group_by_date: bool = False,
    ) -> str:
        """Create a custom digest with specified filters.

        Args:
            since: Only include highlights updated after this time.
            book_id: Only include highlights from this book.
            output_format: The output format.
            group_by_book: Whether to group highlights by book.
            group_by_date: Whether to group highlights by date.

        Returns:
            Formatted digest string.
        """
        highlights = list(
            self._client.v2.list_highlights(
                updated_after=since,
                book_id=book_id,
            )
        )
        return self._format_digest(
            highlights,
            title="Custom Digest",
            output_format=output_format,
            group_by_book=group_by_book,
            group_by_date=group_by_date,
        )

    def _format_digest(
        self,
        highlights: list[Highlight],
        *,
        title: str,
        output_format: DigestFormat,
        group_by_book: bool = True,
        group_by_date: bool = False,
    ) -> str:
        """Format highlights into the specified output format.

        Args:
            highlights: List of highlights.
            title: Digest title.
            output_format: The output format.
            group_by_book: Whether to group by book.
            group_by_date: Whether to group by date.

        Returns:
            Formatted string.
        """
        if output_format == DigestFormat.JSON:
            return self._format_json(highlights, title)
        elif output_format == DigestFormat.CSV:
            return self._format_csv(highlights)
        elif output_format == DigestFormat.TEXT:
            return self._format_text(highlights, title, group_by_book, group_by_date)
        else:
            return self._format_markdown(highlights, title, group_by_book, group_by_date)

    def _format_markdown(
        self,
        highlights: list[Highlight],
        title: str,
        group_by_book: bool,
        group_by_date: bool,
    ) -> str:
        """Format as Markdown."""
        lines = [f"# {title}", "", f"*{len(highlights)} highlights*", ""]

        if group_by_date:
            groups = self._group_by_date(highlights)
            for date_str, date_highlights in sorted(groups.items(), reverse=True):
                lines.append(f"## {date_str}")
                lines.append("")
                for h in date_highlights:
                    lines.extend(self._format_highlight_md(h))
        elif group_by_book:
            groups = self._group_by_book(highlights)
            for book_title, book_highlights in groups.items():
                lines.append(f"## {book_title}")
                lines.append("")
                for h in book_highlights:
                    lines.extend(self._format_highlight_md(h, include_book=False))
        else:
            for h in highlights:
                lines.extend(self._format_highlight_md(h))

        return "\n".join(lines)

    def _format_highlight_md(
        self,
        highlight: Highlight,
        include_book: bool = True,
    ) -> list[str]:
        """Format a single highlight as Markdown."""
        lines = [f"> {highlight.text}", ""]

        metadata = []
        if include_book and highlight.book_id:
            metadata.append(f"Book ID: {highlight.book_id}")
        if highlight.location:
            metadata.append(f"Location: {highlight.location}")
        if highlight.note:
            metadata.append(f"Note: {highlight.note}")
        if highlight.tags:
            tag_names = [t.name for t in highlight.tags]
            metadata.append(f"Tags: {', '.join(tag_names)}")

        if metadata:
            lines.append(f"*{' | '.join(metadata)}*")
            lines.append("")

        return lines

    def _format_text(
        self,
        highlights: list[Highlight],
        title: str,
        group_by_book: bool,
        group_by_date: bool,
    ) -> str:
        """Format as plain text."""
        lines = [title, "=" * len(title), "", f"{len(highlights)} highlights", ""]

        if group_by_date:
            groups = self._group_by_date(highlights)
            for date_str, date_highlights in sorted(groups.items(), reverse=True):
                lines.append(date_str)
                lines.append("-" * len(date_str))
                for h in date_highlights:
                    lines.append(f"  {h.text}")
                    if h.note:
                        lines.append(f"  Note: {h.note}")
                    lines.append("")
        elif group_by_book:
            groups = self._group_by_book(highlights)
            for book_title, book_highlights in groups.items():
                lines.append(book_title)
                lines.append("-" * len(book_title))
                for h in book_highlights:
                    lines.append(f"  {h.text}")
                    if h.note:
                        lines.append(f"  Note: {h.note}")
                    lines.append("")
        else:
            for h in highlights:
                lines.append(h.text)
                if h.note:
                    lines.append(f"Note: {h.note}")
                lines.append("")

        return "\n".join(lines)

    def _format_json(self, highlights: list[Highlight], title: str) -> str:
        """Format as JSON."""
        data = {
            "title": title,
            "generated_at": datetime.now(UTC).isoformat(),
            "count": len(highlights),
            "highlights": [
                {
                    "id": h.id,
                    "text": h.text,
                    "note": h.note,
                    "location": h.location,
                    "book_id": h.book_id,
                    "highlighted_at": h.highlighted_at.isoformat() if h.highlighted_at else None,
                    "tags": [t.name for t in (h.tags or [])],
                }
                for h in highlights
            ],
        }
        return json.dumps(data, indent=2)

    def _format_csv(self, highlights: list[Highlight]) -> str:
        """Format as CSV."""
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "text", "note", "location", "book_id", "highlighted_at", "tags"])

        for h in highlights:
            tags = ",".join(t.name for t in (h.tags or []))
            writer.writerow(
                [
                    h.id,
                    h.text,
                    h.note or "",
                    h.location or "",
                    h.book_id or "",
                    h.highlighted_at.isoformat() if h.highlighted_at else "",
                    tags,
                ]
            )

        return output.getvalue()

    def _group_by_book(self, highlights: list[Highlight]) -> dict[str, list[Highlight]]:
        """Group highlights by book."""
        groups: dict[str, list[Highlight]] = {}
        for h in highlights:
            key = f"Book {h.book_id}" if h.book_id else "Unknown"
            if key not in groups:
                groups[key] = []
            groups[key].append(h)
        return groups

    def _group_by_date(self, highlights: list[Highlight]) -> dict[str, list[Highlight]]:
        """Group highlights by date."""
        groups: dict[str, list[Highlight]] = {}
        for h in highlights:
            if h.highlighted_at:
                key = h.highlighted_at.strftime("%Y-%m-%d")
            else:
                key = "Unknown Date"
            if key not in groups:
                groups[key] = []
            groups[key].append(h)
        return groups
