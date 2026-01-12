"""High-level highlight management operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from readwise_sdk.v2.models import Highlight, HighlightCreate

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from readwise_sdk.client import ReadwiseClient


class HighlightManager:
    """High-level operations for managing highlights."""

    def __init__(self, client: ReadwiseClient) -> None:
        """Initialize the highlight manager.

        Args:
            client: The Readwise client.
        """
        self._client = client

    def get_all_highlights(self) -> list[Highlight]:
        """Get all highlights, exhausting pagination.

        Returns:
            List of all highlights.
        """
        return list(self._client.v2.list_highlights())

    def get_highlights_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Highlight]:
        """Get highlights updated since a given time.

        Args:
            days: Number of days to look back.
            hours: Number of hours to look back.
            since: Specific datetime to look back to.

        Returns:
            List of highlights updated since the given time.
        """
        if since is None:
            if days is not None:
                since = datetime.now(UTC) - timedelta(days=days)
            elif hours is not None:
                since = datetime.now(UTC) - timedelta(hours=hours)
            else:
                raise ValueError("Must specify days, hours, or since")

        return list(self._client.v2.list_highlights(updated_after=since))

    def get_highlights_by_book(self, book_id: int) -> list[Highlight]:
        """Get all highlights for a specific book.

        Args:
            book_id: The book ID.

        Returns:
            List of highlights for the book.
        """
        return list(self._client.v2.list_highlights(book_id=book_id))

    def get_highlights_with_notes(self) -> list[Highlight]:
        """Get all highlights that have notes/annotations.

        Returns:
            List of highlights with notes.
        """
        return [h for h in self._client.v2.list_highlights() if h.note]

    def search_highlights(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Highlight]:
        """Search highlights by text content.

        Args:
            query: The search query.
            case_sensitive: Whether to perform case-sensitive search.

        Returns:
            List of matching highlights.
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        for highlight in self._client.v2.list_highlights():
            text = highlight.text if case_sensitive else highlight.text.lower()
            note = (highlight.note or "") if case_sensitive else (highlight.note or "").lower()

            if query in text or query in note:
                results.append(highlight)

        return results

    def filter_highlights(
        self,
        predicate: Callable[[Highlight], bool],
    ) -> Iterator[Highlight]:
        """Filter highlights using a custom predicate.

        Args:
            predicate: A function that returns True for highlights to include.

        Yields:
            Highlights that match the predicate.
        """
        for highlight in self._client.v2.list_highlights():
            if predicate(highlight):
                yield highlight

    def bulk_tag(
        self,
        highlight_ids: list[int],
        tag: str,
    ) -> dict[int, bool]:
        """Add a tag to multiple highlights.

        Args:
            highlight_ids: List of highlight IDs to tag.
            tag: The tag name to add.

        Returns:
            Dict mapping highlight ID to success status.
        """
        results: dict[int, bool] = {}
        for hid in highlight_ids:
            try:
                self._client.v2.create_highlight_tag(hid, tag)
                results[hid] = True
            except Exception:
                results[hid] = False
        return results

    def bulk_untag(
        self,
        highlight_ids: list[int],
        tag: str,
    ) -> dict[int, bool]:
        """Remove a tag from multiple highlights.

        Args:
            highlight_ids: List of highlight IDs.
            tag: The tag name to remove.

        Returns:
            Dict mapping highlight ID to success status.
        """
        results: dict[int, bool] = {}
        for hid in highlight_ids:
            try:
                # Find the tag ID first
                tags = list(self._client.v2.list_highlight_tags(hid))
                tag_obj = next((t for t in tags if t.name == tag), None)
                if tag_obj:
                    self._client.v2.delete_highlight_tag(hid, tag_obj.id)
                results[hid] = True
            except Exception:
                results[hid] = False
        return results

    def create_highlight(
        self,
        text: str,
        *,
        title: str | None = None,
        author: str | None = None,
        note: str | None = None,
        source_url: str | None = None,
    ) -> int:
        """Create a single highlight (convenience method).

        Args:
            text: The highlight text.
            title: The source title.
            author: The source author.
            note: An optional note/annotation.
            source_url: The source URL.

        Returns:
            The created highlight ID.
        """
        highlight = HighlightCreate(
            text=text,
            title=title,
            author=author,
            note=note,
            source_url=source_url,
        )
        ids = self._client.v2.create_highlights([highlight])
        return ids[0] if ids else 0

    def get_highlight_count(self) -> int:
        """Get the total number of highlights.

        Returns:
            Total highlight count.
        """
        count = 0
        for _ in self._client.v2.list_highlights():
            count += 1
        return count
