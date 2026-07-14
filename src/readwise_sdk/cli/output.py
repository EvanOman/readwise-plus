"""Shared rendering for CLI human and machine output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import click
from rich.console import Console
from rich.table import Table


class OutputFormat(StrEnum):
    """Supported global CLI output formats."""

    TABLE = "table"
    JSON = "json"
    JSONL = "jsonl"


@dataclass(frozen=True, slots=True)
class CliOutputContext:
    """Output selection stored on the root Click context."""

    output_format: OutputFormat = OutputFormat.TABLE


console = Console()
error_console = Console(stderr=True)


def current_output_format() -> OutputFormat:
    """Return the output mode selected on the root CLI invocation."""
    context = click.get_current_context(silent=True)
    if context is None:
        return OutputFormat.TABLE
    root = context.find_root()
    if isinstance(root.obj, CliOutputContext):
        return root.obj.output_format
    return OutputFormat.TABLE


class OutputRenderer:
    """Render adapter-owned values without owning operation semantics."""

    def __init__(
        self,
        output_format: OutputFormat | None = None,
        *,
        legacy_json: bool = False,
    ) -> None:
        self.output_format = output_format or current_output_format()
        self.legacy_json = legacy_json

    def data(self, value: Any) -> None:
        """Write structured data according to the selected machine format."""
        if self.output_format is OutputFormat.JSONL:
            values = value if isinstance(value, list) else [value]
            for item in values:
                click.echo(json.dumps(item, separators=(",", ":")))
            return
        serialized = json.dumps(value, indent=2)
        if self.legacy_json:
            console.print(serialized)
        else:
            click.echo(serialized)

    def table(self, table: Table) -> None:
        """Write a Rich table using the legacy console configuration."""
        console.print(table)

    def message(self, message: str) -> None:
        """Write human-facing command output with legacy Rich behavior."""
        console.print(message)

    def error(self, message: str) -> None:
        """Keep legacy errors on stdout, but isolate machine-mode errors."""
        target = console if self.output_format is OutputFormat.TABLE else error_console
        target.print(message)


def renderer(*, legacy_json: bool = False) -> OutputRenderer:
    """Return a renderer, preserving a command-local legacy ``--json`` flag."""
    output_format = OutputFormat.JSON if legacy_json else current_output_format()
    return OutputRenderer(output_format, legacy_json=legacy_json)


__all__ = [
    "CliOutputContext",
    "OutputFormat",
    "OutputRenderer",
    "console",
    "current_output_format",
    "error_console",
    "renderer",
]
