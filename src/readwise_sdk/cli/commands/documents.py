"""Reader document CLI commands backed by canonical operations."""

from __future__ import annotations

from typing import Annotated

import click
import typer
from rich.table import Table

from readwise_sdk.cli.context import discover_api_key, run_operation
from readwise_sdk.cli.output import OutputFormat, OutputRenderer, renderer
from readwise_sdk.v3.models import (
    Document,
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentUpdate,
)

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


def _document_detail(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "author": document.author,
        "url": document.source_url or document.url,
        "category": document.category.value if document.category else None,
        "location": document.location.value if document.location else None,
        "tags": document.tags,
        "summary": document.summary,
        "notes": document.notes,
        "content": document.content,
    }


def _result_data(result) -> dict:
    return {"id": result.id, "url": result.url}


def _warn_reader_alias(output: OutputRenderer) -> None:
    """Warn only for the human-facing deprecated group alias."""
    context = click.get_current_context(silent=True)
    parent = context.parent if context is not None else None
    if (
        parent is not None
        and parent.info_name == "reader"
        and output.output_format is OutputFormat.TABLE
    ):
        output.notice(
            "[yellow]Warning: 'readwise reader' is deprecated; "
            "use 'readwise documents' instead.[/yellow]"
        )


@reader_app.command("inbox")
def reader_inbox(
    limit: Annotated[int, typer.Option(help="Maximum number of items")] = 20,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List inbox documents."""
    api_key = discover_api_key()
    output = renderer(legacy_json=json_output)
    _warn_reader_alias(output)
    documents = run_operation(
        lambda service: service.documents.inbox(limit=limit),
        api_key=api_key,
    )

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
    _warn_reader_alias(output)
    try:
        result = run_operation(
            lambda service: service.documents.save(DocumentCreate(url=url)),
            api_key=api_key,
        )

        if output.output_format is not OutputFormat.TABLE:
            output.data({"id": result.id, "url": result.url})
            return
        output.success("[green]Saved![/green]")
        output.success(f"[bold]ID:[/bold] {result.id}")
        output.success(f"[bold]URL:[/bold] {result.url}")
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
    _warn_reader_alias(output)
    try:
        result = run_operation(
            lambda service: service.documents.move(document_id, DocumentLocation.ARCHIVE),
            api_key=api_key,
        )

        if output.output_format is not OutputFormat.TABLE:
            output.data({"id": result.id, "url": result.url})
            return
        output.success(f"[green]Archived document {document_id}[/green]")
    except Exception as error:
        output.error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None


@reader_app.command("stats")
def reader_stats() -> None:
    """Show reading queue statistics."""
    api_key = discover_api_key()
    output = renderer()
    _warn_reader_alias(output)
    stats = run_operation(
        lambda service: service.documents.statistics(),
        api_key=api_key,
    )

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


@reader_app.command("get")
def get_document(
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    with_content: Annotated[
        bool,
        typer.Option("--with-content", help="Include document HTML content"),
    ] = False,
) -> None:
    """Get one Reader document."""
    api_key = discover_api_key()
    output = renderer()
    _warn_reader_alias(output)
    try:
        document = run_operation(
            lambda service: service.documents.get(document_id, with_content=with_content),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if document is None:
        output.strict_error(f"[red]Document {document_id} not found[/red]")
        raise typer.Exit(3)
    if output.output_format is not OutputFormat.TABLE:
        output.data(_document_detail(document))
        return

    output.message(f"[bold]ID:[/bold] {document.id}")
    output.message(f"[bold]Title:[/bold] {document.title or ''}")
    output.message(f"[bold]URL:[/bold] {document.source_url or document.url}")
    if document.author:
        output.message(f"[bold]Author:[/bold] {document.author}")
    if document.category:
        output.message(f"[bold]Category:[/bold] {document.category.value}")
    if document.location:
        output.message(f"[bold]Location:[/bold] {document.location.value}")
    if document.tags:
        output.message(f"[bold]Tags:[/bold] {', '.join(document.tags)}")
    if with_content and document.content:
        output.message(f"[bold]Content:[/bold] {document.content}")


@reader_app.command("update")
def update_document(
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    title: Annotated[str | None, typer.Option(help="New title")] = None,
    author: Annotated[str | None, typer.Option(help="New author")] = None,
    summary: Annotated[str | None, typer.Option(help="New summary")] = None,
    category: Annotated[DocumentCategory | None, typer.Option(help="New category")] = None,
    tags: Annotated[
        str | None,
        typer.Option(help="Comma-separated replacement tags"),
    ] = None,
    notes: Annotated[str | None, typer.Option(help="New document notes")] = None,
) -> None:
    """Update document metadata."""
    api_key = discover_api_key()
    output = renderer()
    _warn_reader_alias(output)
    replacement_tags = [tag.strip() for tag in tags.split(",")] if tags is not None else None
    update = DocumentUpdate(
        title=title,
        author=author,
        summary=summary,
        category=category,
        tags=replacement_tags,
        notes=notes,
    )
    try:
        result = run_operation(
            lambda service: service.documents.update(document_id, update),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if output.output_format is not OutputFormat.TABLE:
        output.data(_result_data(result))
        return
    output.success(f"[green]Updated document {document_id}[/green]")


@reader_app.command("delete")
def delete_document(
    document_id: Annotated[str, typer.Argument(help="Document ID")],
) -> None:
    """Permanently delete a Reader document."""
    api_key = discover_api_key()
    output = renderer()
    _warn_reader_alias(output)
    try:
        run_operation(
            lambda service: service.documents.delete(document_id),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if output.output_format is not OutputFormat.TABLE:
        output.data({"id": document_id, "deleted": True})
        return
    output.success(f"[green]Deleted document {document_id}[/green]")


@reader_app.command("move")
def move_document(
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    location: Annotated[DocumentLocation, typer.Argument(help="New location")],
) -> None:
    """Move a document to another Reader location."""
    api_key = discover_api_key()
    output = renderer()
    _warn_reader_alias(output)
    try:
        result = run_operation(
            lambda service: service.documents.move(document_id, location),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if output.output_format is not OutputFormat.TABLE:
        output.data(_result_data(result))
        return
    output.success(f"[green]Moved document {document_id} to {location.value}[/green]")


@reader_app.command("tag")
def tag_document(
    document_id: Annotated[str, typer.Argument(help="Document ID")],
    tag: Annotated[str, typer.Argument(help="Tag to add")],
) -> None:
    """Add one tag to a Reader document."""
    api_key = discover_api_key()
    output = renderer()
    _warn_reader_alias(output)
    try:
        result = run_operation(
            lambda service: service.documents.add_tag(document_id, tag),
            api_key=api_key,
        )
    except Exception as error:
        output.strict_error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None

    if output.output_format is not OutputFormat.TABLE:
        output.data(_result_data(result))
        return
    output.success(f"[green]Tagged document {document_id} with {tag}[/green]")


documents_app = reader_app


__all__ = ["documents_app", "reader_app"]
