# readwise-plus

[![CI](https://github.com/EvanOman/readwise-plus/actions/workflows/ci.yml/badge.svg)](https://github.com/EvanOman/readwise-plus/actions/workflows/ci.yml)
![coverage](https://raw.githubusercontent.com/EvanOman/readwise-plus/badges/assets/coverage.svg)
[![PyPI version](https://img.shields.io/pypi/v/readwise-plus)](https://pypi.org/project/readwise-plus/)
[![Python versions](https://img.shields.io/pypi/pyversions/readwise-plus)](https://pypi.org/project/readwise-plus/)
[![License](https://img.shields.io/github/license/EvanOman/readwise-plus)](https://github.com/EvanOman/readwise-plus/blob/main/LICENSE)

Comprehensive Python SDK for [Readwise](https://readwise.io), covering both the Readwise API (v2) for highlights/books and the Reader API (v3) for documents behind one concept-oriented interface.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Concept Operations](#concept-operations)
- [Compatibility APIs](#compatibility-apis)
- [CLI](#cli)
- [MCP Server](#mcp-server)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Concept-oriented facade**: `Readwise` / `AsyncReadwise` expose `.documents`, `.highlights`, `.books`, `.tags`, `.digests`, and `.sync` — one place to call each operation, shared by the SDK, CLI, and MCP server
- **Raw escape hatch**: `.raw.v2` / `.raw.v3` for direct, low-level Readwise/Reader API access when you need it
- **CLI**: full command tree (`documents`, `highlights`, `books`, `tags`, `digest`, `sync`) with `--output table|json|jsonl`
- **MCP server**: nine tools for AI agents (Claude Code, Claude Desktop, or any MCP client)
- **Compatibility APIs**: the pre-0.3 `ReadwiseClient`, managers, workflows, and contrib helpers keep working unchanged — see [Compatibility APIs](#compatibility-apis) and [MIGRATION.md](MIGRATION.md)

## Installation

```bash
pip install readwise-plus
```

With CLI support:

```bash
pip install readwise-plus[cli]
```

As an MCP server for AI agents:

```bash
pip install readwise-plus[mcp]
```

## Quick Start

```python
from readwise_sdk import Readwise
from readwise_sdk.models import DocumentSearch

with Readwise() as readwise:  # reads READWISE_API_KEY from the environment
    result = readwise.documents.search(DocumentSearch(query="python", limit=20))
    for doc in result.items:
        print(doc.title)
```

Async, for agent runtimes and async apps:

```python
from readwise_sdk import AsyncReadwise
from readwise_sdk.models import DocumentSearch

async with AsyncReadwise() as readwise:
    result = await readwise.documents.search(DocumentSearch(query="python", limit=20))
    for doc in result.items:
        print(doc.title)
```

`Readwise` and `AsyncReadwise` are the preferred entry points as of `0.3`. New code should start here — see [Concept Operations](#concept-operations) below. Everything under [Compatibility APIs](#compatibility-apis) (`ReadwiseClient`, `.v2`/`.v3`, managers, workflows, contrib) still works and is not scheduled for removal before `1.0`; if you have existing code using it, there is no need to migrate immediately.

## Architecture

```
readwise-plus/
├── Concept facade      → Readwise | AsyncReadwise
│   ├── .documents           Reader documents (v3)
│   ├── .highlights          Readwise highlights (v2)
│   ├── .books               Readwise books/sources (v2)
│   ├── .tags                Tag reports, auto-tag, merge/rename/delete
│   ├── .digests             Daily/weekly/book/custom digest data
│   ├── .sync                Full/incremental sync, checkpoints
│   └── .raw.v2 / .raw.v3    Low-level escape hatch (same clients as below)
├── Operations layer    → async-first; shared by the facade, CLI, and MCP server
├── Resource clients    → readwise_sdk.resources.v2 / .v3 (endpoint-only)
└── Compatibility layer → ReadwiseClient/.v2/.v3, managers, workflows, contrib
```

The CLI and MCP server call the same operations layer as the `Readwise`/`AsyncReadwise` facade, so behavior (limits, filtering, error handling) is consistent across all three surfaces. See [docs/architecture.md](docs/architecture.md) for a short contributor-facing note on the layering, and [MIGRATION.md](MIGRATION.md) for the old→new API mapping and deprecation timeline.

## Concept Operations

Each concept attribute exposes the same methods on both `Readwise` (sync) and `AsyncReadwise` (`await`-prefixed):

```python
from readwise_sdk import Readwise
from readwise_sdk.models import BookSearch, DocumentSearch, HighlightSearch

with Readwise() as readwise:
    # Documents (Reader v3)
    docs = readwise.documents.search(DocumentSearch(location="later", query="python"))
    doc = readwise.documents.get(docs.items[0].id, with_content=True)
    readwise.documents.add_tag(doc.id, "to-review")

    # Highlights (Readwise v2)
    highlights = readwise.highlights.search(HighlightSearch(query="python"))
    created = readwise.highlights.create_from_fields(
        text="Important quote", title="Book Title", author="Author Name"
    )

    # Books (Readwise v2)
    books = readwise.books.search(BookSearch(query="python"))
    with_highlights = readwise.books.with_highlights(books.items[0].id)

    # Tags
    report = readwise.tags.get_tag_report()

    # Digests
    daily = readwise.digests.daily()

    # Sync
    checkpoint = readwise.sync.status()
```

For advanced or low-level use, `readwise.raw.v2` and `readwise.raw.v3` return the same client objects documented under [Compatibility APIs](#compatibility-apis).

## Compatibility APIs

Everything below predates the `0.3` concept facade. It is unchanged and fully supported — these are not "legacy" in the sense of being broken or scheduled for imminent removal, just no longer the recommended starting point for new code. See [MIGRATION.md](MIGRATION.md) for the full old→new mapping and the deprecation timeline through `1.0`.

### `ReadwiseClient` / `AsyncReadwiseClient`

```python
from readwise_sdk import ReadwiseClient
from readwise_sdk.v3.models import DocumentLocation

client = ReadwiseClient(api_key="your_token_here")  # or READWISE_API_KEY env var
client.validate_token()

# V2 API (Readwise) — highlights and books
for highlight in client.v2.list_highlights():
    print(highlight.text)

review = client.v2.get_daily_review()

# V3 API (Reader) — documents
for doc in client.v3.list_documents(location=DocumentLocation.LATER):
    print(doc.title)

result = client.v3.save_url("https://example.com/article")
client.close()
```

### Managers

```python
from readwise_sdk.managers import BookManager, DocumentManager, HighlightManager
from readwise_sdk import BookCategory

highlights = HighlightManager(client)
recent = highlights.get_highlights_since(days=7)
matches = highlights.search_highlights("python programming")

books = BookManager(client)
python_books = books.get_books_by_category(BookCategory.BOOKS)
book_with_highlights = books.get_book_with_highlights(book_id=123)

docs = DocumentManager(client)
inbox = docs.get_inbox()
docs.archive(inbox[0].id)
```

### Workflows

```python
from readwise_sdk.workflows import DigestBuilder, TagWorkflow
from readwise_sdk.workflows.tags import TagPattern

digest = DigestBuilder(client)
print(digest.create_daily_digest())

workflow = TagWorkflow(client)
patterns = [
    TagPattern(r"\bpython\b", "python", case_sensitive=False),
    TagPattern(r"TODO:", "actionable", match_in_notes=True),
]
result = workflow.auto_tag_highlights(patterns, dry_run=True)
print(f"Would tag {len(result)} highlights")
```

### Contrib

```python
from readwise_sdk.contrib import BatchSync, BatchSyncConfig, DocumentImporter, HighlightPusher

pusher = HighlightPusher(client)
pusher.push(text="Great quote from the article", title="Article Title", source_url="https://example.com/article")

importer = DocumentImporter(client)
doc_id = importer.save_url("https://example.com/article", tags=["to-read", "python"])

sync = BatchSync(client, config=BatchSyncConfig(batch_size=100, state_file="sync_state.json"))
result = sync.sync_highlights(on_item=lambda h: print(h.text))
```

## CLI

```bash
readwise [--output table|json|jsonl] [--no-color] [--quiet] <group> <command> ...
```

`--output` defaults to `table`; use `json` or `jsonl` for scripting and agent use. `--no-color` disables Rich styling; `--quiet` suppresses non-data notices.

### Highlights

```bash
readwise highlights list --limit 10 --book-id 123
readwise highlights show 123456
readwise highlights create "Important quote" --title "Book Title" --author "Author Name"
readwise highlights update 123456 --note "revised note"
readwise highlights delete 123456
readwise highlights tag 123456 to-review
readwise highlights untag 123456 to-review
readwise highlights export -f markdown -o highlights.md
```

### Books

```bash
readwise books list --limit 20 --category books
readwise books show 123
```

### Documents

```bash
readwise documents inbox --limit 50
readwise documents get abc123 --with-content
readwise documents save "https://example.com/article"
readwise documents update abc123 --title "New title"
readwise documents move abc123 archive
readwise documents tag abc123 to-review
readwise documents delete abc123
readwise documents stats
```

`readwise reader ...` remains as a deprecated alias for `readwise documents ...` (`inbox`, `save`, `archive`, `stats`, plus every `documents` subcommand); it emits a stderr warning in table mode.

### Tags

```bash
readwise tags list
readwise tags search python --limit 20
readwise tags untagged --limit 20
readwise tags auto-tag --pattern '\bpython\b' --tag python --dry-run
readwise tags rename old-name new-name --dry-run
readwise tags merge "tag-a,tag-b" --into merged-tag --dry-run
readwise tags delete old-tag --dry-run
readwise tags report
```

### Digests

```bash
readwise digest daily -f markdown
readwise digest weekly -o weekly.md
readwise digest book 12345 -o book-notes.md
readwise digest custom --since 2024-01-01 --group-by-date
```

### Sync

```bash
readwise --output json sync full
readwise sync incremental --state-file sync.json
readwise sync status --state-file sync.json
readwise sync reset --state-file sync.json
```

## MCP Server

`readwise-plus` ships an optional [MCP](https://modelcontextprotocol.io) server that exposes Readwise and Reader operations as tools for AI agents (Claude Code, Claude Desktop, or any MCP client). It's a thin layer over the same operations layer used by the SDK facade and CLI — install the `mcp` extra and register the `readwise-mcp` command.

### Register with Claude Code

```bash
claude mcp add readwise --env READWISE_API_KEY=your-token -- uvx --from "readwise-plus[mcp]" readwise-mcp
```

### Register with any MCP client

```json
{
  "mcpServers": {
    "readwise": {
      "command": "uvx",
      "args": ["--from", "readwise-plus[mcp]", "readwise-mcp"],
      "env": { "READWISE_API_KEY": "your-token" }
    }
  }
}
```

If `readwise-plus[mcp]` is already installed in the environment, run the `readwise-mcp` console script (equivalently `python -m readwise_sdk.mcp`) directly.

### Tools

Nine tools, backed by the SDK:

- **Documents (Reader v3):** `save_to_reader`, `search_documents`, `get_document`, `update_document`, `delete_document`
- **Highlights (Readwise v2):** `get_highlights`, `export_highlights`, `create_highlight`
- **Books (Readwise v2):** `get_books`

Auth comes from `READWISE_API_KEY` (an environment variable, or a `READWISE_API_KEY=` line in `~/.env`). Talk to your agent in natural language — "save this URL to my reading list", "find the article I archived about X" — and it picks the right tool.

## Development

```bash
# Clone the repository
git clone https://github.com/EvanOman/readwise-plus.git
cd readwise-plus

# Install dependencies
just install

# Run all checks (format, lint, type-check, test)
just fc

# Run tests only
just test

# Run specific test file
uv run pytest tests/v2/test_client.py
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository** and create a feature branch
2. **Follow conventional commits** for commit messages:
   - `feat(scope): add new feature`
   - `fix(scope): fix a bug`
   - `docs: update documentation`
3. **Run `just fc`** before committing to ensure all checks pass
4. **Write tests** for new functionality
5. **Submit a pull request** with a clear description

See [AGENTS.md](AGENTS.md) for detailed development guidelines and [docs/architecture.md](docs/architecture.md) for the layering contributors should preserve.

## License

MIT
