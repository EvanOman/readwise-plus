"""Highlight CLI commands backed by canonical operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer
from rich.table import Table

from readwise_sdk.cli.context import discover_api_key, run_operation
from readwise_sdk.cli.output import OutputFormat, renderer
from readwise_sdk.models import BulkResult
from readwise_sdk.v2.models import Highlight, HighlightColor, HighlightUpdate
from readwise_sdk.workflows.digest import DigestBuilder, DigestFormat

highlights_app = typer.Typer(help="Manage highlights")


def _highlight_data(highlights: list, *, truncate: bool) -> list[dict]:
    return [
        {
            "id": highlight.id,
            "text": highlight.text[:100] + "..."
            if truncate and len(highlight.text) > 100
            else highlight.text,
            "note": highlight.note,
        }
        for highlight in highlights
    ]


def _highlight_detail(highlight: Highlight) -> dict:
    return {
        "id": highlight.id,
        "text": highlight.text,
        "note": highlight.note,
        "location": highlight.location,
        "location_type": highlight.location_type,
        "url": highlight.url,
        "color": highlight.color.value if highlight.color else None,
        "tags": [tag.name for tag in highlight.tags],
        "highlighted_at": highlight.highlighted_at.isoformat()
        if highlight.highlighted_at
        else None,
    }


def _bulk_data(result: BulkResult[int]) -> dict:
    return {
        "succeeded": result.succeeded,
        "failures": [{"id": failure.item, "error": failure.message} for failure in result.failures],
    }


@highlights_app.command("list")
def list_highlights(
    limit: Annotated[int, typer.Option(help="Maximum number of highlights")] = 20,
    book_id: Annotated[int | None, typer.Option(help="Filter by book ID")] = None,
    days: Annotated[int | None, typer.Option(help="Only show highlights from last N days")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List highlights."""
    api_key = discover_api_key()
    since = datetime.now(UTC) - timedelta(days=days) if days else None
    highlights = run_operation(
        lambda service: service.highlights.list(
            book_id=book_id,
            updated_after=since,
            limit=limit,
        ),
        api_key=api_key,
    )

    output = renderer(legacy_json=json_output)
    if output.output_format is not OutputFormat.TABLE:
        output.data(_highlight_data(highlights, truncate=json_output))
        return

    table = Table(title=f"Highlights ({len(highlights)} shown)")
    table.add_column("ID", style="cyan")
    table.add_column("Text", max_width=60)
    table.add_column("Note", max_width=30)

    for highlight in highlights:
        text = highlight.text[:57] + "..." if len(highlight.text) > 60 else highlight.text
        note = (
            highlight.note[:27] + "..."
            if highlight.note and len(highlight.note) > 30
            else highlight.note
        ) or ""
        table.add_row(str(highlight.id), text, note)

    output.table(table)


@highlights_app.command("show")
def show_highlight(
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID")],
) -> None:
    """Show a single highlight."""
    api_key = discover_api_key()
    output = renderer()
    try:
        highlight = run_operation(
            lambda service: service.highlights.get(highlight_id),
            api_key=api_key,
        )

        if output.output_format is not OutputFormat.TABLE:
            output.data(
                {
                    "id": highlight.id,
                    "text": highlight.text,
                    "note": highlight.note,
                    "location": highlight.location,
                    "tags": [tag.name for tag in highlight.tags],
                    "highlighted_at": (
                        highlight.highlighted_at.isoformat() if highlight.highlighted_at else None
                    ),
                }
            )
            return

        output.message(f"[bold]ID:[/bold] {highlight.id}")
        output.message(f"[bold]Text:[/bold] {highlight.text}")
        if highlight.note:
            output.message(f"[bold]Note:[/bold] {highlight.note}")
        if highlight.location:
            output.message(f"[bold]Location:[/bold] {highlight.location}")
        if highlight.tags:
            tag_names = ", ".join(tag.name for tag in highlight.tags)
            output.message(f"[bold]Tags:[/bold] {tag_names}")
        if highlight.highlighted_at:
            output.message(f"[bold]Highlighted:[/bold] {highlight.highlighted_at}")
    except Exception as error:
        output.error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None


@highlights_app.command("export")
def export_highlights(
    format_type: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "markdown",
    output: Annotated[str | None, typer.Option("-o", help="Output file")] = None,
    days: Annotated[
        int | None, typer.Option(help="Only export highlights from last N days")
    ] = None,
) -> None:
    """Export highlights to a file."""
    api_key = discover_api_key()
    command_output = renderer()
    try:
        fmt = DigestFormat(format_type)
    except ValueError:
        command_output.error("[red]Invalid format. Use: markdown, json, csv, text[/red]")
        raise typer.Exit(1) from None

    since = datetime.now(UTC) - timedelta(days=days) if days else None
    highlights = run_operation(
        lambda service: service.highlights.list(updated_after=since),
        api_key=api_key,
    )

    # Stage 13 moves digest presentation. Reuse the legacy formatter here so this
    # adapter changes only data acquisition and preserves every output byte.
    formatter = DigestBuilder.__new__(DigestBuilder)
    content = formatter._format_digest(
        highlights,
        title="Custom Digest",
        output_format=fmt,
        group_by_book=True,
        group_by_date=False,
    )

    if output:
        with open(output, "w") as file:
            file.write(content)
        command_output.message(f"[green]Exported to {output}[/green]")
    else:
        command_output.message(content)


@highlights_app.command("create")
def create_highlight(
    text: Annotated[str, typer.Argument(help="Highlight text")],
    title: Annotated[str | None, typer.Option(help="Source title")] = None,
    author: Annotated[str | None, typer.Option(help="Source author")] = None,
    source_url: Annotated[
        str | None,
        typer.Option("--source-url", help="Source URL"),
    ] = None,
    note: Annotated[str | None, typer.Option(help="Highlight note")] = None,
    category: Annotated[str | None, typer.Option(help="Source category")] = None,
) -> None:
    """Create one highlight."""
    api_key = discover_api_key()
    output = renderer()
    try:
        result = run_operation(
            lambda service: service.highlights.create_from_fields(
                text=text,
                title=title,
                author=author,
                source_url=source_url,
                note=note,
                category=category,
            ),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    data = {
        "ids": result.ids,
        "was_truncated": result.was_truncated,
    }
    if output.output_format is not OutputFormat.TABLE:
        output.data(data)
        return
    ids = ", ".join(str(highlight_id) for highlight_id in result.ids)
    output.success(f"[green]Created highlight {ids}[/green]")


@highlights_app.command("update")
def update_highlight(
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID")],
    text: Annotated[str | None, typer.Option(help="Replacement text")] = None,
    note: Annotated[str | None, typer.Option(help="Replacement note")] = None,
    location: Annotated[int | None, typer.Option(help="Replacement location")] = None,
    location_type: Annotated[
        str | None,
        typer.Option("--location-type", help="Replacement location type"),
    ] = None,
    url: Annotated[str | None, typer.Option(help="Replacement URL")] = None,
    color: Annotated[HighlightColor | None, typer.Option(help="Highlight color")] = None,
) -> None:
    """Update one highlight."""
    api_key = discover_api_key()
    output = renderer()
    update = HighlightUpdate(
        text=text,
        note=note,
        location=location,
        location_type=location_type,
        url=url,
        color=color,
    )
    try:
        highlight = run_operation(
            lambda service: service.highlights.update(highlight_id, update),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if output.output_format is not OutputFormat.TABLE:
        output.data(_highlight_detail(highlight))
        return
    output.success(f"[green]Updated highlight {highlight_id}[/green]")


@highlights_app.command("delete")
def delete_highlight(
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID")],
) -> None:
    """Permanently delete one highlight."""
    api_key = discover_api_key()
    output = renderer()
    try:
        run_operation(
            lambda service: service.highlights.delete(highlight_id),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if output.output_format is not OutputFormat.TABLE:
        output.data({"id": highlight_id, "deleted": True})
        return
    output.success(f"[green]Deleted highlight {highlight_id}[/green]")


def _render_bulk_tag_result(
    result: BulkResult[int],
    *,
    tag: str,
    action: str,
) -> None:
    output = renderer()
    if output.output_format is not OutputFormat.TABLE:
        output.data(_bulk_data(result))
    else:
        for highlight_id in result.succeeded:
            output.success(f"[green]{action} highlight {highlight_id} with {tag}[/green]")
        for failure in result.failures:
            output.strict_error(f"[red]Error for highlight {failure.item}: {failure.message}[/red]")
    if result.failures:
        raise typer.Exit(4)


@highlights_app.command("tag")
def tag_highlight(
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID")],
    tag: Annotated[str, typer.Argument(help="Tag to add")],
) -> None:
    """Add one tag to a highlight."""
    api_key = discover_api_key()
    try:
        result = run_operation(
            lambda service: service.highlights.bulk_tag([highlight_id], tag),
            api_key=api_key,
        )
    except Exception as error:
        renderer().strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None
    _render_bulk_tag_result(result, tag=tag, action="Tagged")


@highlights_app.command("untag")
def untag_highlight(
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID")],
    tag: Annotated[str, typer.Argument(help="Tag to remove")],
) -> None:
    """Remove one tag from a highlight."""
    api_key = discover_api_key()
    try:
        result = run_operation(
            lambda service: service.highlights.bulk_untag([highlight_id], tag),
            api_key=api_key,
        )
    except Exception as error:
        renderer().strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None
    _render_bulk_tag_result(result, tag=tag, action="Untagged")


__all__ = ["highlights_app"]
