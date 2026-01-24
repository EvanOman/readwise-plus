"""Async versions of high-level manager classes.

These managers provide the same functionality as their synchronous counterparts
but use async/await for all I/O operations.

Example:
    async with AsyncReadwiseClient() as client:
        manager = AsyncHighlightManager(client)
        highlights = await manager.get_highlights_since(days=7)
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from readwise_sdk.managers.books import BookWithHighlights, ReadingStats
from readwise_sdk.managers.documents import InboxStats
from readwise_sdk.managers.sync import SyncResult, SyncState
from readwise_sdk.v2.models import Book, BookCategory, Highlight, HighlightCreate
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from readwise_sdk.client import AsyncReadwiseClient


class AsyncHighlightManager:
    """Async high-level operations for managing highlights."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        """Initialize the async highlight manager.

        Args:
            client: The async Readwise client.
        """
        self._client = client

    async def get_all_highlights(self) -> list[Highlight]:
        """Get all highlights, exhausting pagination.

        Returns:
            List of all highlights.
        """
        return [h async for h in self._client.v2.list_highlights()]

    async def get_highlights_since(
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
                since = datetime.now(timezone.utc) - timedelta(days=days)
            elif hours is not None:
                since = datetime.now(timezone.utc) - timedelta(hours=hours)
            else:
                raise ValueError("Must specify days, hours, or since")

        return [h async for h in self._client.v2.list_highlights(updated_after=since)]

    async def get_highlights_by_book(self, book_id: int) -> list[Highlight]:
        """Get all highlights for a specific book.

        Args:
            book_id: The book ID.

        Returns:
            List of highlights for the book.
        """
        return [h async for h in self._client.v2.list_highlights(book_id=book_id)]

    async def get_highlights_with_notes(self) -> list[Highlight]:
        """Get all highlights that have notes/annotations.

        Returns:
            List of highlights with notes.
        """
        return [h async for h in self._client.v2.list_highlights() if h.note]

    async def search_highlights(
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
        async for highlight in self._client.v2.list_highlights():
            text = highlight.text if case_sensitive else highlight.text.lower()
            note = (highlight.note or "") if case_sensitive else (highlight.note or "").lower()

            if query in text or query in note:
                results.append(highlight)

        return results

    async def filter_highlights(
        self,
        predicate: Callable[[Highlight], bool],
    ) -> AsyncIterator[Highlight]:
        """Filter highlights using a custom predicate.

        Args:
            predicate: A function that returns True for highlights to include.

        Yields:
            Highlights that match the predicate.
        """
        async for highlight in self._client.v2.list_highlights():
            if predicate(highlight):
                yield highlight

    async def bulk_tag(
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
                await self._client.v2.create_highlight_tag(hid, tag)
                results[hid] = True
            except Exception:
                results[hid] = False
        return results

    async def bulk_untag(
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
                tags = [t async for t in self._client.v2.list_highlight_tags(hid)]
                tag_obj = next((t for t in tags if t.name == tag), None)
                if tag_obj:
                    await self._client.v2.delete_highlight_tag(hid, tag_obj.id)
                results[hid] = True
            except Exception:
                results[hid] = False
        return results

    async def create_highlight(
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
        ids = await self._client.v2.create_highlights([highlight])
        return ids[0] if ids else 0

    async def get_highlight_count(self) -> int:
        """Get the total number of highlights.

        Returns:
            Total highlight count.
        """
        count = 0
        async for _ in self._client.v2.list_highlights():
            count += 1
        return count


class AsyncBookManager:
    """Async high-level operations for managing books."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        """Initialize the async book manager.

        Args:
            client: The async Readwise client.
        """
        self._client = client

    async def get_all_books(self) -> list[Book]:
        """Get all books, exhausting pagination.

        Returns:
            List of all books.
        """
        return [b async for b in self._client.v2.list_books()]

    async def get_books_by_category(self, category: BookCategory) -> list[Book]:
        """Get books filtered by category.

        Args:
            category: The category to filter by.

        Returns:
            List of books in the category.
        """
        return [b async for b in self._client.v2.list_books(category=category)]

    async def get_books_by_source(self, source: str) -> list[Book]:
        """Get books filtered by source.

        Args:
            source: The source to filter by (e.g., "kindle", "instapaper").

        Returns:
            List of books from the source.
        """
        return [b async for b in self._client.v2.list_books(source=source)]

    async def get_book_with_highlights(self, book_id: int) -> BookWithHighlights:
        """Get a book with all its highlights.

        Args:
            book_id: The book ID.

        Returns:
            BookWithHighlights containing the book and its highlights.
        """
        book = await self._client.v2.get_book(book_id)
        highlights = [h async for h in self._client.v2.list_highlights(book_id=book_id)]
        return BookWithHighlights(book=book, highlights=highlights)

    async def get_recent_books(
        self,
        *,
        days: int | None = None,
        limit: int | None = None,
    ) -> list[Book]:
        """Get recently updated books.

        Args:
            days: Only include books updated in the last N days.
            limit: Maximum number of books to return.

        Returns:
            List of recent books.
        """
        since = None
        if days is not None:
            since = datetime.now(timezone.utc) - timedelta(days=days)

        books = [b async for b in self._client.v2.list_books(updated_after=since)]

        books.sort(
            key=lambda b: b.last_highlight_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        if limit:
            books = books[:limit]

        return books

    async def get_reading_stats(self) -> ReadingStats:
        """Get aggregated reading statistics.

        Returns:
            ReadingStats with various aggregations.
        """
        books = await self.get_all_books()

        books_by_category: Counter[str] = Counter()
        highlights_by_category: Counter[str] = Counter()
        highlights_by_source: Counter[str] = Counter()

        for book in books:
            cat = book.category.value if book.category else "unknown"
            books_by_category[cat] += 1
            highlights_by_category[cat] += book.num_highlights

            source = book.source or "unknown"
            highlights_by_source[source] += book.num_highlights

        most_highlighted = sorted(
            [(b.title, b.num_highlights) for b in books],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        recent = await self.get_recent_books(days=30, limit=10)

        return ReadingStats(
            total_books=len(books),
            total_highlights=sum(b.num_highlights for b in books),
            books_by_category=dict(books_by_category),
            highlights_by_category=dict(highlights_by_category),
            highlights_by_source=dict(highlights_by_source),
            most_highlighted_books=most_highlighted,
            recent_books=recent,
        )

    async def search_books(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Book]:
        """Search books by title or author.

        Args:
            query: The search query.
            case_sensitive: Whether to perform case-sensitive search.

        Returns:
            List of matching books.
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        async for book in self._client.v2.list_books():
            title = book.title if case_sensitive else book.title.lower()
            author = (book.author or "") if case_sensitive else (book.author or "").lower()

            if query in title or query in author:
                results.append(book)

        return results

    async def get_book_count(self) -> int:
        """Get the total number of books.

        Returns:
            Total book count.
        """
        return len(await self.get_all_books())


class AsyncDocumentManager:
    """Async high-level operations for managing Reader documents."""

    def __init__(self, client: AsyncReadwiseClient) -> None:
        """Initialize the async document manager.

        Args:
            client: The async Readwise client.
        """
        self._client = client

    async def get_inbox(self) -> list[Document]:
        """Get all documents in the inbox.

        Returns:
            List of inbox documents.
        """
        return [d async for d in self._client.v3.get_inbox()]

    async def get_reading_list(self) -> list[Document]:
        """Get all documents in the reading list.

        Returns:
            List of reading list documents.
        """
        return [d async for d in self._client.v3.get_reading_list()]

    async def get_archive(self) -> list[Document]:
        """Get all archived documents.

        Returns:
            List of archived documents.
        """
        return [d async for d in self._client.v3.get_archive()]

    async def get_documents_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Document]:
        """Get documents updated since a given time.

        Args:
            days: Number of days to look back.
            hours: Number of hours to look back.
            since: Specific datetime to look back to.

        Returns:
            List of documents updated since the given time.
        """
        if since is None:
            if days is not None:
                since = datetime.now(timezone.utc) - timedelta(days=days)
            elif hours is not None:
                since = datetime.now(timezone.utc) - timedelta(hours=hours)
            else:
                raise ValueError("Must specify days, hours, or since")

        return [d async for d in self._client.v3.list_documents(updated_after=since)]

    async def move_to_later(self, document_id: str) -> None:
        """Move a document to the reading list.

        Args:
            document_id: The document ID.
        """
        await self._client.v3.move_to_later(document_id)

    async def archive(self, document_id: str) -> None:
        """Archive a document.

        Args:
            document_id: The document ID.
        """
        await self._client.v3.archive(document_id)

    async def move_to_inbox(self, document_id: str) -> None:
        """Move a document back to the inbox.

        Args:
            document_id: The document ID.
        """
        await self._client.v3.move_to_inbox(document_id)

    async def bulk_archive(self, document_ids: list[str]) -> dict[str, bool]:
        """Archive multiple documents.

        Args:
            document_ids: List of document IDs.

        Returns:
            Dict mapping document ID to success status.
        """
        results: dict[str, bool] = {}
        for doc_id in document_ids:
            try:
                await self._client.v3.archive(doc_id)
                results[doc_id] = True
            except Exception:
                results[doc_id] = False
        return results

    async def bulk_tag_documents(
        self,
        document_ids: list[str],
        tags: list[str],
    ) -> dict[str, bool]:
        """Set tags on multiple documents.

        Args:
            document_ids: List of document IDs.
            tags: Tags to set on all documents.

        Returns:
            Dict mapping document ID to success status.
        """
        results: dict[str, bool] = {}
        for doc_id in document_ids:
            try:
                await self._client.v3.tag_document(doc_id, tags)
                results[doc_id] = True
            except Exception:
                results[doc_id] = False
        return results

    async def filter_documents(
        self,
        predicate: Callable[[Document], bool],
        *,
        location: DocumentLocation | None = None,
    ) -> AsyncIterator[Document]:
        """Filter documents using a custom predicate.

        Args:
            predicate: A function that returns True for documents to include.
            location: Optional location to filter by first.

        Yields:
            Documents that match the predicate.
        """
        async for doc in self._client.v3.list_documents(location=location):
            if predicate(doc):
                yield doc

    async def search_documents(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        location: DocumentLocation | None = None,
    ) -> list[Document]:
        """Search documents by title, author, or summary.

        Args:
            query: The search query.
            case_sensitive: Whether to perform case-sensitive search.
            location: Optional location to filter by.

        Returns:
            List of matching documents.
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        async for doc in self._client.v3.list_documents(location=location):
            title = (doc.title or "") if case_sensitive else (doc.title or "").lower()
            author = (doc.author or "") if case_sensitive else (doc.author or "").lower()
            summary = (doc.summary or "") if case_sensitive else (doc.summary or "").lower()

            if query in title or query in author or query in summary:
                results.append(doc)

        return results

    async def get_inbox_stats(self) -> InboxStats:
        """Get statistics about the reading inbox.

        Returns:
            InboxStats with counts and oldest/newest items.
        """
        inbox = [d async for d in self._client.v3.get_inbox()]
        reading_list = [d async for d in self._client.v3.get_reading_list()]
        archive = [d async for d in self._client.v3.get_archive()]

        by_category: Counter[str] = Counter()
        for doc in inbox + reading_list:
            cat = doc.category.value if doc.category else "unknown"
            by_category[cat] += 1

        oldest = None
        newest = None
        if inbox:
            sorted_inbox = sorted(
                inbox,
                key=lambda d: d.created_at or datetime.min.replace(tzinfo=timezone.utc),
            )
            oldest = sorted_inbox[0]
            newest = sorted_inbox[-1]

        return InboxStats(
            inbox_count=len(inbox),
            reading_list_count=len(reading_list),
            archive_count=len(archive),
            total_count=len(inbox) + len(reading_list) + len(archive),
            by_category=dict(by_category),
            oldest_inbox_item=oldest,
            newest_inbox_item=newest,
        )

    async def get_documents_by_category(
        self,
        category: DocumentCategory,
    ) -> list[Document]:
        """Get all documents of a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of documents in the category.
        """
        return [d async for d in self._client.v3.list_documents(category=category)]

    async def get_unread_count(self) -> int:
        """Get the count of unread documents (inbox + reading list).

        Returns:
            Count of unread documents.
        """
        inbox = len([d async for d in self._client.v3.get_inbox()])
        reading_list = len([d async for d in self._client.v3.get_reading_list()])
        return inbox + reading_list


class AsyncSyncManager:
    """Async manager for syncing Readwise data with state persistence."""

    def __init__(
        self,
        client: AsyncReadwiseClient,
        *,
        state_file: Path | str | None = None,
    ) -> None:
        """Initialize the async sync manager.

        Args:
            client: The async Readwise client.
            state_file: Optional path to persist sync state.
        """
        self._client = client
        self._state_file = Path(state_file) if state_file else None
        self._state = self._load_state()
        self._callbacks: list[Callable[[SyncResult], None]] = []

    def _load_state(self) -> SyncState:
        """Load state from file if it exists."""
        if self._state_file and self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return SyncState.from_dict(data)
            except Exception:
                pass
        return SyncState()

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if self._state_file:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(self._state.to_dict(), indent=2))

    @property
    def state(self) -> SyncState:
        """Get the current sync state."""
        return self._state

    def on_sync(self, callback: Callable[[SyncResult], None]) -> None:
        """Register a callback for sync events.

        Args:
            callback: Function to call with sync results.
        """
        self._callbacks.append(callback)

    def _notify_callbacks(self, result: SyncResult) -> None:
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass

    async def full_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Perform a full sync of all data.

        Args:
            include_highlights: Whether to sync highlights.
            include_books: Whether to sync books.
            include_documents: Whether to sync documents.

        Returns:
            SyncResult with all synced data.
        """
        now = datetime.now(timezone.utc)
        result = SyncResult(sync_time=now)

        if include_highlights:
            result.highlights = [h async for h in self._client.v2.list_highlights()]
            self._state.last_highlight_sync = now

        if include_books:
            result.books = [b async for b in self._client.v2.list_books()]
            self._state.last_book_sync = now

        if include_documents:
            result.documents = [d async for d in self._client.v3.list_documents()]
            self._state.last_document_sync = now

        self._state.total_syncs += 1
        self._state.last_sync_time = now
        self._save_state()
        self._notify_callbacks(result)

        return result

    async def incremental_sync(
        self,
        *,
        include_highlights: bool = True,
        include_books: bool = True,
        include_documents: bool = True,
    ) -> SyncResult:
        """Perform an incremental sync since the last sync.

        Args:
            include_highlights: Whether to sync highlights.
            include_books: Whether to sync books.
            include_documents: Whether to sync documents.

        Returns:
            SyncResult with newly synced data.
        """
        now = datetime.now(timezone.utc)
        result = SyncResult(sync_time=now)

        if include_highlights:
            since = self._state.last_highlight_sync
            if since:
                result.highlights = [
                    h async for h in self._client.v2.list_highlights(updated_after=since)
                ]
            else:
                result.highlights = [h async for h in self._client.v2.list_highlights()]
            self._state.last_highlight_sync = now

        if include_books:
            since = self._state.last_book_sync
            if since:
                result.books = [b async for b in self._client.v2.list_books(updated_after=since)]
            else:
                result.books = [b async for b in self._client.v2.list_books()]
            self._state.last_book_sync = now

        if include_documents:
            since = self._state.last_document_sync
            if since:
                result.documents = [
                    d async for d in self._client.v3.list_documents(updated_after=since)
                ]
            else:
                result.documents = [d async for d in self._client.v3.list_documents()]
            self._state.last_document_sync = now

        self._state.total_syncs += 1
        self._state.last_sync_time = now
        self._save_state()
        self._notify_callbacks(result)

        return result

    async def sync_highlights_only(self) -> SyncResult:
        """Sync only highlights.

        Returns:
            SyncResult with synced highlights.
        """
        return await self.incremental_sync(include_books=False, include_documents=False)

    async def sync_documents_only(self) -> SyncResult:
        """Sync only documents.

        Returns:
            SyncResult with synced documents.
        """
        return await self.incremental_sync(include_highlights=False, include_books=False)

    def reset_state(self) -> None:
        """Reset the sync state (next sync will be full)."""
        self._state = SyncState()
        self._save_state()
