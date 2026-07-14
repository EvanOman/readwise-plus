"""Readwise MCP server — exposes Readwise/Reader operations as MCP tools.

Tools are designed for agent ergonomics: fewer well-composed tools rather than
many thin wrappers.  The server talks to Readwise through the readwise-plus SDK.

Auth: reads ``READWISE_API_KEY`` from the environment, falling back to a
``READWISE_API_KEY=`` line in ``~/.env``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from readwise_sdk import (
    AsyncReadwiseClient,
    NotFoundError,
    ReadwiseError,
)
from readwise_sdk.v2.models import HighlightCreate
from readwise_sdk.v3.models import DocumentCreate, DocumentLocation, DocumentUpdate

# ---------------------------------------------------------------------------
# Server + client setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "readwise",
    instructions=(
        "Readwise/Reader tools.  Use save_to_reader to save URLs or upload content. "
        "Use search_documents / get_document to find and read articles. "
        "Use get_highlights / export_highlights for highlight data. "
        "Use get_books to browse the library."
    ),
)


def _get_api_key() -> str:
    """Resolve the Readwise API key.

    Checks ``READWISE_API_KEY`` env var first, then falls back to a
    ``READWISE_API_KEY=`` line in ``~/.env``.
    """
    key = os.environ.get("READWISE_API_KEY", "")
    if key:
        return key

    env_file = os.path.expanduser("~/.env")
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("READWISE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")

    msg = "READWISE_API_KEY not found. Set it as an environment variable or add it to ~/.env"
    raise RuntimeError(msg)


def _client() -> AsyncReadwiseClient:
    """Create a fresh async client for each tool call."""
    return AsyncReadwiseClient(api_key=_get_api_key())


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_summary(doc: Any) -> dict[str, Any]:
    """Compact summary of a Document for listing results."""
    return {
        k: v
        for k, v in {
            "id": doc.id,
            "title": doc.title,
            "author": doc.author,
            "url": doc.source_url or doc.url,
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


def _highlight_summary(h: Any) -> dict[str, Any]:
    """Compact summary of a Highlight."""
    return {
        k: v
        for k, v in {
            "id": h.id,
            "text": h.text,
            "note": h.note,
            "book_id": h.book_id,
            "color": h.color.value if h.color else None,
            "location": h.location,
            "highlighted_at": h.highlighted_at.isoformat() if h.highlighted_at else None,
            "tags": [t.name for t in h.tags] if h.tags else None,
        }.items()
        if v is not None
    }


def _book_summary(b: Any) -> dict[str, Any]:
    """Compact summary of a Book."""
    return {
        k: v
        for k, v in {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "category": b.category.value if b.category else None,
            "source": b.source,
            "num_highlights": b.num_highlights,
            "source_url": b.source_url,
            "cover_image_url": b.cover_image_url,
            "last_highlight_at": (b.last_highlight_at.isoformat() if b.last_highlight_at else None),
        }.items()
        if v is not None
    }


def _parse_iso_datetime(s: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string, returning None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _json_result(data: Any) -> str:
    """Serialize a result to a compact JSON string."""
    return json.dumps(data, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Tools — Documents (Reader v3)
# ---------------------------------------------------------------------------


@mcp.tool()
async def save_to_reader(
    url: str,
    title: str | None = None,
    author: str | None = None,
    summary: str | None = None,
    html: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    category: str | None = None,
    location: str | None = None,
) -> str:
    """Save a URL or upload content to Readwise Reader.

    To save a web page for later reading, provide just the URL.
    To upload local content (e.g. a Markdown document converted to HTML),
    provide both a URL (as a unique identifier) and the html parameter.

    Args:
        url: The URL to save. For uploads, use a synthetic unique URL.
        title: Override the parsed title.
        author: Override the parsed author.
        summary: A short summary of the document.
        html: HTML content to upload (omit to let Reader scrape the URL).
        tags: Tags to apply to the document.
        notes: A top-level note on the document.
        category: Document type: article, email, pdf, epub, tweet, video.
        location: Where to put it: new (inbox), later, archive.

    Returns:
        JSON with the created document's id and Reader URL.
    """
    doc_location = None
    if location:
        try:
            doc_location = DocumentLocation(location)
        except ValueError:
            return _json_result(
                {"error": f"Invalid location '{location}'. Use: new, later, archive, feed."}
            )

    doc = DocumentCreate(
        url=url,
        title=title,
        author=author,
        summary=summary,
        html=html,
        tags=tags,
        notes=notes,
        location=doc_location,
        saved_using="readwise-mcp",
    )

    async with _client() as client:
        try:
            result = await client.v3.create_document(doc)
            return _json_result({"id": result.id, "url": result.url})
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


@mcp.tool()
async def search_documents(
    location: str | None = None,
    category: str | None = None,
    updated_after: str | None = None,
    tags: list[str] | None = None,
    query: str | None = None,
    limit: int = 20,
) -> str:
    """Search and filter documents in Readwise Reader.

    Returns a list of document summaries (no content — use get_document
    to fetch the full content of a specific document).

    Args:
        location: Filter by location: new (inbox), later, archive, feed.
        category: Filter by type: article, email, rss, pdf, epub, tweet, video.
        updated_after: ISO datetime — only docs updated after this time.
        tags: Filter by tags.
        query: Text search in title (case-insensitive substring match).
        limit: Maximum results to return (default 20, max 100).

    Returns:
        JSON array of document summaries.
    """
    from readwise_sdk.v3.models import DocumentCategory, DocumentLocation

    limit = min(max(limit, 1), 100)
    doc_location = None
    doc_category = None

    if location:
        try:
            doc_location = DocumentLocation(location)
        except ValueError:
            return _json_result({"error": f"Invalid location '{location}'."})
    if category:
        try:
            doc_category = DocumentCategory(category)
        except ValueError:
            return _json_result({"error": f"Invalid category '{category}'."})

    dt_after = _parse_iso_datetime(updated_after)
    query_lower = query.lower() if query else None

    async with _client() as client:
        try:
            results: list[dict[str, Any]] = []
            async for doc in client.v3.list_documents(
                location=doc_location,
                category=doc_category,
                updated_after=dt_after,
                tags=tags,
            ):
                if query_lower and doc.title and query_lower not in doc.title.lower():
                    continue
                results.append(_doc_summary(doc))
                if len(results) >= limit:
                    break
            return _json_result(results)
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


@mcp.tool()
async def get_document(document_id: str) -> str:
    """Get a single document from Readwise Reader by ID, including its full content.

    Args:
        document_id: The document ID (from search_documents results).

    Returns:
        JSON with full document details and HTML content.
    """
    async with _client() as client:
        try:
            doc = await client.v3.get_document(document_id, with_content=True)
            if doc is None:
                return _json_result({"error": f"Document '{document_id}' not found."})
            return _json_result(_doc_full(doc))
        except NotFoundError:
            return _json_result({"error": f"Document '{document_id}' not found."})
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


@mcp.tool()
async def update_document(
    document_id: str,
    title: str | None = None,
    author: str | None = None,
    summary: str | None = None,
    location: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """Update a document's metadata, move it between locations, or set tags.

    To archive a document, set location to "archive".
    To move it to the reading list, set location to "later".
    To move it back to inbox, set location to "new".

    Note: setting tags replaces all existing tags on the document.
    To add a tag without removing others, first get the document to see
    its current tags, then include them all in the tags list.

    Args:
        document_id: The document ID to update.
        title: New title.
        author: New author.
        summary: New summary.
        location: Move to: new, later, archive.
        tags: Replace tags with this list.
        notes: Set the document note.

    Returns:
        JSON with the updated document's id and URL.
    """
    doc_location = None
    if location:
        try:
            doc_location = DocumentLocation(location)
        except ValueError:
            return _json_result({"error": f"Invalid location '{location}'."})

    update = DocumentUpdate(
        title=title,
        author=author,
        summary=summary,
        location=doc_location,
        tags=tags,
        notes=notes,
    )

    async with _client() as client:
        try:
            result = await client.v3.update_document(document_id, update)
            return _json_result({"id": result.id, "url": result.url})
        except NotFoundError:
            return _json_result({"error": f"Document '{document_id}' not found."})
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


@mcp.tool()
async def delete_document(document_id: str) -> str:
    """Delete a document from Readwise Reader.

    This is permanent and cannot be undone.

    Args:
        document_id: The document ID to delete.

    Returns:
        JSON confirmation or error.
    """
    async with _client() as client:
        try:
            await client.v3.delete_document(document_id)
            return _json_result({"deleted": document_id})
        except NotFoundError:
            return _json_result({"error": f"Document '{document_id}' not found."})
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


# ---------------------------------------------------------------------------
# Tools — Highlights (Readwise v2)
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_highlights(
    book_id: int | None = None,
    updated_after: str | None = None,
    query: str | None = None,
    limit: int = 50,
) -> str:
    """List highlights from Readwise with optional filters.

    Args:
        book_id: Only highlights from this book/source ID.
        updated_after: ISO datetime — only highlights updated after this.
        query: Text search in highlight text (case-insensitive substring).
        limit: Maximum results (default 50, max 200).

    Returns:
        JSON array of highlights.
    """
    limit = min(max(limit, 1), 200)
    dt_after = _parse_iso_datetime(updated_after)
    query_lower = query.lower() if query else None

    async with _client() as client:
        try:
            results: list[dict[str, Any]] = []
            async for h in client.v2.list_highlights(
                book_id=book_id,
                updated_after=dt_after,
            ):
                if query_lower and query_lower not in h.text.lower():
                    continue
                results.append(_highlight_summary(h))
                if len(results) >= limit:
                    break
            return _json_result(results)
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


@mcp.tool()
async def export_highlights(
    updated_after: str | None = None,
    book_ids: list[int] | None = None,
    limit: int = 20,
) -> str:
    """Export highlights grouped by book — efficient for bulk retrieval.

    Each result is a book with its highlights nested inside, which is
    more efficient than listing highlights individually.

    Args:
        updated_after: ISO datetime — only highlights updated after this.
        book_ids: Only export from these specific book IDs.
        limit: Maximum number of books to return (default 20, max 100).

    Returns:
        JSON array of books, each containing a highlights array.
    """
    limit = min(max(limit, 1), 100)
    dt_after = _parse_iso_datetime(updated_after)

    async with _client() as client:
        try:
            results: list[dict[str, Any]] = []
            async for book in client.v2.export_highlights(
                updated_after=dt_after,
                book_ids=book_ids,
            ):
                book_data: dict[str, Any] = {
                    "book_id": book.user_book_id,
                    "title": book.title,
                    "author": book.author,
                    "category": book.category.value if book.category else None,
                    "source": book.source,
                    "source_url": book.source_url,
                    "highlights": [_highlight_summary(h) for h in book.highlights],
                }
                results.append({k: v for k, v in book_data.items() if v is not None})
                if len(results) >= limit:
                    break
            return _json_result(results)
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


@mcp.tool()
async def create_highlight(
    text: str,
    title: str | None = None,
    author: str | None = None,
    source_url: str | None = None,
    note: str | None = None,
    category: str | None = None,
    highlighted_at: str | None = None,
) -> str:
    """Create a new highlight in Readwise.

    The highlight will be associated with a book/source identified by
    title + author + source_url.  If no matching book exists, Readwise
    creates one automatically.

    Args:
        text: The highlighted text (required, max 8191 chars).
        title: Title of the book or article.
        author: Author name.
        source_url: URL of the source.
        note: A note to attach to the highlight.
        category: Source category: books, articles, tweets, podcasts.
        highlighted_at: ISO datetime when the highlight was made.

    Returns:
        JSON with created highlight IDs.
    """
    from readwise_sdk.v2.models import BookCategory

    book_category = None
    if category:
        try:
            book_category = BookCategory(category)
        except ValueError:
            return _json_result(
                {"error": f"Invalid category '{category}'. Use: books, articles, tweets, podcasts."}
            )

    highlight = HighlightCreate(
        text=text[:8191],
        title=title,
        author=author,
        source_url=source_url,
        note=note,
        category=book_category,
        highlighted_at=_parse_iso_datetime(highlighted_at),
    )

    async with _client() as client:
        try:
            ids = await client.v2.create_highlights([highlight])
            return _json_result({"created_highlight_ids": ids})
        except ReadwiseError as e:
            return _json_result({"error": str(e)})


# ---------------------------------------------------------------------------
# Tools — Books (Readwise v2)
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_books(
    category: str | None = None,
    source: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> str:
    """List books and sources in Readwise.

    Args:
        category: Filter by type: books, articles, tweets, podcasts, supplementals.
        source: Filter by import source (e.g. kindle, instapaper, manual).
        query: Text search in title (case-insensitive substring).
        limit: Maximum results (default 20, max 100).

    Returns:
        JSON array of book summaries.
    """
    from readwise_sdk.v2.models import BookCategory

    limit = min(max(limit, 1), 100)
    book_category = None

    if category:
        try:
            book_category = BookCategory(category)
        except ValueError:
            return _json_result({"error": f"Invalid category '{category}'."})

    query_lower = query.lower() if query else None

    async with _client() as client:
        try:
            results: list[dict[str, Any]] = []
            async for book in client.v2.list_books(
                category=book_category,
                source=source,
            ):
                if query_lower and query_lower not in book.title.lower():
                    continue
                results.append(_book_summary(book))
                if len(results) >= limit:
                    break
            return _json_result(results)
        except ReadwiseError as e:
            return _json_result({"error": str(e)})
