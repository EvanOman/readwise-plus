"""Characterize representative CLI output, streams, statuses, and JSON."""

from __future__ import annotations

import importlib
import re
from importlib.metadata import version

import httpx
import pytest
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, READWISE_API_V3_BASE

pytest.importorskip("typer")
pytest.importorskip("rich")
typer_testing = importlib.import_module("typer.testing")
app = importlib.import_module("readwise_sdk.cli.main").app

runner = typer_testing.CliRunner()


def test_version_writes_exact_stdout_and_no_stderr() -> None:
    """The version command is a clean successful stdout-only command."""
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout == f"readwise-plus v{version('readwise-plus')}\n"
    assert result.stderr == ""


@respx.mock
def test_highlights_json_has_exact_structure_and_stdout_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Highlight JSON includes null note and is emitted only on stdout."""
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

    result = runner.invoke(app, ["highlights", "list", "--json"])

    assert result.exit_code == 0
    assert result.stdout == (
        '[\n  {\n    "id": 7,\n    "text": "Exact text",\n    "note": null\n  }\n]\n'
    )
    assert result.stderr == ""


@respx.mock
def test_reader_inbox_json_has_exact_structure_and_stdout_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reader JSON retains null fields and the documented key ordering."""
    monkeypatch.setenv("READWISE_API_KEY", "token")
    respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "doc-1",
                        "url": "https://example.com/article",
                        "title": None,
                        "category": None,
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )

    result = runner.invoke(app, ["reader", "inbox", "--json"])

    assert result.exit_code == 0
    assert result.stdout == (
        "[\n"
        "  {\n"
        '    "id": "doc-1",\n'
        '    "title": null,\n'
        '    "url": "https://example.com/article",\n'
        '    "category": null\n'
        "  }\n"
        "]\n"
    )
    assert result.stderr == ""


def test_missing_api_key_is_an_exit_one_message_on_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Application-level configuration errors currently use stdout."""
    monkeypatch.delenv("READWISE_API_KEY", raising=False)

    result = runner.invoke(app, ["highlights", "list"])

    assert result.exit_code == 1
    assert result.stdout == "Error: READWISE_API_KEY environment variable not set\n"
    assert result.stderr == ""


def test_invalid_book_category_is_an_exit_one_message_on_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Command validation performed inside the handler currently uses stdout."""
    monkeypatch.setenv("READWISE_API_KEY", "token")

    result = runner.invoke(app, ["books", "list", "--category", "invalid"])

    assert result.exit_code == 1
    assert result.stdout == "Invalid category. Use: books, articles, tweets, podcasts\n"
    assert result.stderr == ""


def test_typer_parse_error_is_exit_two_and_routed_to_stderr() -> None:
    """Framework-level argument errors differ from application errors."""
    result = runner.invoke(app, ["highlights", "list", "--bad-option"])
    # Strip ANSI so the assertion holds whether or not the runner forces color
    # (GitHub Actions enables it; a plain terminal does not).
    stderr = re.sub(r"\x1b\[[0-9;]*m", "", result.stderr)

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "No such option: --bad-option" in stderr
    assert "Usage: readwise highlights list [OPTIONS]" in stderr
