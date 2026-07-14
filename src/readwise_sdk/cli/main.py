"""Command-line interface for Readwise SDK."""

from __future__ import annotations

import json
import sys
from importlib.metadata import version as pkg_version
from typing import Annotated

try:
    import typer
    from rich.table import Table
except ImportError:
    print("CLI dependencies not installed. Install with: pip install readwise-plus[cli]")
    sys.exit(1)

from readwise_sdk.cli.commands.books import books_app
from readwise_sdk.cli.commands.documents import reader_app
from readwise_sdk.cli.commands.highlights import highlights_app
from readwise_sdk.cli.context import get_client
from readwise_sdk.cli.output import (
    CliOutputContext,
    OutputFormat,
    configure_color,
    console,
    current_output_format,
    renderer,
)
from readwise_sdk.workflows.digest import DigestBuilder, DigestFormat
from readwise_sdk.workflows.tags import TagPattern, TagWorkflow

app = typer.Typer(
    name="readwise",
    help="Readwise SDK CLI - Manage your Readwise highlights and Reader documents",
    no_args_is_help=True,
)


@app.callback()
def cli_context(
    ctx: typer.Context,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format: table, json, or jsonl"),
    ] = OutputFormat.TABLE,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress non-data notices"),
    ] = False,
) -> None:
    """Configure shared CLI invocation state."""
    ctx.obj = CliOutputContext(output_format=output, no_color=no_color, quiet=quiet)
    configure_color(no_color=no_color)


# Sub-apps
sync_app = typer.Typer(help="Sync operations")
digest_app = typer.Typer(help="Generate digests")
tags_app = typer.Typer(help="Manage tags")

app.add_typer(highlights_app, name="highlights")
app.add_typer(books_app, name="books")
app.add_typer(reader_app, name="documents")
app.add_typer(reader_app, name="reader")
app.add_typer(sync_app, name="sync")
app.add_typer(digest_app, name="digest")
app.add_typer(tags_app, name="tags")


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


# Tags commands
@tags_app.command("list")
def list_tags(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List all tags with usage counts."""
    client = get_client()
    workflow = TagWorkflow(client)

    console.print("[yellow]Fetching tag report...[/yellow]")
    report = workflow.get_tag_report()

    if json_output:
        data = {
            "total_tags": report.total_tags,
            "total_usages": report.total_usages,
            "tags": [{"name": name, "count": count} for name, count in report.tags_by_usage],
            "duplicate_candidates": report.duplicate_candidates,
        }
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Tags ({report.total_tags} total, {report.total_usages} usages)")
        table.add_column("Tag", style="cyan")
        table.add_column("Count", justify="right")

        for name, count in report.tags_by_usage:
            table.add_row(name, str(count))

        console.print(table)

        if report.duplicate_candidates:
            console.print("\n[yellow]Potential duplicates:[/yellow]")
            for group in report.duplicate_candidates:
                console.print(f"  {', '.join(group)}")


@tags_app.command("search")
def search_tags(
    tag: Annotated[str, typer.Argument(help="Tag name to search for")],
    limit: Annotated[int, typer.Option(help="Maximum number of highlights")] = 20,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search highlights by tag."""
    client = get_client()
    workflow = TagWorkflow(client)

    highlights = workflow.get_highlights_by_tag(tag)

    if json_output:
        data = [
            {
                "id": h.id,
                "text": h.text[:100] + "..." if len(h.text) > 100 else h.text,
                "tags": [t.name for t in (h.tags or [])],
            }
            for h in highlights[:limit]
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Highlights with tag '{tag}' ({len(highlights)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Text", max_width=60)
        table.add_column("Tags", max_width=30)

        for h in highlights[:limit]:
            text = h.text[:57] + "..." if len(h.text) > 60 else h.text
            tags = ", ".join(t.name for t in (h.tags or []))
            table.add_row(str(h.id), text, tags)

        console.print(table)


@tags_app.command("untagged")
def untagged_highlights(
    limit: Annotated[int, typer.Option(help="Maximum number of highlights")] = 20,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List highlights without any tags."""
    client = get_client()
    workflow = TagWorkflow(client)

    highlights = workflow.get_untagged_highlights()

    if json_output:
        data = [
            {
                "id": h.id,
                "text": h.text[:100] + "..." if len(h.text) > 100 else h.text,
            }
            for h in highlights[:limit]
        ]
        console.print(json.dumps(data, indent=2))
    else:
        table = Table(title=f"Untagged Highlights ({len(highlights)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Text", max_width=70)

        for h in highlights[:limit]:
            text = h.text[:67] + "..." if len(h.text) > 70 else h.text
            table.add_row(str(h.id), text)

        console.print(table)


@tags_app.command("auto-tag")
def auto_tag(
    pattern: Annotated[str, typer.Option("--pattern", "-p", help="Regex pattern to match")],
    tag: Annotated[str, typer.Option("--tag", "-t", help="Tag to apply")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = True,
    search_notes: Annotated[bool, typer.Option("--notes", help="Search in notes")] = True,
    search_text: Annotated[bool, typer.Option("--text", help="Search in text")] = True,
    case_sensitive: Annotated[
        bool, typer.Option("--case-sensitive", help="Case sensitive")
    ] = False,
) -> None:
    """Auto-tag highlights matching a pattern."""
    client = get_client()
    workflow = TagWorkflow(client)

    tag_pattern = TagPattern(
        pattern=pattern,
        tag=tag,
        case_sensitive=case_sensitive,
        match_in_notes=search_notes,
        match_in_text=search_text,
    )

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]APPLYING[/green]"
    console.print(f"{mode} - Pattern: '{pattern}' -> Tag: '{tag}'")

    results = workflow.auto_tag_highlights([tag_pattern], dry_run=dry_run)

    if results:
        console.print(
            f"\n[bold]{len(results)} highlights {'would be' if dry_run else 'were'} tagged:[/bold]"
        )
        for highlight_id, tags in list(results.items())[:10]:
            console.print(f"  - Highlight {highlight_id}: +{', '.join(tags)}")
        if len(results) > 10:
            console.print(f"  ... and {len(results) - 10} more")
    else:
        console.print("[dim]No highlights matched the pattern.[/dim]")

    if dry_run and results:
        console.print("\n[dim]Run without --dry-run to apply changes.[/dim]")


@tags_app.command("rename")
def rename_tag(
    old_name: Annotated[str, typer.Argument(help="Current tag name")],
    new_name: Annotated[str, typer.Argument(help="New tag name")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = True,
) -> None:
    """Rename a tag across all highlights."""
    client = get_client()
    workflow = TagWorkflow(client)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]APPLYING[/green]"
    console.print(f"{mode} - Renaming '{old_name}' -> '{new_name}'")

    affected = workflow.rename_tag(old_name, new_name, dry_run=dry_run)

    if affected:
        console.print(
            f"\n[bold]{len(affected)} highlights {'would be' if dry_run else 'were'} affected:[/bold]"
        )
        for highlight_id in affected[:10]:
            console.print(f"  - Highlight {highlight_id}")
        if len(affected) > 10:
            console.print(f"  ... and {len(affected) - 10} more")
    else:
        console.print(f"[dim]No highlights found with tag '{old_name}'.[/dim]")

    if dry_run and affected:
        console.print("\n[dim]Run without --dry-run to apply changes.[/dim]")


@tags_app.command("merge")
def merge_tags(
    source_tags: Annotated[str, typer.Argument(help="Comma-separated tags to merge from")],
    into: Annotated[str, typer.Option("--into", help="Tag to merge into")] = "",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = True,
) -> None:
    """Merge multiple tags into one."""
    if not into:
        console.print("[red]Error: --into option is required[/red]")
        raise typer.Exit(1)

    client = get_client()
    workflow = TagWorkflow(client)

    sources = [s.strip() for s in source_tags.split(",")]

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]APPLYING[/green]"
    console.print(f"{mode} - Merging {sources} -> '{into}'")

    affected = workflow.merge_tags(sources, into, dry_run=dry_run)

    if affected:
        console.print(
            f"\n[bold]{len(affected)} highlights {'would be' if dry_run else 'were'} affected:[/bold]"
        )
        for highlight_id in affected[:10]:
            console.print(f"  - Highlight {highlight_id}")
        if len(affected) > 10:
            console.print(f"  ... and {len(affected) - 10} more")
    else:
        console.print("[dim]No highlights found with any of the source tags.[/dim]")

    if dry_run and affected:
        console.print("\n[dim]Run without --dry-run to apply changes.[/dim]")


@tags_app.command("delete")
def delete_tag(
    tag_name: Annotated[str, typer.Argument(help="Tag to delete")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = True,
) -> None:
    """Delete a tag from all highlights."""
    client = get_client()
    workflow = TagWorkflow(client)

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[red]DELETING[/red]"
    console.print(f"{mode} - Removing tag '{tag_name}'")

    affected = workflow.delete_tag(tag_name, dry_run=dry_run)

    if affected:
        console.print(
            f"\n[bold]{len(affected)} highlights {'would be' if dry_run else 'were'} affected:[/bold]"
        )
        for highlight_id in affected[:10]:
            console.print(f"  - Highlight {highlight_id}")
        if len(affected) > 10:
            console.print(f"  ... and {len(affected) - 10} more")
    else:
        console.print(f"[dim]No highlights found with tag '{tag_name}'.[/dim]")

    if dry_run and affected:
        console.print("\n[dim]Run without --dry-run to apply changes.[/dim]")


@tags_app.command("report")
def tag_report(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Generate a detailed tag usage report."""
    client = get_client()
    workflow = TagWorkflow(client)

    console.print("[yellow]Generating tag report...[/yellow]")
    report = workflow.get_tag_report()

    if json_output:
        data = {
            "summary": {
                "total_tags": report.total_tags,
                "total_usages": report.total_usages,
            },
            "top_tags": [
                {"name": name, "count": count} for name, count in report.tags_by_usage[:20]
            ],
            "unused_tags": report.unused_tags,
            "duplicate_candidates": report.duplicate_candidates,
        }
        console.print(json.dumps(data, indent=2))
    else:
        console.print("\n[bold]Tag Report[/bold]")
        console.print(f"  Total Tags: {report.total_tags}")
        console.print(f"  Total Usages: {report.total_usages}")

        if report.tags_by_usage:
            console.print("\n[bold]Top Tags:[/bold]")
            for name, count in report.tags_by_usage[:20]:
                bar = "█" * min(count, 30)
                console.print(f"  {name:20} {count:4} {bar}")

        if report.unused_tags:
            console.print(f"\n[yellow]Unused Tags ({len(report.unused_tags)}):[/yellow]")
            console.print(f"  {', '.join(report.unused_tags[:10])}")
            if len(report.unused_tags) > 10:
                console.print(f"  ... and {len(report.unused_tags) - 10} more")

        if report.duplicate_candidates:
            console.print(
                f"\n[yellow]Potential Duplicates ({len(report.duplicate_candidates)} groups):[/yellow]"
            )
            for group in report.duplicate_candidates[:5]:
                console.print(f"  {', '.join(group)}")


# Version command
@app.command("version")
def version() -> None:
    """Show version information."""
    package_version = pkg_version("readwise-plus")
    if current_output_format() is OutputFormat.TABLE:
        console.print(f"readwise-plus v{package_version}")
    else:
        renderer().data({"version": package_version})


if __name__ == "__main__":
    app()
