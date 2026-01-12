"""Readwise API v2 client implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.v2.models import (
    Book,
    BookCategory,
    DailyReview,
    ExportBook,
    Highlight,
    HighlightCreate,
    HighlightUpdate,
    Tag,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class ReadwiseV2Client:
    """Client for Readwise API v2 (highlights, books, tags)."""

    def __init__(self, base_client: ReadwiseClient) -> None:
        """Initialize the v2 client.

        Args:
            base_client: The base HTTP client for making requests.
        """
        self._client = base_client

    # ==================== Highlights ====================

    def list_highlights(
        self,
        *,
        page_size: int = 100,
        book_id: int | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        highlighted_after: datetime | None = None,
        highlighted_before: datetime | None = None,
    ) -> Iterator[Highlight]:
        """List all highlights with optional filtering.

        Args:
            page_size: Number of results per page (max 1000).
            book_id: Filter highlights by book ID.
            updated_after: Only return highlights updated after this datetime.
            updated_before: Only return highlights updated before this datetime.
            highlighted_after: Only return highlights created after this datetime.
            highlighted_before: Only return highlights created before this datetime.

        Yields:
            Highlight objects.
        """
        params: dict[str, Any] = {"page_size": min(page_size, 1000)}

        if book_id is not None:
            params["book_id"] = book_id
        if updated_after:
            params["updated__gt"] = updated_after.isoformat()
        if updated_before:
            params["updated__lt"] = updated_before.isoformat()
        if highlighted_after:
            params["highlighted_at__gt"] = highlighted_after.isoformat()
        if highlighted_before:
            params["highlighted_at__lt"] = highlighted_before.isoformat()

        for item in self._client.paginate(
            f"{READWISE_API_V2_BASE}/highlights/",
            params=params,
        ):
            yield Highlight.model_validate(item)

    def get_highlight(self, highlight_id: int) -> Highlight:
        """Get a single highlight by ID.

        Args:
            highlight_id: The highlight ID.

        Returns:
            The Highlight object.

        Raises:
            NotFoundError: If the highlight doesn't exist.
        """
        response = self._client.get(f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/")
        return Highlight.model_validate(response.json())

    def create_highlights(self, highlights: list[HighlightCreate]) -> list[int]:
        """Create one or more highlights.

        Args:
            highlights: List of highlights to create.

        Returns:
            List of created highlight IDs (from modified_highlights).
        """
        payload = {"highlights": [h.to_api_dict() for h in highlights]}
        response = self._client.post(f"{READWISE_API_V2_BASE}/highlights/", json=payload)
        data = response.json()

        # Extract modified highlight IDs from response
        highlight_ids: list[int] = []
        for book_data in data:
            modified = book_data.get("modified_highlights", [])
            highlight_ids.extend(modified)

        return highlight_ids

    def update_highlight(self, highlight_id: int, update: HighlightUpdate) -> Highlight:
        """Update an existing highlight.

        Args:
            highlight_id: The highlight ID to update.
            update: The fields to update.

        Returns:
            The updated Highlight object.

        Raises:
            NotFoundError: If the highlight doesn't exist.
        """
        response = self._client.patch(
            f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/",
            json=update.to_api_dict(),
        )
        return Highlight.model_validate(response.json())

    def delete_highlight(self, highlight_id: int) -> None:
        """Delete a highlight.

        Args:
            highlight_id: The highlight ID to delete.

        Raises:
            NotFoundError: If the highlight doesn't exist.
        """
        self._client.delete(f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/")

    # ==================== Books ====================

    def list_books(
        self,
        *,
        page_size: int = 100,
        category: BookCategory | None = None,
        source: str | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        last_highlight_after: datetime | None = None,
        last_highlight_before: datetime | None = None,
    ) -> Iterator[Book]:
        """List all books/sources with optional filtering.

        Args:
            page_size: Number of results per page (max 1000).
            category: Filter by category (books, articles, tweets, podcasts).
            source: Filter by source (kindle, instapaper, etc.).
            updated_after: Only return books updated after this datetime.
            updated_before: Only return books updated before this datetime.
            last_highlight_after: Only return books with highlights after this datetime.
            last_highlight_before: Only return books with highlights before this datetime.

        Yields:
            Book objects.
        """
        params: dict[str, Any] = {"page_size": min(page_size, 1000)}

        if category:
            params["category"] = category.value
        if source:
            params["source"] = source
        if updated_after:
            params["updated__gt"] = updated_after.isoformat()
        if updated_before:
            params["updated__lt"] = updated_before.isoformat()
        if last_highlight_after:
            params["last_highlight_at__gt"] = last_highlight_after.isoformat()
        if last_highlight_before:
            params["last_highlight_at__lt"] = last_highlight_before.isoformat()

        for item in self._client.paginate(
            f"{READWISE_API_V2_BASE}/books/",
            params=params,
        ):
            yield Book.model_validate(item)

    def get_book(self, book_id: int) -> Book:
        """Get a single book by ID.

        Args:
            book_id: The book ID.

        Returns:
            The Book object.

        Raises:
            NotFoundError: If the book doesn't exist.
        """
        response = self._client.get(f"{READWISE_API_V2_BASE}/books/{book_id}/")
        return Book.model_validate(response.json())

    # ==================== Highlight Tags ====================

    def list_highlight_tags(self, highlight_id: int) -> Iterator[Tag]:
        """List all tags for a highlight.

        Args:
            highlight_id: The highlight ID.

        Yields:
            Tag objects.

        Raises:
            NotFoundError: If the highlight doesn't exist.
        """
        for item in self._client.paginate(
            f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/tags/",
        ):
            yield Tag.model_validate(item)

    def create_highlight_tag(self, highlight_id: int, name: str) -> Tag:
        """Add a tag to a highlight.

        Args:
            highlight_id: The highlight ID.
            name: The tag name (max 127 chars).

        Returns:
            The created Tag object.

        Raises:
            NotFoundError: If the highlight doesn't exist.
        """
        response = self._client.post(
            f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/tags/",
            json={"name": name[:127]},
        )
        return Tag.model_validate(response.json())

    def update_highlight_tag(self, highlight_id: int, tag_id: int, name: str) -> Tag:
        """Update a tag on a highlight.

        Args:
            highlight_id: The highlight ID.
            tag_id: The tag ID.
            name: The new tag name.

        Returns:
            The updated Tag object.

        Raises:
            NotFoundError: If the highlight or tag doesn't exist.
        """
        response = self._client.patch(
            f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/tags/{tag_id}/",
            json={"name": name[:127]},
        )
        return Tag.model_validate(response.json())

    def delete_highlight_tag(self, highlight_id: int, tag_id: int) -> None:
        """Remove a tag from a highlight.

        Args:
            highlight_id: The highlight ID.
            tag_id: The tag ID.

        Raises:
            NotFoundError: If the highlight or tag doesn't exist.
        """
        self._client.delete(f"{READWISE_API_V2_BASE}/highlights/{highlight_id}/tags/{tag_id}/")

    # ==================== Book Tags ====================

    def list_book_tags(self, book_id: int) -> Iterator[Tag]:
        """List all tags for a book.

        Args:
            book_id: The book ID.

        Yields:
            Tag objects.

        Raises:
            NotFoundError: If the book doesn't exist.
        """
        for item in self._client.paginate(
            f"{READWISE_API_V2_BASE}/books/{book_id}/tags/",
        ):
            yield Tag.model_validate(item)

    def create_book_tag(self, book_id: int, name: str) -> Tag:
        """Add a tag to a book.

        Args:
            book_id: The book ID.
            name: The tag name (max 512 chars).

        Returns:
            The created Tag object.

        Raises:
            NotFoundError: If the book doesn't exist.
        """
        response = self._client.post(
            f"{READWISE_API_V2_BASE}/books/{book_id}/tags/",
            json={"name": name[:512]},
        )
        return Tag.model_validate(response.json())

    def update_book_tag(self, book_id: int, tag_id: int, name: str) -> Tag:
        """Update a tag on a book.

        Args:
            book_id: The book ID.
            tag_id: The tag ID.
            name: The new tag name.

        Returns:
            The updated Tag object.

        Raises:
            NotFoundError: If the book or tag doesn't exist.
        """
        response = self._client.patch(
            f"{READWISE_API_V2_BASE}/books/{book_id}/tags/{tag_id}/",
            json={"name": name[:512]},
        )
        return Tag.model_validate(response.json())

    def delete_book_tag(self, book_id: int, tag_id: int) -> None:
        """Remove a tag from a book.

        Args:
            book_id: The book ID.
            tag_id: The tag ID.

        Raises:
            NotFoundError: If the book or tag doesn't exist.
        """
        self._client.delete(f"{READWISE_API_V2_BASE}/books/{book_id}/tags/{tag_id}/")

    # ==================== Export ====================

    def export_highlights(
        self,
        *,
        updated_after: datetime | None = None,
        book_ids: list[int] | None = None,
        include_deleted: bool = False,
    ) -> Iterator[ExportBook]:
        """Export highlights using the export endpoint.

        This endpoint returns books with their highlights nested, which is more
        efficient for bulk operations.

        Args:
            updated_after: Only return highlights updated after this datetime.
            book_ids: Only return highlights from these books.
            include_deleted: Whether to include deleted highlights.

        Yields:
            ExportBook objects containing nested highlights.
        """
        params: dict[str, Any] = {}

        if updated_after:
            params["updatedAfter"] = updated_after.isoformat()
        if book_ids:
            params["ids"] = ",".join(str(bid) for bid in book_ids)
        if include_deleted:
            params["includeDeleted"] = "true"

        for item in self._client.paginate(
            f"{READWISE_API_V2_BASE}/export/",
            params=params,
            cursor_key="nextPageCursor",
        ):
            yield ExportBook.model_validate(item)

    # ==================== Daily Review ====================

    def get_daily_review(self) -> DailyReview:
        """Get the current daily review.

        Returns:
            The DailyReview object with selected highlights.
        """
        response = self._client.get(f"{READWISE_API_V2_BASE}/review/")
        return DailyReview.model_validate(response.json())
