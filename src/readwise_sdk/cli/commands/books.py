"""Book CLI commands backed by canonical operations."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from readwise_sdk.cli.context import discover_api_key, run_operation
from readwise_sdk.cli.output import OutputFormat, renderer
from readwise_sdk.v2.models import BookCategory

books_app = typer.Typer(help="Manage books")


def _book_data(books: list) -> list[dict]:
    return [
        {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "highlights": book.num_highlights,
        }
        for book in books
    ]


@books_app.command("list")
def list_books(
    limit: Annotated[int, typer.Option(help="Maximum number of books")] = 20,
    category: Annotated[str | None, typer.Option(help="Filter by category")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """List books."""
    api_key = discover_api_key()
    output = renderer(legacy_json=json_output)
    parsed_category = None
    if category:
        try:
            parsed_category = BookCategory(category)
        except ValueError:
            output.error("[red]Invalid category. Use: books, articles, tweets, podcasts[/red]")
            raise typer.Exit(1) from None

    books = run_operation(
        lambda service: service.books.list(category=parsed_category, limit=limit),
        api_key=api_key,
    )

    if output.output_format is not OutputFormat.TABLE:
        output.data(_book_data(books))
        return

    table = Table(title=f"Books ({len(books)} shown)")
    table.add_column("ID", style="cyan")
    table.add_column("Title", max_width=40)
    table.add_column("Author", max_width=20)
    table.add_column("Highlights", justify="right")

    for book in books:
        title = book.title[:37] + "..." if len(book.title) > 40 else book.title
        author = (
            book.author[:17] + "..." if book.author and len(book.author) > 20 else book.author
        ) or ""
        table.add_row(str(book.id), title, author, str(book.num_highlights))

    output.table(table)


@books_app.command("show")
def show_book(
    book_id: Annotated[int, typer.Argument(help="Book ID")],
) -> None:
    """Show a single book with its highlights."""
    api_key = discover_api_key()
    output = renderer()
    try:
        result = run_operation(
            lambda service: service.books.with_highlights(book_id),
            api_key=api_key,
        )

        book = result.book
        if output.output_format is not OutputFormat.TABLE:
            output.data(
                {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "category": book.category.value if book.category else None,
                    "highlights": book.num_highlights,
                    "source": book.source,
                    "recent_highlights": [
                        {
                            "id": highlight.id,
                            "text": (
                                highlight.text[:100] + "..."
                                if len(highlight.text) > 100
                                else highlight.text
                            ),
                        }
                        for highlight in result.highlights[:5]
                    ],
                }
            )
            return

        output.message(f"[bold]ID:[/bold] {book.id}")
        output.message(f"[bold]Title:[/bold] {book.title}")
        if book.author:
            output.message(f"[bold]Author:[/bold] {book.author}")
        if book.category:
            output.message(f"[bold]Category:[/bold] {book.category.value}")
        output.message(f"[bold]Highlights:[/bold] {book.num_highlights}")
        if book.source:
            output.message(f"[bold]Source:[/bold] {book.source}")

        if result.highlights:
            output.message(f"\n[bold]Recent Highlights ({len(result.highlights)}):[/bold]")
            for highlight in result.highlights[:5]:
                text = highlight.text[:100] + "..." if len(highlight.text) > 100 else highlight.text
                output.message(f"  - {text}")
    except Exception as error:
        output.error(f"[red]Error: {error}[/red]")
        raise typer.Exit(1) from None


__all__ = ["books_app"]
