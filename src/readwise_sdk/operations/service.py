"""Container for canonical operation groups."""

from __future__ import annotations

from readwise_sdk.operations.books import BookHighlightsResource, BookOperations, BooksResource
from readwise_sdk.operations.digests import (
    DigestBooksResource,
    DigestHighlightsResource,
    DigestOperations,
)
from readwise_sdk.operations.documents import DocumentOperations, DocumentsResource
from readwise_sdk.operations.highlights import (
    ExportResource,
    HighlightOperations,
    HighlightsResource,
    HighlightTagsResource,
)
from readwise_sdk.operations.sync import (
    AsyncBooksResource as SyncBooksResource,
)
from readwise_sdk.operations.sync import (
    AsyncDocumentsResource as SyncDocumentsResource,
)
from readwise_sdk.operations.sync import (
    AsyncHighlightsResource as SyncHighlightsResource,
)
from readwise_sdk.operations.sync import SyncOperations
from readwise_sdk.operations.tags import (
    HighlightTagsResource as TagMutationsResource,
)
from readwise_sdk.operations.tags import TagHighlightsResource, TagOperations


class ReadwiseService:
    """Compose canonical operations from low-level resources."""

    def __init__(
        self,
        *,
        documents: DocumentsResource | None = None,
        highlights: HighlightsResource | None = None,
        highlight_tags: HighlightTagsResource | None = None,
        export: ExportResource | None = None,
        books: BooksResource | None = None,
        book_highlights: BookHighlightsResource | None = None,
        tag_highlights: TagHighlightsResource | None = None,
        tag_mutations: TagMutationsResource | None = None,
        digest_highlights: DigestHighlightsResource | None = None,
        digest_books: DigestBooksResource | None = None,
        sync_highlights: SyncHighlightsResource | None = None,
        sync_books: SyncBooksResource | None = None,
        sync_documents: SyncDocumentsResource | None = None,
    ) -> None:
        self._documents = DocumentOperations(documents) if documents is not None else None
        self._highlights = (
            HighlightOperations(highlights, highlight_tags, export)
            if highlights is not None and highlight_tags is not None and export is not None
            else None
        )
        highlights_for_books = book_highlights or highlights
        self._books = (
            BookOperations(books, highlights_for_books)
            if books is not None and highlights_for_books is not None
            else None
        )
        self._tags = (
            TagOperations(tag_highlights, tag_mutations)
            if tag_highlights is not None and tag_mutations is not None
            else None
        )
        self._digests = (
            DigestOperations(digest_highlights, digest_books)
            if digest_highlights is not None and digest_books is not None
            else None
        )
        self._sync = SyncOperations(
            highlights=sync_highlights,
            books=sync_books,
            documents=sync_documents,
        )

    @property
    def documents(self) -> DocumentOperations:
        """Return configured document operations."""
        if self._documents is None:
            raise RuntimeError("Document operations were not configured")
        return self._documents

    @property
    def highlights(self) -> HighlightOperations:
        """Return configured highlight operations."""
        if self._highlights is None:
            raise RuntimeError("Highlight operations were not configured")
        return self._highlights

    @property
    def books(self) -> BookOperations:
        """Return configured book operations."""
        if self._books is None:
            raise RuntimeError("Book operations were not configured")
        return self._books

    @property
    def tags(self) -> TagOperations:
        """Return configured tag operations."""
        if self._tags is None:
            raise RuntimeError("Tag operations were not configured")
        return self._tags

    @property
    def digests(self) -> DigestOperations:
        """Return configured digest operations."""
        if self._digests is None:
            raise RuntimeError("Digest operations were not configured")
        return self._digests

    @property
    def sync(self) -> SyncOperations:
        """Return configured synchronization operations."""
        return self._sync


__all__ = ["ReadwiseService"]
