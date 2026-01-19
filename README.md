# readwise-plus

[![CI](https://github.com/EvanOman/readwise-plus/actions/workflows/ci.yml/badge.svg)](https://github.com/EvanOman/readwise-plus/actions/workflows/ci.yml)
![coverage](assets/coverage.svg)
[![PyPI version](https://badge.fury.io/py/readwise-plus.svg)](https://pypi.org/project/readwise-plus/)
[![Python versions](https://img.shields.io/pypi/pyversions/readwise-plus)](https://pypi.org/project/readwise-plus/)
[![License](https://img.shields.io/github/license/EvanOman/readwise-plus)](https://github.com/EvanOman/readwise-plus/blob/main/LICENSE)

Comprehensive Python SDK for [Readwise](https://readwise.io) with high-level workflow abstractions. Supports both the Readwise API (v2) for highlights/books and the Reader API (v3) for documents.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Core API Usage](#core-api-usage)
- [Managers](#managers)
- [Workflows](#workflows)
- [Contrib Interfaces](#contrib-interfaces)
- [CLI](#cli)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Features

- **V2 API (Readwise)**: Full support for highlights, books, tags, and daily review
- **V3 API (Reader)**: Full support for documents, inbox, reading list, and archive
- **Managers**: High-level abstractions for common operations
- **Workflows**: Pre-built workflows for digests, tagging, and syncing
- **Contrib**: Convenience interfaces for common integration patterns
- **CLI**: Command-line interface for quick operations

## Installation

```bash
pip install readwise-plus
```

With CLI support:

```bash
pip install readwise-plus[cli]
```

## Quick Start

```python
from readwise_sdk import ReadwiseClient

# Initialize with your API token
client = ReadwiseClient(api_key="your_token_here")

# Or use environment variable READWISE_API_KEY
client = ReadwiseClient()

# Validate your token
client.validate_token()

# Get all highlights
for highlight in client.v2.highlights.list():
    print(highlight.text)

# Get Reader inbox
for doc in client.v3.documents.list(location="new"):
    print(doc.title)
```

## Architecture

The SDK is organized into layers of increasing abstraction:

```
readwise-plus/
├── Core Layer
│   ├── V2 Client      → client.v2.*     (Readwise API)
│   └── V3 Client      → client.v3.*     (Reader API)
├── Manager Layer
│   ├── HighlightManager   → Highlight operations
│   ├── BookManager        → Book operations
│   ├── DocumentManager    → Document operations
│   └── SyncManager        → Sync state tracking
├── Workflow Layer
│   ├── DigestBuilder      → Create highlight digests
│   ├── ReadingInbox       → Inbox management
│   ├── TagWorkflow        → Auto-tagging
│   └── BackgroundPoller   → Background sync
└── Contrib Layer
    ├── HighlightPusher    → Push highlights to Readwise
    ├── DocumentImporter   → Import documents to Reader
    └── BatchSync          → Batch synchronization
```

## Core API Usage

### V2 API (Readwise Highlights)

```python
from readwise_sdk import ReadwiseClient
from datetime import datetime

client = ReadwiseClient()

# List highlights with filtering
highlights = client.v2.highlights.list(
    book_id=123,
    updated_after=datetime(2024, 1, 1),
)

# Get a specific highlight
highlight = client.v2.highlights.get(highlight_id=456)

# Create a highlight
new_highlight = client.v2.highlights.create(
    text="Important quote from the book",
    title="Book Title",
    author="Author Name",
    source_type="book",
)

# Export all highlights with full book metadata
for book in client.v2.export_highlights():
    print(f"{book.title}: {len(book.highlights)} highlights")
    for h in book.highlights:
        print(f"  - {h.text[:50]}...")

# Get daily review highlights
review = client.v2.get_daily_review()
for highlight in review.highlights:
    print(highlight.text)
```

### V3 API (Reader Documents)

```python
# List inbox documents
for doc in client.v3.documents.list(location="new"):
    print(f"{doc.title} ({doc.category})")

# Save a URL to Reader
result = client.v3.save_url("https://example.com/article")
print(f"Saved: {result.id}")

# Get document with full content
doc = client.v3.documents.get(doc_id, with_html=True)
print(doc.html)

# Move document to archive
client.v3.documents.update(doc_id, location="archive")

# Filter by category
articles = client.v3.documents.list(category="article")
pdfs = client.v3.documents.list(category="pdf")
```

## Managers

Managers provide higher-level operations with better ergonomics.

### HighlightManager

```python
from readwise_sdk.managers import HighlightManager

highlights = HighlightManager(client)

# Get recent highlights
recent = highlights.get_highlights_since(days=7)

# Search highlights
results = highlights.search("python programming")

# Bulk operations
highlights.bulk_tag(highlight_ids, "to-review")
highlights.bulk_delete(highlight_ids)

# Get highlights by book
book_highlights = highlights.get_by_book(book_id=123)
```

### BookManager

```python
from readwise_sdk.managers import BookManager

books = BookManager(client)

# List all books
all_books = books.list()

# Get books by category
articles = books.get_by_category("articles")

# Get book with highlights
book = books.get_with_highlights(book_id=123)
```

### DocumentManager

```python
from readwise_sdk.managers import DocumentManager

docs = DocumentManager(client)

# Get inbox
inbox = docs.get_inbox()

# Archive a document
docs.archive(doc_id)

# Get reading stats
stats = docs.get_stats()
print(f"Inbox: {stats.inbox_count}, Archive: {stats.archive_count}")
```

## Workflows

Pre-built workflows for common use cases.

### DigestBuilder

```python
from readwise_sdk.workflows import DigestBuilder

digest = DigestBuilder(client)

# Daily digest
daily = digest.build_daily()
print(daily.to_markdown())

# Weekly digest
weekly = digest.build_weekly()

# Book-specific digest
book_digest = digest.build_for_book(book_id=123)
book_digest.save("book-notes.md")
```

### TagWorkflow

```python
from readwise_sdk.workflows.tags import TagWorkflow, TagPattern

workflow = TagWorkflow(client)

# Define tagging patterns
patterns = [
    TagPattern(r"\bpython\b", "python", case_sensitive=False),
    TagPattern(r"\bmachine learning\b", "ml", case_sensitive=False),
    TagPattern(r"TODO:", "actionable", search_in_notes=True),
]

# Auto-tag highlights
result = workflow.auto_tag_highlights(patterns, dry_run=True)
print(f"Would tag {result.matched_count} highlights")

# Apply tags
result = workflow.auto_tag_highlights(patterns, dry_run=False)

# Rename a tag
workflow.rename_tag(old_name="todo", new_name="actionable")
```

### ReadingInbox

```python
from readwise_sdk.workflows import ReadingInbox

inbox = ReadingInbox(client)

# Get prioritized inbox
prioritized = inbox.get_prioritized(limit=10)

# Triage inbox items
for doc in inbox.get_untriaged():
    if doc.word_count < 500:
        inbox.archive(doc.id)
    else:
        inbox.move_to_later(doc.id)
```

## Contrib Interfaces

Simplified interfaces for common integration patterns.

### HighlightPusher

```python
from readwise_sdk.contrib import HighlightPusher

pusher = HighlightPusher(client)

# Push a single highlight
pusher.push(
    text="Great quote from the article",
    title="Article Title",
    source_url="https://example.com/article",
)

# Push multiple highlights
pusher.push_batch([
    {"text": "Quote 1", "title": "Book 1"},
    {"text": "Quote 2", "title": "Book 2"},
])
```

### DocumentImporter

```python
from readwise_sdk.contrib import DocumentImporter

importer = DocumentImporter(client)

# Import a URL
doc = importer.import_url("https://example.com/article")

# Import with tags
doc = importer.import_url(
    "https://example.com/article",
    tags=["to-read", "python"],
)
```

### BatchSync

```python
from readwise_sdk.contrib import BatchSync, BatchSyncConfig

config = BatchSyncConfig(
    batch_size=100,
    state_file="sync_state.json",
)
sync = BatchSync(client, config=config)

# Sync with callback
def on_highlight(highlight):
    save_to_database(highlight)

result = sync.sync_highlights(on_item=on_highlight)
print(f"Synced {result.synced_count} highlights")
```

## CLI

The CLI provides quick access to common operations.

### Highlights

```bash
# List recent highlights
readwise highlights list --limit 10

# Show a specific highlight
readwise highlights show 123456

# Export highlights
readwise highlights export -f markdown -o highlights.md
readwise highlights export -f json -o highlights.json
```

### Books

```bash
# List books
readwise books list --limit 20

# Show book details
readwise books show 123
```

### Reader

```bash
# View inbox
readwise reader inbox --limit 50

# Save a URL
readwise reader save "https://example.com/article"

# Archive a document
readwise reader archive abc123

# Get reading stats
readwise reader stats
```

### Digests

```bash
# Generate daily digest
readwise digest daily -f markdown

# Generate weekly digest
readwise digest weekly -o weekly.md

# Generate book digest
readwise digest book 12345 -o book-notes.md
```

### Sync

```bash
# Full sync
readwise sync full --output-dir ./data

# Incremental sync
readwise sync incremental --state-file sync.json
```

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

See [AGENTS.md](AGENTS.md) for detailed development guidelines.

## License

MIT
