"""Container for canonical operation groups."""

from __future__ import annotations

from readwise_sdk.operations.books import BookHighlightsResource, BookOperations, BooksResource
from readwise_sdk.operations.documents import DocumentOperations, DocumentsResource
from readwise_sdk.operations.highlights import (
    ExportResource,
    HighlightOperations,
    HighlightsResource,
    HighlightTagsResource,
)


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


__all__ = ["ReadwiseService"]
