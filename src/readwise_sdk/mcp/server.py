"""Readwise MCP server — exposes Readwise/Reader operations as MCP tools.

Tools are designed for agent ergonomics: fewer well-composed tools rather than
many thin wrappers.  The server talks to Readwise through the readwise-plus SDK.

Auth: reads ``READWISE_API_KEY`` from the environment, falling back to a
``READWISE_API_KEY=`` line in ``~/.env``.
"""

from __future__ import annotations

import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from readwise_sdk import (
    AsyncReadwiseClient,
    NotFoundError,
    ReadwiseError,
)
from readwise_sdk.mcp.output import (
    _book_summary,
    _doc_full,
    _doc_summary,
    _document_not_found,
    _error_result,
    _export_summary,
    _highlight_summary,
    _json_result,
)
from readwise_sdk.models import BookSearch, DocumentSearch, HighlightSearch
from readwise_sdk.operations import ReadwiseService
from readwise_sdk.resources.v2 import (
    AsyncBooksResource,
    AsyncExportResource,
    AsyncHighlightsResource,
    AsyncTagsResource,
)
from readwise_sdk.resources.v3 import AsyncDocumentsResource
from readwise_sdk.v2.models import BookCategory
from readwise_sdk.v3.models import (
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentUpdate,
)

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


def _service(client: AsyncReadwiseClient) -> ReadwiseService:
    """Compose canonical operations over one tool call's client transport."""
    transport = client._transport
    highlights = AsyncHighlightsResource(transport)
    return ReadwiseService(
        documents=AsyncDocumentsResource(transport),
        highlights=highlights,
        highlight_tags=AsyncTagsResource(transport),
        export=AsyncExportResource(transport),
        books=AsyncBooksResource(transport),
        book_highlights=highlights,
    )


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


def _parse_iso_datetime(s: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string, returning None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


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
            return _error_result(f"Invalid location '{location}'. Use: new, later, archive, feed.")

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
            result = await _service(client).documents.save(doc)
            return _json_result({"id": result.id, "url": result.url})
        except ReadwiseError as e:
            return _error_result(e)


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
    limit = min(max(limit, 1), 100)
    doc_location = None
    doc_category = None

    if location:
        try:
            doc_location = DocumentLocation(location)
        except ValueError:
            return _error_result(f"Invalid location '{location}'.")
    if category:
        try:
            doc_category = DocumentCategory(category)
        except ValueError:
            return _error_result(f"Invalid category '{category}'.")

    search = DocumentSearch.model_construct(
        location=doc_location,
        category=doc_category,
        updated_after=_parse_iso_datetime(updated_after),
        tags=tuple(tags or ()),
        query=query,
        limit=limit,
    )

    async with _client() as client:
        try:
            result = await _service(client).documents.search(search)
            return _json_result([_doc_summary(doc) for doc in result.items])
        except ReadwiseError as e:
            return _error_result(e)


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
            doc = await _service(client).documents.get(document_id, with_content=True)
            if doc is None:
                return _document_not_found(document_id)
            return _json_result(_doc_full(doc))
        except NotFoundError:
            return _document_not_found(document_id)
        except ReadwiseError as e:
            return _error_result(e)


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
            return _error_result(f"Invalid location '{location}'.")

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
            result = await _service(client).documents.update(document_id, update)
            return _json_result({"id": result.id, "url": result.url})
        except NotFoundError:
            return _document_not_found(document_id)
        except ReadwiseError as e:
            return _error_result(e)


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
            await _service(client).documents.delete(document_id)
            return _json_result({"deleted": document_id})
        except NotFoundError:
            return _document_not_found(document_id)
        except ReadwiseError as e:
            return _error_result(e)


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
    search = HighlightSearch.model_construct(
        book_id=book_id,
        updated_after=_parse_iso_datetime(updated_after),
        query=query,
        limit=limit,
    )

    async with _client() as client:
        try:
            result = await _service(client).highlights.search(search)
            return _json_result([_highlight_summary(item) for item in result.items])
        except ReadwiseError as e:
            return _error_result(e)


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
    async with _client() as client:
        try:
            result = await _service(client).highlights.export(
                updated_after=_parse_iso_datetime(updated_after),
                book_ids=book_ids,
                limit=limit,
            )
            return _json_result([_export_summary(item) for item in result.items])
        except ReadwiseError as e:
            return _error_result(e)


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
    book_category = None
    if category:
        try:
            book_category = BookCategory(category)
        except ValueError:
            return _error_result(
                f"Invalid category '{category}'. Use: books, articles, tweets, podcasts."
            )

    async with _client() as client:
        try:
            result = await _service(client).highlights.create_from_fields(
                text=text,
                title=title,
                author=author,
                source_url=source_url,
                note=note,
                category=book_category,
                highlighted_at=_parse_iso_datetime(highlighted_at),
            )
            return _json_result({"created_highlight_ids": result.ids})
        except ReadwiseError as e:
            return _error_result(e)


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
    limit = min(max(limit, 1), 100)
    book_category = None

    if category:
        try:
            book_category = BookCategory(category)
        except ValueError:
            return _error_result(f"Invalid category '{category}'.")

    search = BookSearch.model_construct(
        category=book_category,
        source=source,
        updated_after=None,
        query=query,
        limit=limit,
    )

    async with _client() as client:
        try:
            result = await _service(client).books.search(search)
            return _json_result([_book_summary(book) for book in result.items])
        except ReadwiseError as e:
            return _error_result(e)
