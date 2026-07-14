"""Reader document CLI commands backed by canonical operations."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from readwise_sdk.cli.context import discover_api_key, run_operation
from readwise_sdk.cli.output import OutputFormat, renderer
from readwise_sdk.v3.models import DocumentCreate, DocumentLocation

reader_app = typer.Typer(help="Manage Reader documents")


def _document_data(documents: list) -> list[dict]:
    return [
        {
            "id": document.id,
            "title": document.title,
            "url": document.url,
            "category": document.category.value if document.category else None,
        }
        for document in documents
    ]


@reader_app.command("inbox")
def reader_inbox(
    limit: Annotated[int, typer.Option(help="Maximum number of items")] = 20,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List inbox documents."""
    api_key = discover_api_key()
    documents = run_operation(
        lambda service: service.documents.inbox(limit=limit),
        api_key=api_key,
    )

    output = renderer(legacy_json=json_output)
    if output.output_format is not OutputFormat.TABLE:
        output.data(_document_data(documents))
        return

    table = Table(title=f"Inbox ({len(documents)} shown)")
    table.add_column("ID", style="cyan", max_width=15)
    table.add_column("Title", max_width=40)
    table.add_column("Category")

    for document in documents:
        title = (
            document.title[:37] + "..."
            if document.title and len(document.title) > 40
            else document.title
        ) or ""
        category = document.category.value if document.category else ""
        table.add_row(document.id[:15], title, category)

    output.table(table)


@reader_app.command("save")
def reader_save(
    url: Annotated[str, typer.Argument(help="URL to save")],
) -> None:
    """Save a URL to Reader."""
    api_key = discover_api_key()
    output = renderer()
    try:
        result = run_operation(
            lambda service: service.documents.save(DocumentCreate(url=url)),
            api_key=api_key,
        )

        if output.output_format is not OutputFormat.TABLE:
            output.data({"id": result.id, "url": result.url})
            return
        output.message("[green]Saved![/green]")
        output.message(f"[bold]ID:[/bold] {result.id}")
        output.message(f"[bold]URL:[/bold] {result.url}")
    except Exception as error:
        output.error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None


@reader_app.command("archive")
def reader_archive(
    document_id: Annotated[str, typer.Argument(help="Document ID to archive")],
) -> None:
    """Archive a document."""
    api_key = discover_api_key()
    output = renderer()
    try:
        result = run_operation(
            lambda service: service.documents.move(document_id, DocumentLocation.ARCHIVE),
            api_key=api_key,
        )

        if output.output_format is not OutputFormat.TABLE:
            output.data({"id": result.id, "url": result.url})
            return
        output.message(f"[green]Archived document {document_id}[/green]")
    except Exception as error:
        output.error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None


@reader_app.command("stats")
def reader_stats() -> None:
    """Show reading queue statistics."""
    api_key = discover_api_key()
    stats = run_operation(
        lambda service: service.documents.statistics(),
        api_key=api_key,
    )

    output = renderer()
    if output.output_format is not OutputFormat.TABLE:
        output.data(
            {
                "inbox_count": stats.inbox_count,
                "reading_list_count": stats.reading_list_count,
                "total_unread": stats.total_unread,
                "oldest_item_age_days": stats.oldest_item_age_days,
                "average_age_days": stats.average_age_days,
                "items_older_than_30_days": stats.items_older_than_30_days,
                "items_older_than_90_days": stats.items_older_than_90_days,
                "by_category": stats.by_category,
            }
        )
        return

    output.message("[bold]Reading Queue Statistics[/bold]")
    output.message(f"  Inbox: {stats.inbox_count}")
    output.message(f"  Reading List: {stats.reading_list_count}")
    output.message(f"  Total Unread: {stats.total_unread}")
    if stats.oldest_item_age_days is not None:
        output.message(f"  Oldest Item: {stats.oldest_item_age_days} days")
    if stats.average_age_days is not None:
        output.message(f"  Average Age: {stats.average_age_days:.1f} days")
    output.message(f"  Items > 30 days: {stats.items_older_than_30_days}")
    output.message(f"  Items > 90 days: {stats.items_older_than_90_days}")

    if stats.by_category:
        output.message("\n[bold]By Category:[/bold]")
        for category, count in sorted(stats.by_category.items(), key=lambda item: -item[1]):
            output.message(f"  {category}: {count}")


__all__ = ["reader_app"]
