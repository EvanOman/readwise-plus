"""Command-line interface for Readwise SDK."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Annotated

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("CLI dependencies not installed. Install with: pip install readwise-sdk[cli]")
    sys.exit(1)

from readwise_sdk.client import ReadwiseClient
from readwise_sdk.v2.models import BookCategory
from readwise_sdk.workflows.digest import DigestBuilder, DigestFormat

app = typer.Typer(
    name="readwise",
    help="Readwise SDK CLI - Manage your Readwise highlights and Reader documents",
    no_args_is_help=True,
)
console = Console()

# Sub-apps
highlights_app = typer.Typer(help="Manage highlights")
books_app = typer.Typer(help="Manage books")
reader_app = typer.Typer(help="Manage Reader documents")
sync_app = typer.Typer(help="Sync operations")
digest_app = typer.Typer(help="Generate digests")

app.add_typer(highlights_app, name="highlights")
app.add_typer(books_app, name="books")
app.add_typer(reader_app, name="reader")
app.add_typer(sync_app, name="sync")
app.add_typer(digest_app, name="digest")


def get_client() -> ReadwiseClient:
    """Get a configured Readwise client."""
    api_key = os.environ.get("READWISE_API_KEY")
    if not api_key:
        console.print("[red]Error: READWISE_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)
    return ReadwiseClient(api_key=api_key)


# Highlights commands
@highlights_app.command("list")
def list_highlights(
    limit: Annotated[int, typer.Option(help="Maximum number of highlights")] = 20,
    book_id: Annotated[int | None, typer.Option(help="Filter by book ID")] = None,
    days: Annotated[int | None, typer.Option(help="Only show highlights from last N days")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List highlights."""
    client = get_client()

    since = None
    if days:
        since = datetime.now(UTC) - timedelta(days=days)

    highlights = []
    for i, h in enumerate(client.v2.list_highlights(book_id=book_id, updated_after=since)):
        if i >= limit:
            break
        highlights.append(h)

    if json_output:
        data = [
            {
                "id": h.id,
                "text": h.text[:100] + "..." if len(h.text) > 100 else h.text,
                "note": h.note,
            }
            for h in highlights
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Highlights ({len(highlights)} shown)")
        table.add_column("ID", style="cyan")
        table.add_column("Text", max_width=60)
        table.add_column("Note", max_width=30)

        for h in highlights:
            text = h.text[:57] + "..." if len(h.text) > 60 else h.text
            note = (h.note[:27] + "..." if h.note and len(h.note) > 30 else h.note) or ""
            table.add_row(str(h.id), text, note)

        console.print(table)


@highlights_app.command("show")
def show_highlight(
    highlight_id: Annotated[int, typer.Argument(help="Highlight ID")],
) -> None:
    """Show a single highlight."""
    client = get_client()

    try:
        h = client.v2.get_highlight(highlight_id)
        console.print(f"[bold]ID:[/bold] {h.id}")
        console.print(f"[bold]Text:[/bold] {h.text}")
        if h.note:
            console.print(f"[bold]Note:[/bold] {h.note}")
        if h.location:
            console.print(f"[bold]Location:[/bold] {h.location}")
        if h.tags:
            tag_names = ", ".join(t.name for t in h.tags)
            console.print(f"[bold]Tags:[/bold] {tag_names}")
        if h.highlighted_at:
            console.print(f"[bold]Highlighted:[/bold] {h.highlighted_at}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
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
    client = get_client()
    builder = DigestBuilder(client)

    try:
        fmt = DigestFormat(format_type)
    except ValueError:
        console.print("[red]Invalid format. Use: markdown, json, csv, text[/red]")
        raise typer.Exit(1) from None

    if days:
        content = builder.create_custom_digest(
            since=datetime.now(UTC) - timedelta(days=days),
            output_format=fmt,
        )
    else:
        content = builder.create_custom_digest(output_format=fmt)

    if output:
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        console.print(content)


# Books commands
@books_app.command("list")
def list_books(
    limit: Annotated[int, typer.Option(help="Maximum number of books")] = 20,
    category: Annotated[str | None, typer.Option(help="Filter by category")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List books."""
    client = get_client()

    cat = None
    if category:
        try:
            cat = BookCategory(category)
        except ValueError:
            console.print("[red]Invalid category. Use: books, articles, tweets, podcasts[/red]")
            raise typer.Exit(1) from None

    books = []
    for i, b in enumerate(client.v2.list_books(category=cat)):
        if i >= limit:
            break
        books.append(b)

    if json_output:
        data = [
            {"id": b.id, "title": b.title, "author": b.author, "highlights": b.num_highlights}
            for b in books
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Books ({len(books)} shown)")
        table.add_column("ID", style="cyan")
        table.add_column("Title", max_width=40)
        table.add_column("Author", max_width=20)
        table.add_column("Highlights", justify="right")

        for b in books:
            title = b.title[:37] + "..." if len(b.title) > 40 else b.title
            author = (b.author[:17] + "..." if b.author and len(b.author) > 20 else b.author) or ""
            table.add_row(str(b.id), title, author, str(b.num_highlights))

        console.print(table)


@books_app.command("show")
def show_book(
    book_id: Annotated[int, typer.Argument(help="Book ID")],
) -> None:
    """Show a single book with its highlights."""
    client = get_client()

    try:
        b = client.v2.get_book(book_id)
        console.print(f"[bold]ID:[/bold] {b.id}")
        console.print(f"[bold]Title:[/bold] {b.title}")
        if b.author:
            console.print(f"[bold]Author:[/bold] {b.author}")
        if b.category:
            console.print(f"[bold]Category:[/bold] {b.category.value}")
        console.print(f"[bold]Highlights:[/bold] {b.num_highlights}")
        if b.source:
            console.print(f"[bold]Source:[/bold] {b.source}")

        # Show recent highlights
        highlights = list(client.v2.list_highlights(book_id=book_id))
        if highlights:
            console.print(f"\n[bold]Recent Highlights ({len(highlights)}):[/bold]")
            for h in highlights[:5]:
                text = h.text[:100] + "..." if len(h.text) > 100 else h.text
                console.print(f"  - {text}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


# Reader commands
@reader_app.command("inbox")
def reader_inbox(
    limit: Annotated[int, typer.Option(help="Maximum number of items")] = 20,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List inbox documents."""
    client = get_client()

    docs = []
    for i, d in enumerate(client.v3.get_inbox()):
        if i >= limit:
            break
        docs.append(d)

    if json_output:
        data = [
            {
                "id": d.id,
                "title": d.title,
                "url": d.url,
                "category": d.category.value if d.category else None,
            }
            for d in docs
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Inbox ({len(docs)} shown)")
        table.add_column("ID", style="cyan", max_width=15)
        table.add_column("Title", max_width=40)
        table.add_column("Category")

        for d in docs:
            title = (d.title[:37] + "..." if d.title and len(d.title) > 40 else d.title) or ""
            cat = d.category.value if d.category else ""
            table.add_row(d.id[:15], title, cat)

        console.print(table)


@reader_app.command("save")
def reader_save(
    url: Annotated[str, typer.Argument(help="URL to save")],
) -> None:
    """Save a URL to Reader."""
    client = get_client()

    try:
        result = client.v3.save_url(url)
        console.print("[green]Saved![/green]")
        console.print(f"[bold]ID:[/bold] {result.id}")
        console.print(f"[bold]URL:[/bold] {result.url}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


@reader_app.command("archive")
def reader_archive(
    document_id: Annotated[str, typer.Argument(help="Document ID to archive")],
) -> None:
    """Archive a document."""
    client = get_client()

    try:
        client.v3.archive(document_id)
        console.print(f"[green]Archived document {document_id}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


@reader_app.command("stats")
def reader_stats() -> None:
    """Show reading queue statistics."""
    client = get_client()

    from readwise_sdk.workflows.inbox import ReadingInbox

    inbox_workflow = ReadingInbox(client)
    stats = inbox_workflow.get_queue_stats()

    console.print("[bold]Reading Queue Statistics[/bold]")
    console.print(f"  Inbox: {stats.inbox_count}")
    console.print(f"  Reading List: {stats.reading_list_count}")
    console.print(f"  Total Unread: {stats.total_unread}")
    if stats.oldest_item_age_days is not None:
        console.print(f"  Oldest Item: {stats.oldest_item_age_days} days")
    if stats.average_age_days is not None:
        console.print(f"  Average Age: {stats.average_age_days:.1f} days")
    console.print(f"  Items > 30 days: {stats.items_older_than_30_days}")
    console.print(f"  Items > 90 days: {stats.items_older_than_90_days}")

    if stats.by_category:
        console.print("\n[bold]By Category:[/bold]")
        for cat, count in sorted(stats.by_category.items(), key=lambda x: -x[1]):
            console.print(f"  {cat}: {count}")


# Sync commands
@sync_app.command("full")
def sync_full() -> None:
    """Perform a full sync."""
    client = get_client()

    from readwise_sdk.managers.sync import SyncManager

    manager = SyncManager(client)
    console.print("[yellow]Starting full sync...[/yellow]")

    result = manager.full_sync()

    console.print("[green]Sync complete![/green]")
    console.print(f"  Highlights: {len(result.highlights)}")
    console.print(f"  Books: {len(result.books)}")
    console.print(f"  Documents: {len(result.documents)}")


@sync_app.command("incremental")
def sync_incremental(
    state_file: Annotated[str | None, typer.Option(help="State file for persistence")] = None,
) -> None:
    """Perform an incremental sync."""
    client = get_client()

    from readwise_sdk.managers.sync import SyncManager

    manager = SyncManager(client, state_file=state_file)
    console.print("[yellow]Starting incremental sync...[/yellow]")

    result = manager.incremental_sync()

    console.print("[green]Sync complete![/green]")
    console.print(f"  New highlights: {len(result.highlights)}")
    console.print(f"  New books: {len(result.books)}")
    console.print(f"  New documents: {len(result.documents)}")
    console.print(f"  Total syncs: {manager.state.total_syncs}")


# Digest commands
@digest_app.command("daily")
def digest_daily(
    format_type: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "markdown",
    output: Annotated[str | None, typer.Option("-o", help="Output file")] = None,
) -> None:
    """Generate a daily digest of highlights."""
    client = get_client()
    builder = DigestBuilder(client)

    try:
        fmt = DigestFormat(format_type)
    except ValueError:
        console.print("[red]Invalid format. Use: markdown, json, csv, text[/red]")
        raise typer.Exit(1) from None

    content = builder.create_daily_digest(output_format=fmt)

    if output:
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]Saved daily digest to {output}[/green]")
    else:
        console.print(content)


@digest_app.command("weekly")
def digest_weekly(
    format_type: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "markdown",
    output: Annotated[str | None, typer.Option("-o", help="Output file")] = None,
) -> None:
    """Generate a weekly digest of highlights."""
    client = get_client()
    builder = DigestBuilder(client)

    try:
        fmt = DigestFormat(format_type)
    except ValueError:
        console.print("[red]Invalid format. Use: markdown, json, csv, text[/red]")
        raise typer.Exit(1) from None

    content = builder.create_weekly_digest(output_format=fmt)

    if output:
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]Saved weekly digest to {output}[/green]")
    else:
        console.print(content)


@digest_app.command("book")
def digest_book(
    book_id: Annotated[int, typer.Argument(help="Book ID")],
    format_type: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "markdown",
    output: Annotated[str | None, typer.Option("-o", help="Output file")] = None,
) -> None:
    """Generate a digest for a specific book."""
    client = get_client()
    builder = DigestBuilder(client)

    try:
        fmt = DigestFormat(format_type)
    except ValueError:
        console.print("[red]Invalid format. Use: markdown, json, csv, text[/red]")
        raise typer.Exit(1) from None

    content = builder.create_book_digest(book_id, output_format=fmt)

    if output:
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]Saved book digest to {output}[/green]")
    else:
        console.print(content)


# Version command
@app.command("version")
def version() -> None:
    """Show version information."""
    console.print("readwise-sdk v0.1.0")


if __name__ == "__main__":
    app()
