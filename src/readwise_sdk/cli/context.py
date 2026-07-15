"""CLI credential discovery and service lifecycle."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

import anyio
import typer

from readwise_sdk.cli.output import OutputFormat, console, current_output_format, error_console
from readwise_sdk.client import ReadwiseClient
from readwise_sdk.sdk.async_ import AsyncReadwise


def discover_api_key() -> str:
    """Return the configured API key or preserve the legacy CLI failure."""
    api_key = os.environ.get("READWISE_API_KEY")
    if api_key:
        return api_key

    message = "[red]Error: READWISE_API_KEY environment variable not set[/red]"
    if current_output_format() is OutputFormat.TABLE:
        # Characterizes current behavior: this application error is on stdout.
        console.print(message)
    else:
        error_console.print(message)
    raise typer.Exit(1)


def get_client() -> ReadwiseClient:
    """Return the legacy client for untouched commands and import compatibility."""
    return ReadwiseClient(api_key=discover_api_key())


def run_operation[ResultT](
    operation: Callable[[AsyncReadwise], Awaitable[ResultT]],
    *,
    api_key: str | None = None,
) -> ResultT:
    """Run exactly one operation inside an owned async service lifecycle."""
    resolved_api_key = api_key or discover_api_key()

    async def invoke() -> ResultT:
        async with AsyncReadwise(api_key=resolved_api_key) as service:
            return await operation(service)

    return anyio.run(invoke)


__all__ = ["discover_api_key", "get_client", "run_operation"]
