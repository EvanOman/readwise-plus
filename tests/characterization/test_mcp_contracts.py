"""Exact characterization contracts for all nine MCP tool handlers."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

pytest.importorskip("mcp")

from readwise_sdk.mcp.server import (
    create_highlight,
    delete_document,
    export_highlights,
    get_books,
    get_document,
    get_highlights,
    save_to_reader,
    search_documents,
    update_document,
)

V2_BASE = "https://readwise.io/api/v2"
V3_BASE = "https://readwise.io/api/v3"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READWISE_API_KEY", "token")


@respx.mock
@pytest.mark.asyncio
async def test_save_to_reader_returns_exact_compact_json() -> None:
    """save_to_reader is a compact two-field JSON adapter."""
    respx.post(f"{V3_BASE}/save/").mock(
        return_value=httpx.Response(
            201,
            json={"id": "doc-1", "url": "https://read.readwise.io/read/doc-1"},
        )
    )

    assert await save_to_reader("https://example.com") == (
        '{"id": "doc-1", "url": "https://read.readwise.io/read/doc-1"}'
    )


@respx.mock
@pytest.mark.asyncio
async def test_save_to_reader_includes_category_in_payload() -> None:
    """The category argument is validated and copied into the save payload."""
    route = respx.post(f"{V3_BASE}/save/").mock(
        return_value=httpx.Response(201, json={"id": "doc-1", "url": "reader-url"})
    )

    await save_to_reader(
        "https://example.com",
        title="Title",
        author="Author",
        summary="Summary",
        html="<p>Body</p>",
        tags=["tag"],
        notes="Note",
        category="article",
        location="later",
    )

    assert json.loads(route.calls.last.request.content) == {
        "url": "https://example.com",
        "html": "<p>Body</p>",
        "title": "Title",
        "author": "Author",
        "summary": "Summary",
        "location": "later",
        "category": "article",
        "saved_using": "readwise-mcp",
        "tags": ["tag"],
        "notes": "Note",
    }


@respx.mock
@pytest.mark.asyncio
async def test_save_to_reader_rejects_invalid_category() -> None:
    """An unknown category returns an error envelope and makes no request."""
    route = respx.post(f"{V3_BASE}/save/").mock(
        return_value=httpx.Response(201, json={"id": "doc-1", "url": "reader-url"})
    )

    result = await save_to_reader("https://example.com", category="bogus")

    assert json.loads(result) == {"error": "Invalid category 'bogus'."}
    assert not route.called


@respx.mock
@pytest.mark.asyncio
async def test_search_documents_returns_exact_compact_json_and_omits_none() -> None:
    """Document summaries omit absent fields rather than serializing nulls."""
    respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "doc-1",
                        "url": "https://reader.example/doc-1",
                        "source_url": "https://source.example/article",
                        "title": "Title",
                        "author": None,
                        "category": "article",
                        "location": "new",
                        "tags": [],
                        "word_count": 10,
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )

    assert await search_documents() == (
        '[{"id": "doc-1", "title": "Title", '
        '"url": "https://source.example/article", "category": "article", '
        '"location": "new", "word_count": 10}]'
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_document_returns_exact_full_compact_json_and_omits_none() -> None:
    """Full documents add only truthy content, summary, and notes fields."""
    respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "doc-1",
                        "url": "https://example.com",
                        "title": None,
                        "content": "<p>Body</p>",
                        "summary": "Summary",
                        "notes": "",
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )

    assert await get_document("doc-1") == (
        '{"id": "doc-1", "url": "https://example.com", '
        '"content": "<p>Body</p>", "summary": "Summary"}'
    )


@respx.mock
@pytest.mark.asyncio
async def test_update_document_returns_exact_compact_json() -> None:
    """update_document returns only the API's id and URL projection."""
    respx.patch(f"{V3_BASE}/update/doc-1/").mock(
        return_value=httpx.Response(200, json={"id": "doc-1", "url": "reader-url"})
    )

    assert await update_document("doc-1", title="New") == ('{"id": "doc-1", "url": "reader-url"}')


@respx.mock
@pytest.mark.asyncio
async def test_delete_document_returns_exact_compact_json() -> None:
    """delete_document returns its exact confirmation envelope."""
    respx.delete(f"{V3_BASE}/delete/doc-1/").mock(return_value=httpx.Response(204))

    assert await delete_document("doc-1") == '{"deleted": "doc-1"}'


@respx.mock
@pytest.mark.asyncio
async def test_get_highlights_returns_exact_compact_json_and_omits_none() -> None:
    """Highlight summaries include zero values and omit absent optional fields."""
    respx.get(f"{V2_BASE}/highlights/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1,
                        "text": "Insight",
                        "note": None,
                        "book_id": 0,
                        "color": "yellow",
                        "location": 0,
                        "tags": [],
                    }
                ],
                "next": None,
            },
        )
    )

    assert await get_highlights() == (
        '[{"id": 1, "text": "Insight", "book_id": 0, "color": "yellow", "location": 0}]'
    )


@respx.mock
@pytest.mark.asyncio
async def test_export_highlights_returns_exact_compact_json_and_omits_none() -> None:
    """Export books and their nested highlights use compact projections."""
    respx.get(f"{V2_BASE}/export/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "user_book_id": 2,
                        "title": "Book",
                        "author": None,
                        "highlights": [{"id": 1, "text": "Insight", "tags": []}],
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )

    assert await export_highlights() == (
        '[{"book_id": 2, "title": "Book", "highlights": [{"id": 1, "text": "Insight"}]}]'
    )


@respx.mock
@pytest.mark.asyncio
async def test_create_highlight_returns_exact_compact_json() -> None:
    """create_highlight returns the exact created-IDs envelope."""
    respx.post(f"{V2_BASE}/highlights/").mock(
        return_value=httpx.Response(200, json=[{"modified_highlights": [8, 9]}])
    )

    assert await create_highlight("Insight") == '{"created_highlight_ids": [8, 9]}'


@respx.mock
@pytest.mark.asyncio
async def test_get_books_returns_exact_compact_json_and_omits_none() -> None:
    """Book summaries retain zero counts but omit absent metadata."""
    respx.get(f"{V2_BASE}/books/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 2,
                        "title": "Book",
                        "author": None,
                        "category": "books",
                        "source": None,
                        "num_highlights": 0,
                    }
                ],
                "next": None,
            },
        )
    )

    assert await get_books() == (
        '[{"id": 2, "title": "Book", "category": "books", "num_highlights": 0}]'
    )


@pytest.mark.asyncio
async def test_invalid_enums_return_exact_error_envelopes() -> None:
    """Every enum-validating MCP entry point retains its current message."""
    assert await save_to_reader("https://example.com", location="bad") == (
        '{"error": "Invalid location \'bad\'. Use: new, later, archive, feed."}'
    )
    assert await search_documents(location="bad") == ('{"error": "Invalid location \'bad\'."}')
    assert await search_documents(category="bad") == ('{"error": "Invalid category \'bad\'."}')
    assert await update_document("doc-1", location="bad") == (
        '{"error": "Invalid location \'bad\'."}'
    )
    assert await create_highlight("text", category="bad") == (
        '{"error": "Invalid category \'bad\'. Use: books, articles, tweets, podcasts."}'
    )
    assert await get_books(category="bad") == '{"error": "Invalid category \'bad\'."}'


@respx.mock
@pytest.mark.asyncio
async def test_document_not_found_messages_are_exact() -> None:
    """All three document tools use the same quoted not-found wording."""
    respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(200, json={"results": [], "nextPageCursor": None})
    )
    respx.patch(f"{V3_BASE}/update/missing/").mock(
        return_value=httpx.Response(404, text="not found")
    )
    respx.delete(f"{V3_BASE}/delete/missing/").mock(
        return_value=httpx.Response(404, text="not found")
    )
    expected = '{"error": "Document \'missing\' not found."}'

    assert await get_document("missing") == expected
    assert await update_document("missing", title="new") == expected
    assert await delete_document("missing") == expected


def _documents(count: int) -> list[dict[str, object]]:
    return [{"id": f"doc-{index}", "url": f"https://example.com/{index}"} for index in range(count)]


def _highlights(count: int) -> list[dict[str, object]]:
    return [{"id": index, "text": f"highlight-{index}"} for index in range(count)]


def _exports(count: int) -> list[dict[str, object]]:
    return [
        {"user_book_id": index, "title": f"book-{index}", "highlights": []}
        for index in range(count)
    ]


def _books(count: int) -> list[dict[str, object]]:
    return [{"id": index, "title": f"book-{index}"} for index in range(count)]


@respx.mock
@pytest.mark.asyncio
async def test_search_documents_default_minimum_and_maximum_limits() -> None:
    """Document search defaults to 20 and clamps into the inclusive 1..100 range."""
    respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(200, json={"results": _documents(101), "nextPageCursor": None})
    )

    assert len(json.loads(await search_documents())) == 20
    assert len(json.loads(await search_documents(limit=0))) == 1
    assert len(json.loads(await search_documents(limit=1000))) == 100


@respx.mock
@pytest.mark.asyncio
async def test_get_highlights_default_minimum_and_maximum_limits() -> None:
    """Highlight search defaults to 50 and clamps into the inclusive 1..200 range."""
    respx.get(f"{V2_BASE}/highlights/").mock(
        return_value=httpx.Response(200, json={"results": _highlights(201), "next": None})
    )

    assert len(json.loads(await get_highlights())) == 50
    assert len(json.loads(await get_highlights(limit=0))) == 1
    assert len(json.loads(await get_highlights(limit=1000))) == 200


@respx.mock
@pytest.mark.asyncio
async def test_export_highlights_default_minimum_and_maximum_limits() -> None:
    """Highlight export defaults to 20 and clamps into the inclusive 1..100 range."""
    respx.get(f"{V2_BASE}/export/").mock(
        return_value=httpx.Response(200, json={"results": _exports(101), "nextPageCursor": None})
    )

    assert len(json.loads(await export_highlights())) == 20
    assert len(json.loads(await export_highlights(limit=0))) == 1
    assert len(json.loads(await export_highlights(limit=1000))) == 100


@respx.mock
@pytest.mark.asyncio
async def test_get_books_default_minimum_and_maximum_limits() -> None:
    """Book search defaults to 20 and clamps into the inclusive 1..100 range."""
    respx.get(f"{V2_BASE}/books/").mock(
        return_value=httpx.Response(200, json={"results": _books(101), "next": None})
    )

    assert len(json.loads(await get_books())) == 20
    assert len(json.loads(await get_books(limit=0))) == 1
    assert len(json.loads(await get_books(limit=1000))) == 100


@respx.mock
@pytest.mark.asyncio
async def test_invalid_datetimes_are_leniently_ignored_by_all_four_tools() -> None:
    """Invalid ISO strings silently become None rather than error envelopes."""
    docs = respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(200, json={"results": [], "nextPageCursor": None})
    )
    highlights = respx.get(f"{V2_BASE}/highlights/").mock(
        return_value=httpx.Response(200, json={"results": [], "next": None})
    )
    exports = respx.get(f"{V2_BASE}/export/").mock(
        return_value=httpx.Response(200, json={"results": [], "nextPageCursor": None})
    )
    created = respx.post(f"{V2_BASE}/highlights/").mock(
        return_value=httpx.Response(200, json=[{"modified_highlights": [1]}])
    )

    # NOTE: characterizes current lenient (possibly surprising) parsing.
    assert await search_documents(updated_after="not-a-date") == "[]"
    assert await get_highlights(updated_after="not-a-date") == "[]"
    assert await export_highlights(updated_after="not-a-date") == "[]"
    assert await create_highlight("text", highlighted_at="not-a-date") == (
        '{"created_highlight_ids": [1]}'
    )
    assert str(docs.calls.last.request.url) == f"{V3_BASE}/list/"
    assert str(highlights.calls.last.request.url) == f"{V2_BASE}/highlights/?page_size=100"
    assert str(exports.calls.last.request.url) == f"{V2_BASE}/export/"
    assert json.loads(created.calls.last.request.content) == {"highlights": [{"text": "text"}]}
