"""Focused contracts for the restructured CLI shell."""

from __future__ import annotations

import json
from importlib.metadata import version
from types import SimpleNamespace
from typing import Any

import anyio
import httpx
import pytest
import respx
from typer.testing import CliRunner

from readwise_sdk.cli.main import app
from readwise_sdk.client import READWISE_API_V2_BASE
from readwise_sdk.operations import DocumentStatistics
from readwise_sdk.v2.models import Book, Highlight
from readwise_sdk.v3.models import CreateDocumentResult, Document

runner = CliRunner()


def test_global_json_output_renders_version_as_machine_data() -> None:
    """The new global output mode renders version data on stdout only."""
    result = runner.invoke(app, ["--output", "json", "version"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"version": version("readwise-plus")}
    assert result.stderr == ""


@respx.mock
def test_global_json_output_renders_highlight_list_without_legacy_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global JSON uses the existing highlight projection and stdout stream."""
    monkeypatch.setenv("READWISE_API_KEY", "token")
    respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [{"id": 7, "text": "Exact text", "note": None}],
                "next": None,
            },
        )
    )

    result = runner.invoke(app, ["--output", "json", "highlights", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"id": 7, "text": "Exact text", "note": None}]
    assert result.stderr == ""


@respx.mock
def test_global_machine_output_keeps_full_values_and_supports_jsonl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New machine modes avoid the legacy JSON truncation policy."""
    monkeypatch.setenv("READWISE_API_KEY", "token")
    full_text = "A" * 120
    respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"id": 1, "text": full_text, "note": None},
                    {"id": 2, "text": "second", "note": "note"},
                ],
                "next": None,
            },
        )
    )

    json_result = runner.invoke(app, ["--output", "json", "highlights", "list"])
    jsonl_result = runner.invoke(app, ["--output", "jsonl", "highlights", "list"])

    assert json.loads(json_result.stdout)[0]["text"] == full_text
    assert [json.loads(line)["id"] for line in jsonl_result.stdout.splitlines()] == [1, 2]


def test_machine_mode_routes_missing_credentials_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New machine modes reserve stdout for data."""
    monkeypatch.delenv("READWISE_API_KEY", raising=False)

    result = runner.invoke(app, ["--output", "json", "highlights", "list"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: READWISE_API_KEY environment variable not set\n"


def _operation_runner(service: Any):
    def run(operation, *, api_key: str | None = None):
        assert api_key == "token"

        async def invoke():
            return await operation(service)

        return anyio.run(invoke)

    return run


def test_highlight_commands_each_call_one_highlight_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every migrated highlight handler crosses the operation seam once."""
    from readwise_sdk.cli.commands import highlights as commands

    monkeypatch.setenv("READWISE_API_KEY", "token")
    calls: list[str] = []

    class Operations:
        async def list(self, **kwargs):
            calls.append("list")
            return [Highlight(id=1, text="Highlight")]

        async def get(self, highlight_id: int):
            calls.append("get")
            return Highlight(id=highlight_id, text="Highlight")

    service = SimpleNamespace(highlights=Operations())
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    for arguments, expected in (
        (["--output", "json", "highlights", "list"], "list"),
        (["--output", "json", "highlights", "show", "1"], "get"),
        (["highlights", "export"], "list"),
    ):
        calls.clear()
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0
        assert calls == [expected]


def test_book_commands_each_call_one_book_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every migrated book handler crosses the operation seam once."""
    from readwise_sdk.cli.commands import books as commands

    monkeypatch.setenv("READWISE_API_KEY", "token")
    calls: list[str] = []
    book = Book(id=1, title="Book")

    class Operations:
        async def list(self, **kwargs):
            calls.append("list")
            return [book]

        async def with_highlights(self, book_id: int):
            calls.append("with_highlights")
            return SimpleNamespace(book=book, highlights=[])

    service = SimpleNamespace(books=Operations())
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    for arguments, expected in (
        (["--output", "json", "books", "list"], "list"),
        (["--output", "json", "books", "show", "1"], "with_highlights"),
    ):
        calls.clear()
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0
        assert calls == [expected]


def test_document_commands_each_call_one_document_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every migrated Reader handler crosses the operation seam once."""
    from readwise_sdk.cli.commands import documents as commands

    monkeypatch.setenv("READWISE_API_KEY", "token")
    calls: list[str] = []
    document = Document(id="doc-1", url="https://example.com")
    create_result = CreateDocumentResult(id="doc-1", url="https://example.com")
    statistics = DocumentStatistics(
        inbox_count=1,
        reading_list_count=0,
        archive_count=0,
        total_count=1,
        total_unread=1,
        by_category={},
        oldest_inbox_item=document,
        newest_inbox_item=document,
        oldest_item_age_days=None,
        average_age_days=None,
        items_older_than_30_days=0,
        items_older_than_90_days=0,
    )

    class Operations:
        async def inbox(self, **kwargs):
            calls.append("inbox")
            return [document]

        async def save(self, request):
            calls.append("save")
            return create_result

        async def move(self, document_id, location):
            calls.append("move")
            return create_result

        async def statistics(self):
            calls.append("statistics")
            return statistics

    service = SimpleNamespace(documents=Operations())
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    for arguments, expected in (
        (["--output", "json", "reader", "inbox"], "inbox"),
        (["--output", "json", "reader", "save", "https://example.com"], "save"),
        (["--output", "json", "reader", "archive", "doc-1"], "move"),
        (["--output", "json", "reader", "stats"], "statistics"),
    ):
        calls.clear()
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0
        assert calls == [expected]
