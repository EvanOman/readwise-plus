"""Compatibility shim for the legacy digest builder."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk.operations.digests import SyncDigestOperations, build_digest
from readwise_sdk.presenters import DigestFormat, render_digest
from readwise_sdk.v2.models import Highlight

if TYPE_CHECKING:
    from readwise_sdk.client import ReadwiseClient


class DigestBuilder:
    """Legacy blocking wrapper over digest operations and presenters."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client
        self._operations = SyncDigestOperations(client.v2)

    def create_daily_digest(
        self,
        *,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
        group_by_book: bool = True,
    ) -> str:
        """Create a digest of highlights from the last 24 hours."""
        data = self._operations.daily(group_by_book=group_by_book)
        return render_digest(data, output_format)

    def create_weekly_digest(
        self,
        *,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
        group_by_book: bool = True,
    ) -> str:
        """Create a digest of highlights from the last seven days."""
        data = self._operations.weekly(group_by_book=group_by_book)
        return render_digest(data, output_format)

    def create_book_digest(
        self,
        book_id: int,
        *,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
    ) -> str:
        """Create a digest of all highlights for a specific book."""
        return render_digest(self._operations.book(book_id), output_format)

    def create_custom_digest(
        self,
        *,
        since: datetime | None = None,
        book_id: int | None = None,
        output_format: DigestFormat = DigestFormat.MARKDOWN,
        group_by_book: bool = True,
        group_by_date: bool = False,
    ) -> str:
        """Create a custom digest with specified filters and grouping."""
        data = self._operations.custom(
            since=since,
            book_id=book_id,
            group_by_book=group_by_book,
            group_by_date=group_by_date,
        )
        return render_digest(data, output_format)

    def _format_digest(
        self,
        highlights: list[Highlight],
        *,
        title: str,
        output_format: DigestFormat,
        group_by_book: bool = True,
        group_by_date: bool = False,
    ) -> str:
        """Preserve the formatter seam used by the existing highlights CLI."""
        data = build_digest(
            highlights,
            title=title,
            group_by_book_enabled=group_by_book,
            group_by_date_enabled=group_by_date,
        )
        return render_digest(data, output_format)


__all__ = ["DigestBuilder", "DigestFormat"]
