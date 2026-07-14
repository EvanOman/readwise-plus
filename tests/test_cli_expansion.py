"""Contracts for the additive PR 12 CLI commands and global options."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from typer.testing import CliRunner

from readwise_sdk.cli.main import app
from readwise_sdk.models import BulkResult
from readwise_sdk.operations.highlights import HighlightCreateResult
from readwise_sdk.v2.models import Highlight, HighlightColor
from readwise_sdk.v3.models import (
    CreateDocumentResult,
    Document,
    DocumentCategory,
    DocumentLocation,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READWISE_API_KEY", "token")


def _operation_runner(service: Any):
    def run(operation, *, api_key: str | None = None):
        assert api_key == "token"

        async def invoke():
            return await operation(service)

        return anyio.run(invoke)

    return run


class DocumentOperations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.document = Document(
            id="doc-1",
            url="https://example.com/article",
            title="An article",
            author="Ada",
            category=DocumentCategory.ARTICLE,
            location=DocumentLocation.NEW,
            tags=["python"],
            content="<p>Full text</p>",
        )
        self.result = CreateDocumentResult(id="doc-1", url=self.document.url)

    async def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return self.document

    async def update(self, *args, **kwargs):
        self.calls.append(("update", args, kwargs))
        return self.result

    async def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))

    async def move(self, *args, **kwargs):
        self.calls.append(("move", args, kwargs))
        return self.result

    async def add_tag(self, *args, **kwargs):
        self.calls.append(("add_tag", args, kwargs))
        return self.result

    async def save(self, *args, **kwargs):
        self.calls.append(("save", args, kwargs))
        return self.result

    async def inbox(self, *args, **kwargs):
        self.calls.append(("inbox", args, kwargs))
        return [self.document]


class HighlightOperations:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.highlight = Highlight(
            id=7,
            text="A useful highlight",
            note="Remember this",
            location=4,
            color=HighlightColor.YELLOW,
        )

    async def create_from_fields(self, *args, **kwargs):
        self.calls.append(("create_from_fields", args, kwargs))
        return HighlightCreateResult(ids=[7])

    async def update(self, *args, **kwargs):
        self.calls.append(("update", args, kwargs))
        return self.highlight

    async def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))

    async def bulk_tag(self, *args, **kwargs):
        self.calls.append(("bulk_tag", args, kwargs))
        return BulkResult[int](succeeded=[7])

    async def bulk_untag(self, *args, **kwargs):
        self.calls.append(("bulk_untag", args, kwargs))
        return BulkResult[int](succeeded=[7])


DOCUMENT_CASES = [
    (["documents", "get", "doc-1", "--with-content"], "get"),
    (["documents", "update", "doc-1", "--title", "Revised"], "update"),
    (["documents", "delete", "doc-1"], "delete"),
    (["documents", "move", "doc-1", "archive"], "move"),
    (["documents", "tag", "doc-1", "research"], "add_tag"),
]


HIGHLIGHT_CASES = [
    (["highlights", "create", "New insight", "--title", "Source"], "create_from_fields"),
    (["highlights", "update", "7", "--note", "Revised note"], "update"),
    (["highlights", "delete", "7"], "delete"),
    (["highlights", "tag", "7", "favorite"], "bulk_tag"),
    (["highlights", "untag", "7", "favorite"], "bulk_untag"),
]


@pytest.mark.parametrize(("arguments", "expected_operation"), DOCUMENT_CASES)
@pytest.mark.parametrize("output_format", ["table", "json", "jsonl"])
def test_each_new_document_command_calls_one_operation_and_renders_requested_output(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected_operation: str,
    output_format: str,
) -> None:
    from readwise_sdk.cli.commands import documents as commands

    operations = DocumentOperations()
    service = SimpleNamespace(documents=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))
    cli_arguments = arguments
    if output_format != "table":
        cli_arguments = ["--output", output_format, *arguments]

    result = runner.invoke(app, cli_arguments)

    assert result.exit_code == 0, result.output
    assert [call[0] for call in operations.calls] == [expected_operation]
    assert result.stdout
    assert result.stderr == ""
    if output_format == "json":
        assert isinstance(json.loads(result.stdout), dict)
    elif output_format == "jsonl":
        lines = result.stdout.splitlines()
        assert len(lines) == 1
        assert isinstance(json.loads(lines[0]), dict)


@pytest.mark.parametrize(("arguments", "expected_operation"), HIGHLIGHT_CASES)
@pytest.mark.parametrize("output_format", ["table", "json", "jsonl"])
def test_each_new_highlight_command_calls_one_operation_and_renders_requested_output(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected_operation: str,
    output_format: str,
) -> None:
    from readwise_sdk.cli.commands import highlights as commands

    operations = HighlightOperations()
    service = SimpleNamespace(highlights=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))
    cli_arguments = arguments
    if output_format != "table":
        cli_arguments = ["--output", output_format, *arguments]

    result = runner.invoke(app, cli_arguments)

    assert result.exit_code == 0, result.output
    assert [call[0] for call in operations.calls] == [expected_operation]
    assert result.stdout
    assert result.stderr == ""
    if output_format == "json":
        assert isinstance(json.loads(result.stdout), dict)
    elif output_format == "jsonl":
        lines = result.stdout.splitlines()
        assert len(lines) == 1
        assert isinstance(json.loads(lines[0]), dict)


def test_documents_inbox_jsonl_streams_one_document_per_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from readwise_sdk.cli.commands import documents as commands

    operations = DocumentOperations()
    operations.document = operations.document.model_copy(update={"id": "doc-1"})
    second = operations.document.model_copy(update={"id": "doc-2"})

    async def inbox(*args, **kwargs):
        operations.calls.append(("inbox", args, kwargs))
        return [operations.document, second]

    operations.inbox = inbox  # type: ignore[method-assign]
    service = SimpleNamespace(documents=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    result = runner.invoke(app, ["--output", "jsonl", "documents", "inbox"])

    assert result.exit_code == 0
    assert [json.loads(line)["id"] for line in result.stdout.splitlines()] == ["doc-1", "doc-2"]
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "expected_operation"),
    [
        (["reader", "inbox"], "inbox"),
        (["reader", "save", "https://example.com/article"], "save"),
        (["reader", "archive", "doc-1"], "move"),
    ],
)
def test_reader_aliases_warn_on_stderr_only_in_human_mode(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected_operation: str,
) -> None:
    from readwise_sdk.cli.commands import documents as commands

    operations = DocumentOperations()
    service = SimpleNamespace(documents=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0
    assert [call[0] for call in operations.calls] == [expected_operation]
    assert "deprecated" not in result.stdout.lower()
    assert "reader" in result.stderr.lower()
    assert "deprecated" in result.stderr.lower()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--output", "json", "reader", "inbox"],
        ["--output", "jsonl", "reader", "inbox"],
        ["reader", "inbox", "--json"],
    ],
)
def test_reader_alias_machine_output_has_no_deprecation_notice(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    from readwise_sdk.cli.commands import documents as commands

    operations = DocumentOperations()
    service = SimpleNamespace(documents=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0
    assert "deprecated" not in result.stdout.lower()
    assert result.stderr == ""


def test_books_list_jsonl_streams_one_book_per_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from readwise_sdk.cli.commands import books as commands
    from readwise_sdk.v2.models import Book

    class Operations:
        async def list(self, **kwargs):
            return [Book(id=1, title="One"), Book(id=2, title="Two")]

    service = SimpleNamespace(books=Operations())
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    result = runner.invoke(app, ["--output", "jsonl", "books", "list"])

    assert result.exit_code == 0
    assert [json.loads(line)["id"] for line in result.stdout.splitlines()] == [1, 2]
    assert result.stderr == ""


def test_quiet_suppresses_success_messages_but_still_runs_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from readwise_sdk.cli.commands import documents as commands

    operations = DocumentOperations()
    service = SimpleNamespace(documents=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    result = runner.invoke(app, ["--quiet", "documents", "delete", "doc-1"])

    assert result.exit_code == 0
    assert [call[0] for call in operations.calls] == ["delete"]
    assert result.stdout == ""
    assert result.stderr == ""


def test_no_color_removes_ansi_codes_from_human_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from readwise_sdk.cli.commands import documents as commands

    operations = DocumentOperations()
    service = SimpleNamespace(documents=operations)
    monkeypatch.setattr(commands, "run_operation", _operation_runner(service))

    result = runner.invoke(
        app,
        ["--no-color", "documents", "delete", "doc-1"],
        color=True,
    )

    assert result.exit_code == 0
    assert "Deleted document doc-1" in result.stdout
    assert "\x1b[" not in result.stdout
    assert "\x1b[" not in result.stderr
