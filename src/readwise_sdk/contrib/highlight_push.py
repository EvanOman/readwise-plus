"""Simplified interface for pushing highlights to Readwise.

Designed for highlight_helper and similar projects that need to sync
user-created highlights TO Readwise.

Example:
    from readwise_sdk import ReadwiseClient
    from readwise_sdk.contrib import HighlightPusher, SimpleHighlight

    client = ReadwiseClient()
    pusher = HighlightPusher(client)

    # Push a single highlight
    result = pusher.push(
        text="This is my highlight",
        title="Article Title",
        author="John Doe",
        note="My note about this",
    )
    print(f"Created highlight {result.highlight_id}")

    # Push multiple highlights
    highlights = [
        SimpleHighlight(text="First highlight", title="Book 1"),
        SimpleHighlight(text="Second highlight", title="Book 2"),
    ]
    results = pusher.push_batch(highlights)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk._utils import truncate_string
from readwise_sdk.v2.models import BookCategory, Highlight, HighlightCreate, HighlightUpdate

if TYPE_CHECKING:
    from readwise_sdk.client import AsyncReadwiseClient, ReadwiseClient

# Readwise field limits
MAX_TEXT_LENGTH = 8191
MAX_NOTE_LENGTH = 8191
MAX_TITLE_LENGTH = 511
MAX_AUTHOR_LENGTH = 1024


@dataclass
class SimpleHighlight:
    """A simplified highlight for pushing to Readwise."""

    text: str
    title: str
    author: str | None = None
    source_url: str | None = None
    source_type: str = "readwise_sdk"
    category: BookCategory | None = None
    note: str | None = None
    location: int | None = None
    location_type: str | None = None
    highlighted_at: datetime | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class PushResult:
    """Result of pushing a highlight to Readwise."""

    success: bool
    highlight_id: int | None = None
    book_id: int | None = None
    error: str | None = None
    original: SimpleHighlight | None = None
    was_truncated: bool = False


@dataclass
class UpdateResult:
    """Result of updating a highlight in Readwise."""

    success: bool
    highlight_id: int
    highlight: Highlight | None = None
    error: str | None = None
    was_truncated: bool = False


@dataclass
class DeleteResult:
    """Result of deleting a highlight from Readwise."""

    success: bool
    highlight_id: int
    error: str | None = None


def _to_create_request(
    highlight: SimpleHighlight, auto_truncate: bool
) -> tuple[HighlightCreate, bool]:
    """Convert SimpleHighlight to HighlightCreate, optionally truncating.

    Args:
        highlight: The highlight to convert.
        auto_truncate: Whether to truncate fields to API limits.

    Returns:
        Tuple of (HighlightCreate, was_truncated).
    """
    was_truncated = False

    text = highlight.text
    note = highlight.note
    title = highlight.title
    author = highlight.author

    if auto_truncate:
        text, t1 = truncate_string(text, MAX_TEXT_LENGTH)
        note, t2 = truncate_string(note, MAX_NOTE_LENGTH)
        title, t3 = truncate_string(title, MAX_TITLE_LENGTH)
        author, t4 = truncate_string(author, MAX_AUTHOR_LENGTH)
        was_truncated = any([t1, t2, t3, t4])
        # Text must not be None after truncation
        if text is None:
            text = ""

    return (
        HighlightCreate(
            text=text,
            title=title,
            author=author,
            source_url=highlight.source_url,
            source_type=highlight.source_type,
            category=highlight.category,
            note=note,
            location=highlight.location,
            location_type=highlight.location_type,
            highlighted_at=highlight.highlighted_at,
        ),
        was_truncated,
    )


def _to_update_request(
    text: str | None,
    note: str | None,
    location: int | None,
    location_type: str | None,
    auto_truncate: bool,
) -> tuple[HighlightUpdate, bool]:
    """Create HighlightUpdate, optionally truncating text fields.

    Args:
        text: New highlight text.
        note: New note.
        location: New location.
        location_type: New location type.
        auto_truncate: Whether to truncate fields to API limits.

    Returns:
        Tuple of (HighlightUpdate, was_truncated).
    """
    was_truncated = False

    if auto_truncate:
        if text is not None:
            text, t1 = truncate_string(text, MAX_TEXT_LENGTH)
            was_truncated = was_truncated or t1
        if note is not None:
            note, t2 = truncate_string(note, MAX_NOTE_LENGTH)
            was_truncated = was_truncated or t2

    return (
        HighlightUpdate(
            text=text,
            note=note,
            location=location,
            location_type=location_type,
        ),
        was_truncated,
    )


class HighlightPusher:
    """Simplified interface for pushing highlights to Readwise.

    Provides:
    - Automatic field truncation to Readwise limits
    - Batch operations with individual error handling
    - Simple dataclass-based input
    """

    def __init__(
        self,
        client: ReadwiseClient,
        *,
        auto_truncate: bool = True,
    ) -> None:
        """Initialize the highlight pusher.

        Args:
            client: The Readwise client.
            auto_truncate: Automatically truncate fields to Readwise limits.
        """
        self._client = client
        self._auto_truncate = auto_truncate

    def push(
        self,
        text: str,
        title: str,
        *,
        author: str | None = None,
        source_url: str | None = None,
        source_type: str = "readwise_sdk",
        category: BookCategory | None = None,
        note: str | None = None,
        location: int | None = None,
        highlighted_at: datetime | None = None,
        tags: list[str] | None = None,
    ) -> PushResult:
        """Push a single highlight to Readwise.

        Args:
            text: The highlight text.
            title: Title of the source (book/article name).
            author: Author of the source.
            source_url: URL of the source.
            source_type: Type identifier for the source.
            category: Category (articles, books, tweets, etc.). Defaults to None
                to let the Readwise API decide.
            note: Note attached to the highlight.
            location: Location in the source (page number, etc.).
            highlighted_at: When the highlight was made.
            tags: Tags to apply to the highlight.

        Returns:
            PushResult with success status and IDs.
        """
        highlight = SimpleHighlight(
            text=text,
            title=title,
            author=author,
            source_url=source_url,
            source_type=source_type,
            category=category,
            note=note,
            location=location,
            highlighted_at=highlighted_at,
            tags=tags or [],
        )
        return self.push_highlight(highlight)

    def push_highlight(self, highlight: SimpleHighlight) -> PushResult:
        """Push a SimpleHighlight to Readwise.

        Args:
            highlight: The highlight to push.

        Returns:
            PushResult with success status and IDs.
        """
        results = self.push_batch([highlight])
        return results[0]

    def push_batch(self, highlights: list[SimpleHighlight]) -> list[PushResult]:
        """Push multiple highlights to Readwise.

        Each highlight is processed independently - failures don't affect others.

        Args:
            highlights: List of highlights to push.

        Returns:
            List of PushResults in the same order as input.
        """
        if not highlights:
            return []

        # Convert to create requests
        create_requests = []
        truncation_flags = []
        for h in highlights:
            req, was_truncated = _to_create_request(h, self._auto_truncate)
            create_requests.append(req)
            truncation_flags.append(was_truncated)

        # Push to API
        results: list[PushResult] = []
        try:
            # create_highlights returns list[int] (highlight IDs)
            highlight_ids = self._client.v2.create_highlights(create_requests)

            # Map results back to highlights
            for i, h in enumerate(highlights):
                if i < len(highlight_ids):
                    highlight_id = highlight_ids[i]
                    results.append(
                        PushResult(
                            success=True,
                            highlight_id=highlight_id,
                            book_id=None,  # Not returned by API
                            original=h,
                            was_truncated=truncation_flags[i],
                        )
                    )
                else:
                    results.append(
                        PushResult(
                            success=False,
                            error="No API result returned",
                            original=h,
                            was_truncated=truncation_flags[i],
                        )
                    )
        except Exception as e:
            # If batch fails, mark all as failed
            for i, h in enumerate(highlights):
                results.append(
                    PushResult(
                        success=False,
                        error=str(e),
                        original=h,
                        was_truncated=truncation_flags[i],
                    )
                )

        return results

    def validate_token(self) -> bool:
        """Validate the API token.

        Returns:
            True if the token is valid.
        """
        return self._client.validate_token()

    def update(
        self,
        highlight_id: int,
        *,
        text: str | None = None,
        note: str | None = None,
        location: int | None = None,
        location_type: str | None = None,
    ) -> UpdateResult:
        """Update an existing highlight.

        Args:
            highlight_id: The ID of the highlight to update.
            text: New highlight text.
            note: New note.
            location: New location in the source.
            location_type: Type of location (e.g., "page").

        Returns:
            UpdateResult with success status and updated highlight.
        """
        results = self.update_batch([(highlight_id, text, note, location, location_type)])
        return results[0]

    def update_batch(
        self,
        updates: list[tuple[int, str | None, str | None, int | None, str | None]],
    ) -> list[UpdateResult]:
        """Update multiple highlights.

        Args:
            updates: List of tuples (highlight_id, text, note, location, location_type).
                     Pass None for fields you don't want to update.

        Returns:
            List of UpdateResults in the same order as input.
        """
        results: list[UpdateResult] = []

        for highlight_id, text, note, location, location_type in updates:
            try:
                update_req, was_truncated = _to_update_request(
                    text, note, location, location_type, self._auto_truncate
                )
                highlight = self._client.v2.update_highlight(highlight_id, update_req)
                results.append(
                    UpdateResult(
                        success=True,
                        highlight_id=highlight_id,
                        highlight=highlight,
                        was_truncated=was_truncated,
                    )
                )
            except Exception as e:
                results.append(
                    UpdateResult(
                        success=False,
                        highlight_id=highlight_id,
                        error=str(e),
                    )
                )

        return results

    def delete(self, highlight_id: int) -> DeleteResult:
        """Delete a highlight.

        Args:
            highlight_id: The ID of the highlight to delete.

        Returns:
            DeleteResult with success status.
        """
        results = self.delete_batch([highlight_id])
        return results[0]

    def delete_batch(self, highlight_ids: list[int]) -> list[DeleteResult]:
        """Delete multiple highlights.

        Args:
            highlight_ids: List of highlight IDs to delete.

        Returns:
            List of DeleteResults in the same order as input.
        """
        results: list[DeleteResult] = []

        for highlight_id in highlight_ids:
            try:
                self._client.v2.delete_highlight(highlight_id)
                results.append(
                    DeleteResult(
                        success=True,
                        highlight_id=highlight_id,
                    )
                )
            except Exception as e:
                results.append(
                    DeleteResult(
                        success=False,
                        highlight_id=highlight_id,
                        error=str(e),
                    )
                )

        return results


class AsyncHighlightPusher:
    """Async interface for pushing highlights to Readwise.

    Provides the same functionality as HighlightPusher but with async/await
    support for use with async frameworks like FastAPI or aiohttp.

    Example:
        from readwise_sdk import AsyncReadwiseClient
        from readwise_sdk.contrib import AsyncHighlightPusher

        async with AsyncReadwiseClient() as client:
            pusher = AsyncHighlightPusher(client)
            result = await pusher.push(
                text="This is my highlight",
                title="Article Title",
            )
    """

    def __init__(
        self,
        client: AsyncReadwiseClient,
        *,
        auto_truncate: bool = True,
    ) -> None:
        """Initialize the async highlight pusher.

        Args:
            client: The async Readwise client.
            auto_truncate: Automatically truncate fields to Readwise limits.
        """
        self._client = client
        self._auto_truncate = auto_truncate

    async def push(
        self,
        text: str,
        title: str,
        *,
        author: str | None = None,
        source_url: str | None = None,
        source_type: str = "readwise_sdk",
        category: BookCategory | None = None,
        note: str | None = None,
        location: int | None = None,
        highlighted_at: datetime | None = None,
        tags: list[str] | None = None,
    ) -> PushResult:
        """Push a single highlight to Readwise.

        Args:
            text: The highlight text.
            title: Title of the source (book/article name).
            author: Author of the source.
            source_url: URL of the source.
            source_type: Type identifier for the source.
            category: Category (articles, books, tweets, etc.). Defaults to None
                to let the Readwise API decide.
            note: Note attached to the highlight.
            location: Location in the source (page number, etc.).
            highlighted_at: When the highlight was made.
            tags: Tags to apply to the highlight.

        Returns:
            PushResult with success status and IDs.
        """
        highlight = SimpleHighlight(
            text=text,
            title=title,
            author=author,
            source_url=source_url,
            source_type=source_type,
            category=category,
            note=note,
            location=location,
            highlighted_at=highlighted_at,
            tags=tags or [],
        )
        return await self.push_highlight(highlight)

    async def push_highlight(self, highlight: SimpleHighlight) -> PushResult:
        """Push a SimpleHighlight to Readwise.

        Args:
            highlight: The highlight to push.

        Returns:
            PushResult with success status and IDs.
        """
        results = await self.push_batch([highlight])
        return results[0]

    async def push_batch(self, highlights: list[SimpleHighlight]) -> list[PushResult]:
        """Push multiple highlights to Readwise.

        Each highlight is processed independently - failures don't affect others.

        Args:
            highlights: List of highlights to push.

        Returns:
            List of PushResults in the same order as input.
        """
        if not highlights:
            return []

        # Convert to create requests
        create_requests = []
        truncation_flags = []
        for h in highlights:
            req, was_truncated = _to_create_request(h, self._auto_truncate)
            create_requests.append(req)
            truncation_flags.append(was_truncated)

        # Push to API
        results: list[PushResult] = []
        try:
            highlight_ids = await self._client.v2.create_highlights(create_requests)

            for i, h in enumerate(highlights):
                if i < len(highlight_ids):
                    highlight_id = highlight_ids[i]
                    results.append(
                        PushResult(
                            success=True,
                            highlight_id=highlight_id,
                            book_id=None,
                            original=h,
                            was_truncated=truncation_flags[i],
                        )
                    )
                else:
                    results.append(
                        PushResult(
                            success=False,
                            error="No API result returned",
                            original=h,
                            was_truncated=truncation_flags[i],
                        )
                    )
        except Exception as e:
            for i, h in enumerate(highlights):
                results.append(
                    PushResult(
                        success=False,
                        error=str(e),
                        original=h,
                        was_truncated=truncation_flags[i],
                    )
                )

        return results

    async def validate_token(self) -> bool:
        """Validate the API token.

        Returns:
            True if the token is valid.
        """
        return await self._client.validate_token()

    async def update(
        self,
        highlight_id: int,
        *,
        text: str | None = None,
        note: str | None = None,
        location: int | None = None,
        location_type: str | None = None,
    ) -> UpdateResult:
        """Update an existing highlight.

        Args:
            highlight_id: The ID of the highlight to update.
            text: New highlight text.
            note: New note.
            location: New location in the source.
            location_type: Type of location (e.g., "page").

        Returns:
            UpdateResult with success status and updated highlight.
        """
        results = await self.update_batch([(highlight_id, text, note, location, location_type)])
        return results[0]

    async def update_batch(
        self,
        updates: list[tuple[int, str | None, str | None, int | None, str | None]],
    ) -> list[UpdateResult]:
        """Update multiple highlights.

        Args:
            updates: List of tuples (highlight_id, text, note, location, location_type).
                     Pass None for fields you don't want to update.

        Returns:
            List of UpdateResults in the same order as input.
        """
        results: list[UpdateResult] = []

        for highlight_id, text, note, location, location_type in updates:
            try:
                update_req, was_truncated = _to_update_request(
                    text, note, location, location_type, self._auto_truncate
                )
                highlight = await self._client.v2.update_highlight(highlight_id, update_req)
                results.append(
                    UpdateResult(
                        success=True,
                        highlight_id=highlight_id,
                        highlight=highlight,
                        was_truncated=was_truncated,
                    )
                )
            except Exception as e:
                results.append(
                    UpdateResult(
                        success=False,
                        highlight_id=highlight_id,
                        error=str(e),
                    )
                )

        return results

    async def delete(self, highlight_id: int) -> DeleteResult:
        """Delete a highlight.

        Args:
            highlight_id: The ID of the highlight to delete.

        Returns:
            DeleteResult with success status.
        """
        results = await self.delete_batch([highlight_id])
        return results[0]

    async def delete_batch(self, highlight_ids: list[int]) -> list[DeleteResult]:
        """Delete multiple highlights.

        Args:
            highlight_ids: List of highlight IDs to delete.

        Returns:
            List of DeleteResults in the same order as input.
        """
        results: list[DeleteResult] = []

        for highlight_id in highlight_ids:
            try:
                await self._client.v2.delete_highlight(highlight_id)
                results.append(
                    DeleteResult(
                        success=True,
                        highlight_id=highlight_id,
                    )
                )
            except Exception as e:
                results.append(
                    DeleteResult(
                        success=False,
                        highlight_id=highlight_id,
                        error=str(e),
                    )
                )

        return results
