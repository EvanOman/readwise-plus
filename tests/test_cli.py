"""Tests for the CLI module."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from readwise_sdk.cli.main import app, get_client
from readwise_sdk.client import READWISE_API_V2_BASE, READWISE_API_V3_BASE
from readwise_sdk.v2.models import Tag

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set READWISE_API_KEY for all tests by default."""
    monkeypatch.setenv("READWISE_API_KEY", "test-key")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_json(output: str) -> Any:
    """Extract and parse the first JSON object/array from CLI output.

    The Rich console may prepend status lines (e.g. "Fetching tag report...")
    before the actual JSON payload.  This helper locates the first '{' or '['
    and parses from there.
    """
    for i, ch in enumerate(output):
        if ch in ("{", "["):
            return json.loads(output[i:])
    raise ValueError(f"No JSON found in output: {output!r}")


def _highlight(
    id: int = 1,
    text: str = "Test highlight",
    note: str | None = None,
    location: int | None = None,
    tags: list[Tag] | None = None,
    highlighted_at: str | None = None,
    book_id: int | None = None,
) -> dict:
    """Return a highlight dict suitable for an API response."""
    return {
        "id": id,
        "text": text,
        "note": note,
        "location": location,
        "tags": [{"id": t.id, "name": t.name} for t in tags] if tags else [],
        "highlighted_at": highlighted_at,
        "book_id": book_id,
    }


def _book(
    id: int = 1,
    title: str = "Test Book",
    author: str | None = "Author",
    category: str | None = None,
    num_highlights: int = 5,
    source: str | None = None,
) -> dict:
    """Return a book dict suitable for an API response."""
    return {
        "id": id,
        "title": title,
        "author": author,
        "category": category,
        "num_highlights": num_highlights,
        "source": source,
    }


def _document(
    id: str = "doc-1",
    url: str = "https://example.com/article",
    title: str | None = "Test Article",
    category: str | None = "article",
    location: str | None = "new",
    author: str | None = None,
) -> dict:
    """Return a document dict suitable for an API response."""
    return {
        "id": id,
        "url": url,
        "title": title,
        "category": category,
        "location": location,
        "author": author,
    }


def _mock_v2_highlights(highlights: list[dict]) -> respx.Route:
    """Mock the V2 highlights endpoint with a paginated response."""
    return respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
        return_value=httpx.Response(200, json={"results": highlights, "next": None})
    )


def _mock_v2_books(books: list[dict]) -> respx.Route:
    """Mock the V2 books endpoint with a paginated response."""
    return respx.get(f"{READWISE_API_V2_BASE}/books/").mock(
        return_value=httpx.Response(200, json={"results": books, "next": None})
    )


def _mock_v3_documents(documents: list[dict]) -> respx.Route:
    """Mock the V3 documents endpoint with a paginated response."""
    return respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
        return_value=httpx.Response(200, json={"results": documents, "nextPageCursor": None})
    )


# ---------------------------------------------------------------------------
# get_client()
# ---------------------------------------------------------------------------


class TestGetClient:
    """Tests for the get_client helper function."""

    def test_get_client_with_api_key(self) -> None:
        """get_client returns a ReadwiseClient when READWISE_API_KEY is set."""
        client = get_client()
        assert client.api_key == "test-key"

    def test_get_client_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_client raises typer.Exit when READWISE_API_KEY is not set."""
        monkeypatch.delenv("READWISE_API_KEY", raising=False)
        from click.exceptions import Exit

        with pytest.raises(Exit):
            get_client()


# ---------------------------------------------------------------------------
# Version command
# ---------------------------------------------------------------------------


class TestVersionCommand:
    """Tests for the version command."""

    def test_version(self) -> None:
        """version command prints version info."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "readwise-plus" in result.output


# ---------------------------------------------------------------------------
# Highlights commands
# ---------------------------------------------------------------------------


class TestHighlightsListCommand:
    """Tests for the highlights list command."""

    @respx.mock
    def test_list_highlights_table(self) -> None:
        """highlights list outputs a table by default."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="Highlight one"),
                _highlight(id=2, text="Highlight two"),
            ]
        )
        result = runner.invoke(app, ["highlights", "list"])
        assert result.exit_code == 0
        assert "Highlight one" in result.output
        assert "Highlight two" in result.output

    @respx.mock
    def test_list_highlights_json(self) -> None:
        """highlights list --json outputs JSON."""
        _mock_v2_highlights([_highlight(id=10, text="Short text", note="A note")])
        result = runner.invoke(app, ["highlights", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == 10
        assert data[0]["note"] == "A note"

    @respx.mock
    def test_list_highlights_limit(self) -> None:
        """highlights list --limit respects the limit option."""
        _mock_v2_highlights([_highlight(id=i, text=f"H{i}") for i in range(5)])
        result = runner.invoke(app, ["highlights", "list", "--limit", "2", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    @respx.mock
    def test_list_highlights_long_text_truncation_json(self) -> None:
        """Long highlight texts are truncated in JSON output."""
        long_text = "A" * 200
        _mock_v2_highlights([_highlight(id=1, text=long_text)])
        result = runner.invoke(app, ["highlights", "list", "--json"])
        assert result.exit_code == 0
        assert "..." in result.output
        assert long_text not in result.output

    @respx.mock
    def test_list_highlights_empty(self) -> None:
        """highlights list handles empty response."""
        _mock_v2_highlights([])
        result = runner.invoke(app, ["highlights", "list"])
        assert result.exit_code == 0
        assert "0 shown" in result.output

    def test_list_highlights_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """highlights list fails when API key is missing."""
        monkeypatch.delenv("READWISE_API_KEY", raising=False)
        result = runner.invoke(app, ["highlights", "list"])
        assert result.exit_code != 0


class TestHighlightsShowCommand:
    """Tests for the highlights show command."""

    @respx.mock
    def test_show_highlight(self) -> None:
        """highlights show displays highlight details."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/42/").mock(
            return_value=httpx.Response(
                200,
                json=_highlight(
                    id=42,
                    text="Great insight",
                    note="My note",
                    location=15,
                    tags=[Tag(id=1, name="favorite")],
                    highlighted_at="2024-01-01T00:00:00Z",
                ),
            )
        )
        result = runner.invoke(app, ["highlights", "show", "42"])
        assert result.exit_code == 0
        for expected in ("42", "Great insight", "My note", "15", "favorite"):
            assert expected in result.output

    @respx.mock
    def test_show_highlight_not_found(self) -> None:
        """highlights show handles not-found gracefully."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/99999/").mock(
            return_value=httpx.Response(404, text="Not found")
        )
        result = runner.invoke(app, ["highlights", "show", "99999"])
        assert result.exit_code != 0

    @respx.mock
    def test_show_highlight_minimal(self) -> None:
        """highlights show works with minimal data (no note, location, tags)."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/1/").mock(
            return_value=httpx.Response(200, json=_highlight(id=1, text="Minimal highlight"))
        )
        result = runner.invoke(app, ["highlights", "show", "1"])
        assert result.exit_code == 0
        assert "Minimal highlight" in result.output


class TestHighlightsExportCommand:
    """Tests for the highlights export command."""

    @respx.mock
    @pytest.mark.parametrize(
        ("extra_args", "expected_in_output"),
        [
            ([], "Exported text"),
            (["--format", "json"], "JSON export"),
        ],
        ids=["default_markdown", "json_format"],
    )
    def test_export_highlights(self, extra_args: list[str], expected_in_output: str) -> None:
        """highlights export outputs in the requested format."""
        _mock_v2_highlights([_highlight(id=1, text=expected_in_output)])
        result = runner.invoke(app, ["highlights", "export", *extra_args])
        assert result.exit_code == 0
        assert expected_in_output in result.output

    @respx.mock
    def test_export_highlights_to_file(self, tmp_path) -> None:
        """highlights export -o writes to a file."""
        _mock_v2_highlights([_highlight(id=1, text="File export")])
        outfile = tmp_path / "export.md"
        result = runner.invoke(app, ["highlights", "export", "-o", str(outfile)])
        assert result.exit_code == 0
        assert "Exported to" in result.output
        assert outfile.exists()
        assert "File export" in outfile.read_text()

    def test_export_highlights_invalid_format(self) -> None:
        """highlights export fails with an invalid format."""
        result = runner.invoke(app, ["highlights", "export", "--format", "invalid_format"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Books commands
# ---------------------------------------------------------------------------


class TestBooksListCommand:
    """Tests for the books list command."""

    @respx.mock
    def test_list_books_table(self) -> None:
        """books list outputs a table by default."""
        _mock_v2_books(
            [
                _book(id=1, title="Book One", author="Author One", num_highlights=10),
                _book(id=2, title="Book Two", author="Author Two", num_highlights=3),
            ]
        )
        result = runner.invoke(app, ["books", "list"])
        assert result.exit_code == 0
        assert "Book One" in result.output
        assert "Book Two" in result.output

    @respx.mock
    def test_list_books_json(self) -> None:
        """books list --json outputs JSON."""
        _mock_v2_books([_book(id=5, title="My Book", author="Jane", num_highlights=7)])
        result = runner.invoke(app, ["books", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == 5
        assert data[0]["highlights"] == 7

    @respx.mock
    def test_list_books_with_category(self) -> None:
        """books list --category filters by category."""
        route = _mock_v2_books([])
        result = runner.invoke(app, ["books", "list", "--category", "articles"])
        assert result.exit_code == 0
        assert route.called
        assert "category=articles" in str(route.calls.last.request.url)

    def test_list_books_invalid_category(self) -> None:
        """books list fails with an invalid category."""
        result = runner.invoke(app, ["books", "list", "--category", "not_a_category"])
        assert result.exit_code != 0

    @respx.mock
    def test_list_books_empty(self) -> None:
        """books list handles empty response."""
        _mock_v2_books([])
        result = runner.invoke(app, ["books", "list"])
        assert result.exit_code == 0
        assert "0 shown" in result.output

    @respx.mock
    def test_list_books_long_title_truncation(self) -> None:
        """Long book titles are truncated in table output."""
        long_title = "A" * 50
        _mock_v2_books([_book(id=1, title=long_title, author="B" * 25)])
        result = runner.invoke(app, ["books", "list"])
        assert result.exit_code == 0
        assert "..." in result.output
        assert long_title not in result.output


class TestBooksShowCommand:
    """Tests for the books show command."""

    @respx.mock
    def test_show_book(self) -> None:
        """books show displays book details with highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/books/10/").mock(
            return_value=httpx.Response(
                200,
                json=_book(
                    id=10,
                    title="Great Book",
                    author="John",
                    category="books",
                    num_highlights=3,
                    source="kindle",
                ),
            )
        )
        _mock_v2_highlights(
            [
                _highlight(id=1, text="Highlight A"),
                _highlight(id=2, text="Highlight B"),
            ]
        )
        result = runner.invoke(app, ["books", "show", "10"])
        assert result.exit_code == 0
        for expected in ("Great Book", "John", "books", "kindle", "Highlight A"):
            assert expected in result.output

    @respx.mock
    def test_show_book_not_found(self) -> None:
        """books show handles not-found gracefully."""
        respx.get(f"{READWISE_API_V2_BASE}/books/99999/").mock(
            return_value=httpx.Response(404, text="Not found")
        )
        result = runner.invoke(app, ["books", "show", "99999"])
        assert result.exit_code != 0

    @respx.mock
    def test_show_book_no_highlights(self) -> None:
        """books show works when there are no highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/books/5/").mock(
            return_value=httpx.Response(200, json=_book(id=5, title="Empty Book", num_highlights=0))
        )
        _mock_v2_highlights([])
        result = runner.invoke(app, ["books", "show", "5"])
        assert result.exit_code == 0
        assert "Empty Book" in result.output


# ---------------------------------------------------------------------------
# Reader commands
# ---------------------------------------------------------------------------


class TestReaderInboxCommand:
    """Tests for the reader inbox command."""

    @respx.mock
    def test_reader_inbox_table(self) -> None:
        """reader inbox outputs a table by default."""
        _mock_v3_documents(
            [
                _document(id="d1", title="Article One", category="article"),
                _document(id="d2", title="Article Two", category="email"),
            ]
        )
        result = runner.invoke(app, ["reader", "inbox"])
        assert result.exit_code == 0
        assert "Article One" in result.output
        assert "Article Two" in result.output

    @respx.mock
    def test_reader_inbox_json(self) -> None:
        """reader inbox --json outputs JSON."""
        _mock_v3_documents(
            [
                _document(id="abc123", title="Test Doc", category="article"),
            ]
        )
        result = runner.invoke(app, ["reader", "inbox", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == "abc123"
        assert data[0]["category"] == "article"

    @respx.mock
    def test_reader_inbox_limit(self) -> None:
        """reader inbox --limit respects the limit option."""
        _mock_v3_documents([_document(id=f"d{i}", title=f"Doc {i}") for i in range(5)])
        result = runner.invoke(app, ["reader", "inbox", "--limit", "3", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3

    @respx.mock
    def test_reader_inbox_empty(self) -> None:
        """reader inbox handles empty response."""
        _mock_v3_documents([])
        result = runner.invoke(app, ["reader", "inbox"])
        assert result.exit_code == 0
        assert "0 shown" in result.output


class TestReaderSaveCommand:
    """Tests for the reader save command."""

    @respx.mock
    def test_reader_save(self) -> None:
        """reader save saves a URL."""
        respx.post(f"{READWISE_API_V3_BASE}/save/").mock(
            return_value=httpx.Response(
                200, json={"id": "new-doc-id", "url": "https://example.com/saved"}
            )
        )
        result = runner.invoke(app, ["reader", "save", "https://example.com/saved"])
        assert result.exit_code == 0
        assert "Saved" in result.output
        assert "new-doc-id" in result.output

    @respx.mock
    def test_reader_save_error(self) -> None:
        """reader save handles errors gracefully."""
        respx.post(f"{READWISE_API_V3_BASE}/save/").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        result = runner.invoke(app, ["reader", "save", "https://example.com/fail"])
        assert result.exit_code != 0


class TestReaderArchiveCommand:
    """Tests for the reader archive command."""

    @respx.mock
    def test_reader_archive(self) -> None:
        """reader archive archives a document."""
        respx.patch(url__startswith=f"{READWISE_API_V3_BASE}/update/").mock(
            return_value=httpx.Response(
                200, json={"id": "doc-to-archive", "url": "https://example.com"}
            )
        )
        result = runner.invoke(app, ["reader", "archive", "doc-to-archive"])
        assert result.exit_code == 0
        assert "Archived" in result.output

    @respx.mock
    def test_reader_archive_error(self) -> None:
        """reader archive handles errors gracefully."""
        respx.patch(url__startswith=f"{READWISE_API_V3_BASE}/update/").mock(
            return_value=httpx.Response(404, text="Not found")
        )
        result = runner.invoke(app, ["reader", "archive", "nonexistent"])
        assert result.exit_code != 0


class TestReaderStatsCommand:
    """Tests for the reader stats command."""

    @respx.mock
    def test_reader_stats(self) -> None:
        """reader stats displays queue statistics."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            side_effect=lambda request: httpx.Response(
                200,
                json={
                    "results": [
                        _document(id=f"inbox-{i}", title=f"Inbox {i}", category="article")
                        for i in range(3)
                    ],
                    "nextPageCursor": None,
                }
                if "location=new" in str(request.url)
                else {
                    "results": [
                        _document(id=f"later-{i}", title=f"Later {i}", category="email")
                        for i in range(2)
                    ],
                    "nextPageCursor": None,
                },
            )
        )
        result = runner.invoke(app, ["reader", "stats"])
        assert result.exit_code == 0
        for expected in ("3", "2", "5", "article", "email"):
            assert expected in result.output

    @respx.mock
    def test_reader_stats_empty(self) -> None:
        """reader stats handles empty inbox and reading list (no age display)."""
        _mock_v3_documents([])
        result = runner.invoke(app, ["reader", "stats"])
        assert result.exit_code == 0
        assert "Oldest Item" not in result.output
        assert "Average Age" not in result.output


# ---------------------------------------------------------------------------
# Sync commands
# ---------------------------------------------------------------------------


class TestSyncCommands:
    """Tests for sync full and incremental commands."""

    @respx.mock
    def test_sync_full(self) -> None:
        """sync full performs a full sync."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="H1"),
                _highlight(id=2, text="H2"),
            ]
        )
        _mock_v2_books([_book(id=1, title="B1")])
        _mock_v3_documents([])

        result = runner.invoke(app, ["sync", "full"])
        assert result.exit_code == 0
        assert "Sync complete" in result.output
        assert "Highlights: 2" in result.output
        assert "Books: 1" in result.output
        assert "Documents: 0" in result.output

    @respx.mock
    def test_sync_incremental(self) -> None:
        """sync incremental performs an incremental sync."""
        _mock_v2_highlights([_highlight(id=1, text="New H")])
        _mock_v2_books([])
        _mock_v3_documents([_document(id="d1", url="https://example.com")])

        result = runner.invoke(app, ["sync", "incremental"])
        assert result.exit_code == 0
        assert "Sync complete" in result.output
        assert "New highlights: 1" in result.output
        assert "New books: 0" in result.output
        assert "New documents: 1" in result.output
        assert "Total syncs: 1" in result.output

    def test_sync_incremental_with_state_file(self, tmp_path) -> None:
        """sync incremental --state-file persists state to disk."""
        state_file = tmp_path / "sync.json"

        with respx.mock:
            _mock_v2_highlights([])
            _mock_v2_books([])
            _mock_v3_documents([])
            result = runner.invoke(app, ["sync", "incremental", "--state-file", str(state_file)])

        assert result.exit_code == 0
        assert state_file.exists()
        state_data = json.loads(state_file.read_text())
        assert state_data["total_syncs"] == 1

    def test_sync_status_reads_a_legacy_state_file(self, tmp_path) -> None:
        """sync status reports checkpoints from existing unversioned state."""
        state_file = tmp_path / "sync.json"
        state_file.write_text(
            json.dumps(
                {
                    "last_highlight_sync": "2025-02-03T04:05:06+00:00",
                    "last_book_sync": None,
                    "last_document_sync": None,
                    "total_syncs": 7,
                    "last_sync_time": "2025-02-03T04:05:06+00:00",
                }
            )
        )

        result = runner.invoke(app, ["sync", "status", "--state-file", str(state_file)])

        assert result.exit_code == 0
        assert "2025-02-03T04:05:06+00:00" in result.output

    def test_sync_reset_writes_new_versioned_state(self, tmp_path) -> None:
        """sync reset clears the checkpoint through the canonical state store."""
        state_file = tmp_path / "sync.json"

        result = runner.invoke(app, ["sync", "reset", "--state-file", str(state_file)])

        assert result.exit_code == 0
        assert "Sync state reset" in result.output
        assert json.loads(state_file.read_text()) == {
            "version": 1,
            "last_highlight_sync": None,
            "last_book_sync": None,
            "last_document_sync": None,
            "last_sync_time": None,
        }


# ---------------------------------------------------------------------------
# Digest commands
# ---------------------------------------------------------------------------


class TestDigestCommands:
    """Tests for digest daily, weekly, and book commands."""

    @respx.mock
    @pytest.mark.parametrize(
        ("subcommand", "expected_title"),
        [
            (["daily"], "Daily Digest"),
            (["weekly"], "Weekly Digest"),
        ],
        ids=["daily", "weekly"],
    )
    def test_digest_default_output(self, subcommand: list[str], expected_title: str) -> None:
        """digest daily/weekly outputs a digest with the correct title."""
        _mock_v2_highlights([_highlight(id=1, text="Digest highlight")])
        result = runner.invoke(app, ["digest", *subcommand])
        assert result.exit_code == 0
        assert expected_title in result.output
        assert "Digest highlight" in result.output

    @respx.mock
    def test_digest_daily_json_format(self) -> None:
        """digest daily --format json outputs JSON digest."""
        _mock_v2_highlights([_highlight(id=1, text="JSON highlight")])
        result = runner.invoke(app, ["digest", "daily", "--format", "json"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert data["title"] == "Daily Digest"
        assert len(data["highlights"]) == 1

    @respx.mock
    @pytest.mark.parametrize(
        ("subcommand", "expected_saved_msg", "expected_title"),
        [
            (["daily"], "Saved daily digest", "Daily Digest"),
            (["weekly"], "Saved weekly digest", "Weekly Digest"),
        ],
        ids=["daily", "weekly"],
    )
    def test_digest_to_file(
        self,
        subcommand: list[str],
        expected_saved_msg: str,
        expected_title: str,
        tmp_path,
    ) -> None:
        """digest daily/weekly -o writes to a file."""
        _mock_v2_highlights([_highlight(id=1, text="File content")])
        outfile = tmp_path / "digest.md"
        result = runner.invoke(app, ["digest", *subcommand, "-o", str(outfile)])
        assert result.exit_code == 0
        assert expected_saved_msg in result.output
        assert outfile.exists()
        content = outfile.read_text()
        assert expected_title in content

    @pytest.mark.parametrize(
        ("subcommand", "format_value"),
        [
            (["daily"], "xml"),
            (["weekly"], "html"),
            (["book", "42"], "pdf"),
        ],
        ids=["daily_xml", "weekly_html", "book_pdf"],
    )
    def test_digest_invalid_format(self, subcommand: list[str], format_value: str) -> None:
        """digest commands fail with invalid format values."""
        result = runner.invoke(app, ["digest", *subcommand, "--format", format_value])
        assert result.exit_code != 0

    @respx.mock
    def test_digest_book(self) -> None:
        """digest book outputs a book digest."""
        respx.get(f"{READWISE_API_V2_BASE}/books/42/").mock(
            return_value=httpx.Response(200, json=_book(id=42, title="My Great Book"))
        )
        _mock_v2_highlights([_highlight(id=1, text="Book highlight")])
        result = runner.invoke(app, ["digest", "book", "42"])
        assert result.exit_code == 0
        assert "My Great Book" in result.output
        assert "Book highlight" in result.output

    @respx.mock
    def test_digest_book_to_file(self, tmp_path) -> None:
        """digest book -o writes to a file."""
        respx.get(f"{READWISE_API_V2_BASE}/books/42/").mock(
            return_value=httpx.Response(200, json=_book(id=42, title="File Book"))
        )
        _mock_v2_highlights([_highlight(id=1, text="Book file content")])
        outfile = tmp_path / "book.md"
        result = runner.invoke(app, ["digest", "book", "42", "-o", str(outfile)])
        assert result.exit_code == 0
        assert "Saved book digest" in result.output
        assert outfile.exists()
        assert "File Book" in outfile.read_text()


# ---------------------------------------------------------------------------
# Tags commands
# ---------------------------------------------------------------------------


class TestTagsListCommand:
    """Tests for the tags list command."""

    @respx.mock
    def test_tags_list_table(self) -> None:
        """tags list outputs a table by default."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="H1", tags=[Tag(id=1, name="python")]),
                _highlight(id=2, text="H2", tags=[Tag(id=1, name="python")]),
                _highlight(
                    id=3,
                    text="H3",
                    tags=[Tag(id=1, name="python"), Tag(id=2, name="coding")],
                ),
                _highlight(id=4, text="H4", tags=[Tag(id=2, name="coding")]),
                _highlight(id=5, text="H5", tags=[Tag(id=3, name="ai")]),
            ]
        )
        result = runner.invoke(app, ["tags", "list"])
        assert result.exit_code == 0
        for tag in ("python", "coding", "ai"):
            assert tag in result.output

    @respx.mock
    def test_tags_list_json(self) -> None:
        """tags list --json outputs JSON."""
        _mock_v2_highlights(
            [
                _highlight(
                    id=1,
                    text="H1",
                    tags=[Tag(id=1, name="python"), Tag(id=2, name="coding")],
                ),
                _highlight(id=2, text="H2", tags=[Tag(id=1, name="python")]),
                _highlight(id=3, text="H3", tags=[Tag(id=2, name="coding")]),
            ]
        )
        result = runner.invoke(app, ["tags", "list", "--json"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert data["total_tags"] == 2
        assert data["total_usages"] == 4
        assert len(data["tags"]) == 2

    @respx.mock
    def test_tags_list_with_duplicates(self) -> None:
        """tags list shows duplicate candidates."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="H1", tags=[Tag(id=1, name="python")]),
                _highlight(id=2, text="H2", tags=[Tag(id=2, name="Python")]),
                _highlight(id=3, text="H3", tags=[Tag(id=3, name="coding")]),
                _highlight(id=4, text="H4", tags=[Tag(id=4, name="Coding")]),
            ]
        )
        result = runner.invoke(app, ["tags", "list"])
        assert result.exit_code == 0
        assert "duplicates" in result.output.lower() or "Potential" in result.output


class TestTagsSearchCommand:
    """Tests for the tags search command."""

    @respx.mock
    def test_tags_search_table(self) -> None:
        """tags search outputs a table filtering by tag."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="Python programming", tags=[Tag(id=1, name="python")]),
                _highlight(
                    id=2,
                    text="Python data science",
                    tags=[Tag(id=1, name="python"), Tag(id=2, name="data")],
                ),
                _highlight(id=3, text="JavaScript basics", tags=[Tag(id=3, name="javascript")]),
            ]
        )
        result = runner.invoke(app, ["tags", "search", "python"])
        assert result.exit_code == 0
        assert "Python programming" in result.output
        assert "Python data science" in result.output
        assert "JavaScript basics" not in result.output

    @respx.mock
    def test_tags_search_json(self) -> None:
        """tags search --json outputs JSON."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="Short text", tags=[Tag(id=1, name="test")]),
                _highlight(id=2, text="No match"),
            ]
        )
        result = runner.invoke(app, ["tags", "search", "test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert "test" in data[0]["tags"]


class TestTagsUntaggedCommand:
    """Tests for the tags untagged command."""

    @respx.mock
    def test_tags_untagged_table(self) -> None:
        """tags untagged outputs a table of untagged highlights."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="No tags here"),
                _highlight(id=2, text="Also no tags"),
                _highlight(id=3, text="Has a tag", tags=[Tag(id=1, name="tagged")]),
            ]
        )
        result = runner.invoke(app, ["tags", "untagged"])
        assert result.exit_code == 0
        assert "No tags here" in result.output
        assert "Also no tags" in result.output
        assert "Has a tag" not in result.output

    @respx.mock
    def test_tags_untagged_json(self) -> None:
        """tags untagged --json outputs JSON."""
        _mock_v2_highlights([_highlight(id=10, text="Untagged highlight")])
        result = runner.invoke(app, ["tags", "untagged", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == 10

    @respx.mock
    def test_tags_untagged_empty(self) -> None:
        """tags untagged handles empty result."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="Tagged", tags=[Tag(id=1, name="some-tag")]),
            ]
        )
        result = runner.invoke(app, ["tags", "untagged"])
        assert result.exit_code == 0


class TestAutoTagCommand:
    """Tests for the tags auto-tag command."""

    @respx.mock
    def test_auto_tag_dry_run(self) -> None:
        """tags auto-tag performs a dry run, shows match count and hint."""
        _mock_v2_highlights(
            [
                _highlight(id=100, text="I love python programming"),
                _highlight(id=200, text="Python is great for data science"),
                _highlight(id=300, text="JavaScript is also nice"),
            ]
        )
        result = runner.invoke(
            app,
            ["tags", "auto-tag", "--pattern", "python", "--tag", "python"],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "2 highlights" in result.output
        assert "without --dry-run" in result.output

    @respx.mock
    def test_auto_tag_no_matches(self) -> None:
        """tags auto-tag reports when no highlights match."""
        _mock_v2_highlights([_highlight(id=1, text="Nothing matching here")])
        result = runner.invoke(
            app,
            ["tags", "auto-tag", "--pattern", "nomatch", "--tag", "test"],
        )
        assert result.exit_code == 0
        assert "No highlights matched" in result.output

    @respx.mock
    def test_auto_tag_many_results(self) -> None:
        """tags auto-tag truncates output for many results."""
        _mock_v2_highlights([_highlight(id=i, text=f"test content {i}") for i in range(15)])
        result = runner.invoke(
            app,
            ["tags", "auto-tag", "--pattern", "test", "--tag", "tag"],
        )
        assert result.exit_code == 0
        assert "15 highlights" in result.output
        assert "5 more" in result.output


class TestTagMutationCommands:
    """Tests for tags rename, merge, and delete (dry-run) commands.

    These commands share the same structure: dry-run by default, show match
    counts, show a hint to re-run without --dry-run, and handle no-matches.
    """

    @respx.mock
    @pytest.mark.parametrize(
        ("cli_args", "expected_count"),
        [
            (["tags", "rename", "old-tag", "new-tag"], "3 highlights"),
            (["tags", "delete", "old-tag"], "3 highlights"),
            (["tags", "merge", "tag1,tag2", "--into", "merged"], "2 highlights"),
        ],
        ids=["rename", "delete", "merge"],
    )
    def test_dry_run_with_matches(self, cli_args: list[str], expected_count: str) -> None:
        """Mutation commands show DRY RUN, match count, and hint."""
        if "merge" in cli_args:
            _mock_v2_highlights(
                [
                    _highlight(id=1, text="H1", tags=[Tag(id=10, name="tag1")]),
                    _highlight(id=2, text="H2", tags=[Tag(id=20, name="tag2")]),
                    _highlight(id=3, text="H3", tags=[Tag(id=30, name="other")]),
                ]
            )
        else:
            _mock_v2_highlights(
                [
                    _highlight(id=1, text="H1", tags=[Tag(id=10, name="old-tag")]),
                    _highlight(id=2, text="H2", tags=[Tag(id=10, name="old-tag")]),
                    _highlight(id=3, text="H3", tags=[Tag(id=10, name="old-tag")]),
                    _highlight(id=4, text="H4", tags=[Tag(id=20, name="other")]),
                ]
            )
        result = runner.invoke(app, cli_args)
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert expected_count in result.output
        assert "would be" in result.output
        assert "without --dry-run" in result.output

    @respx.mock
    @pytest.mark.parametrize(
        "cli_args",
        [
            ["tags", "rename", "nonexistent", "new-name"],
            ["tags", "delete", "nonexistent"],
            ["tags", "merge", "nonexistent", "--into", "target"],
        ],
        ids=["rename", "delete", "merge"],
    )
    def test_no_matches(self, cli_args: list[str]) -> None:
        """Mutation commands report when no highlights have the tag."""
        _mock_v2_highlights(
            [
                _highlight(id=1, text="H1", tags=[Tag(id=10, name="other")]),
            ]
        )
        result = runner.invoke(app, cli_args)
        assert result.exit_code == 0
        assert "No highlights found" in result.output

    def test_merge_tags_missing_into(self) -> None:
        """tags merge fails when --into is not provided."""
        result = runner.invoke(app, ["tags", "merge", "tag1,tag2"])
        assert result.exit_code != 0

    @respx.mock
    def test_delete_tag_many_results(self) -> None:
        """tags delete truncates output for many results."""
        _mock_v2_highlights(
            [_highlight(id=i, text=f"H{i}", tags=[Tag(id=10, name="big-tag")]) for i in range(15)]
        )
        result = runner.invoke(app, ["tags", "delete", "big-tag"])
        assert result.exit_code == 0
        assert "15 highlights" in result.output
        assert "5 more" in result.output


class TestTagReportCommand:
    """Tests for the tags report command."""

    @respx.mock
    def test_tag_report_table(self) -> None:
        """tags report outputs a table by default."""
        highlights = [
            *[
                _highlight(id=100 + i, text=f"py-{i}", tags=[Tag(id=1, name="python")])
                for i in range(8)
            ],
            *[
                _highlight(id=200 + i, text=f"code-{i}", tags=[Tag(id=2, name="coding")])
                for i in range(6)
            ],
            *[
                _highlight(id=300 + i, text=f"ai-{i}", tags=[Tag(id=3, name="ai")])
                for i in range(4)
            ],
            *[
                _highlight(id=400 + i, text=f"ml-{i}", tags=[Tag(id=4, name="ml")])
                for i in range(2)
            ],
        ]
        _mock_v2_highlights(highlights)
        result = runner.invoke(app, ["tags", "report"])
        assert result.exit_code == 0
        assert "Tag Report" in result.output
        assert "Total Tags: 4" in result.output
        assert "Total Usages: 20" in result.output
        assert "python" in result.output

    @respx.mock
    def test_tag_report_json(self) -> None:
        """tags report --json outputs JSON."""
        _mock_v2_highlights(
            [
                _highlight(
                    id=1,
                    text="H1",
                    tags=[Tag(id=1, name="python"), Tag(id=2, name="coding")],
                ),
                _highlight(
                    id=2,
                    text="H2",
                    tags=[Tag(id=1, name="python"), Tag(id=3, name="ai")],
                ),
                _highlight(id=3, text="H3", tags=[Tag(id=2, name="coding")]),
                _highlight(id=4, text="H4", tags=[Tag(id=1, name="python")]),
                _highlight(id=5, text="H5", tags=[Tag(id=3, name="ai")]),
            ]
        )
        result = runner.invoke(app, ["tags", "report", "--json"])
        assert result.exit_code == 0
        data = _extract_json(result.output)
        assert data["summary"]["total_tags"] == 3
        assert data["summary"]["total_usages"] == 7
        assert len(data["top_tags"]) == 3

    @respx.mock
    def test_tag_report_no_data(self) -> None:
        """tags report handles empty data."""
        _mock_v2_highlights([])
        result = runner.invoke(app, ["tags", "report"])
        assert result.exit_code == 0
        assert "Total Tags: 0" in result.output


# ---------------------------------------------------------------------------
# No-args-is-help behaviour
# ---------------------------------------------------------------------------


class TestNoArgsHelp:
    """Tests that the app shows help when no args are provided."""

    def test_no_args_shows_help(self) -> None:
        """Running the app with no arguments shows help (exit code 0 or 2)."""
        result = runner.invoke(app, [])
        assert result.exit_code in (0, 2)
        assert "Readwise SDK CLI" in result.output or "Usage" in result.output

    @pytest.mark.parametrize(
        "subcommand",
        ["highlights", "books", "reader", "sync", "digest", "tags"],
    )
    def test_subcommand_no_args_shows_help(self, subcommand: str) -> None:
        """Sub-apps with no args show help (exit code 0 or 2)."""
        result = runner.invoke(app, [subcommand])
        assert result.exit_code in (0, 2)
        assert "Usage" in result.output or subcommand in result.output
