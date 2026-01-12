# Readwise SDK - Project Plan

## Overview

A comprehensive Python SDK for the Readwise platform providing:
1. **Core Layer**: Direct Python methods for each API endpoint (v2 + v3)
2. **Abstraction Layer**: User-friendly, workflow-oriented operations for power readers

## Research Summary

### API Capabilities

**Readwise API v2** (Highlights & Books):
- `GET/POST/PATCH/DELETE /api/v2/highlights/` - Highlight CRUD
- `GET /api/v2/books/` - Book listing with filtering
- `GET/POST/PATCH/DELETE /api/v2/highlights/{id}/tags/` - Tag management
- `GET /api/v2/export/` - Bulk export with pagination
- `GET /api/v2/review/` - Daily review highlights
- `GET /api/v2/auth/` - Token validation

**Readwise Reader API v3** (Documents):
- `POST /api/v3/save/` - Create documents
- `GET /api/v3/list/` - List documents with filtering
- `PATCH /api/v3/update/{id}/` - Update document metadata
- `DELETE /api/v3/delete/{id}/` - Delete documents
- `GET /api/v3/tags/` - List all tags

### Rate Limits
- Base: 240 requests/minute
- Highlight/Book LIST: 20 requests/minute
- Reader operations: 50 requests/minute

### Patterns from Existing Projects

From `readwise_digest`:
- Iterator-based pagination
- Comprehensive error hierarchy
- Retry with exponential backoff
- State persistence for polling

From `highlight_helper`:
- Async HTTP client (httpx)
- Background sync workflows
- Batch operations with result tracking
- Field truncation handling

From `sane_reader`:
- Document location/category filtering
- HTML content extraction
- Tag-based workflows
- Incremental sync patterns

From `goodreads_api`:
- Pydantic models with field aliases
- Rate-limiting HTTP client wrapper
- CLI with typer
- Browser cookie extraction

---

## Milestones

### Milestone 1: Core SDK Foundation
**Goal**: Establish project structure with proper tooling and base HTTP client

**Deliverables**:
1. Project scaffolding (pyproject.toml, Justfile, CI)
2. Base HTTP client with:
   - Token authentication
   - Rate limiting (configurable)
   - Retry with exponential backoff
   - Timeout handling
3. Exception hierarchy:
   - `ReadwiseError` (base)
   - `AuthenticationError` (401)
   - `RateLimitError` (429, with retry_after)
   - `NotFoundError` (404)
   - `ValidationError` (400)
   - `ServerError` (5xx)
4. Sync and async client variants
5. Unit tests for HTTP client and error handling

**Testing**:
- Unit tests with mocked HTTP responses
- Test error handling for all status codes
- Test retry logic
- `just fc` passes

---

### Milestone 2: Readwise API v2 Client
**Goal**: Complete implementation of all Readwise API v2 endpoints

**Deliverables**:
1. Pydantic models:
   - `Book`, `Highlight`, `Tag`, `DailyReview`
   - Request/response models with validation
2. Highlight operations:
   - `list_highlights(filters)` - with pagination iterator
   - `get_highlight(id)`
   - `create_highlights(highlights)` - batch create
   - `update_highlight(id, fields)`
   - `delete_highlight(id)`
3. Book operations:
   - `list_books(filters)` - with pagination iterator
   - `get_book(id)`
4. Tag operations:
   - `list_highlight_tags(highlight_id)`
   - `create_highlight_tag(highlight_id, name)`
   - `update_highlight_tag(highlight_id, tag_id, name)`
   - `delete_highlight_tag(highlight_id, tag_id)`
   - Book tag operations (same pattern)
5. Export operation:
   - `export_highlights(filters)` - cursor-based pagination
6. Daily review:
   - `get_daily_review()`
7. Auth:
   - `validate_token()`

**Testing**:
- Unit tests with fixtures for each endpoint
- Integration tests (marked, require API key)
- Test pagination exhaustion
- Test filter combinations
- `just fc` passes

---

### Milestone 3: Reader API v3 Client
**Goal**: Complete implementation of all Readwise Reader API v3 endpoints

**Deliverables**:
1. Pydantic models:
   - `Document` with all fields
   - `DocumentLocation` enum (new, later, archive, feed)
   - `DocumentCategory` enum (article, email, pdf, etc.)
2. Document operations:
   - `create_document(url, **kwargs)` - with all optional fields
   - `list_documents(filters)` - with pagination iterator
   - `get_document(id, with_content=False)`
   - `update_document(id, fields)`
   - `delete_document(id)`
3. Tag operations:
   - `list_tags()` - with pagination
4. Content handling:
   - Option to fetch HTML content
   - HTML to text extraction utilities

**Testing**:
- Unit tests with fixtures
- Integration tests (marked)
- Test document creation with various content types
- Test filtering by location/category
- `just fc` passes

---

### Milestone 4: High-Level Abstractions
**Goal**: User-friendly operations built on top of core client

**Deliverables**:
1. `HighlightManager`:
   - `get_all_highlights()` - exhaust pagination automatically
   - `get_highlights_since(datetime)` - incremental fetch
   - `get_highlights_by_book(book_id)`
   - `get_highlights_with_notes()` - filter annotated
   - `search_highlights(query)` - text search across highlights
   - `bulk_tag(highlight_ids, tag)` - batch tagging
   - `bulk_untag(highlight_ids, tag)` - batch untagging

2. `BookManager`:
   - `get_all_books()`
   - `get_books_by_category(category)`
   - `get_book_with_highlights(book_id)` - enriched response
   - `get_reading_stats()` - aggregated statistics

3. `DocumentManager` (Reader):
   - `get_inbox()` - documents in "new" location
   - `get_reading_list()` - documents in "later"
   - `get_archive()` - archived documents
   - `move_to_later(doc_id)` / `archive(doc_id)`
   - `bulk_tag_documents(doc_ids, tags)`
   - `get_documents_since(datetime)`

4. `SyncManager`:
   - `full_sync()` - fetch everything
   - `incremental_sync(since)` - fetch updates only
   - State persistence (configurable backend)
   - Callback hooks for new items

**Testing**:
- Unit tests for each manager
- Test batch operations
- Test sync state persistence
- `just fc` passes

---

### Milestone 5: Advanced Workflows
**Goal**: Power-user workflows based on observed usage patterns

**Deliverables**:
1. `DigestBuilder`:
   - `create_daily_digest()` - highlights from last 24h
   - `create_weekly_digest()` - highlights from last 7d
   - `create_book_digest(book_id)` - all highlights for a book
   - Export formats: Markdown, JSON, CSV, plain text
   - Grouping options: by book, by date, by source

2. `BackgroundPoller`:
   - Configurable polling interval
   - Graceful shutdown (signal handling)
   - Error recovery with backoff
   - State persistence across restarts
   - Callback system for new highlights/documents

3. `TagWorkflow`:
   - `auto_tag_by_content(patterns)` - regex-based tagging
   - `tag_cleanup()` - find/merge duplicate tags
   - `tag_report()` - usage statistics

4. `ReadingInbox`:
   - `triage()` - interactive inbox processing helper
   - `smart_archive(rules)` - auto-archive based on rules
   - `reading_queue_stats()` - queue depth, age distribution

5. CLI (optional but recommended):
   - `readwise highlights list/create/export`
   - `readwise books list/show`
   - `readwise reader inbox/archive/save`
   - `readwise sync --incremental`
   - `readwise digest --format markdown`

**Testing**:
- Unit tests for workflows
- Integration tests for CLI commands
- Test background poller lifecycle
- `just fc` passes

---

## Technical Standards

### Python Practices (from pystd)
- Python 3.12+
- uv for package management
- ruff for linting/formatting
- ty for type checking
- just for task running
- pytest for testing
- GitHub Actions CI

### Dependencies
```toml
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "pytest-cov>=6.0.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.22.0",  # httpx mocking
    "ruff>=0.14.0",
    "ty>=0.0.8",
]
cli = [
    "typer>=0.21.0",
    "rich>=14.0.0",
]
```

### Project Structure
```
readwise-sdk/
├── src/
│   └── readwise_sdk/
│       ├── __init__.py
│       ├── client.py          # Base HTTP client
│       ├── exceptions.py      # Error hierarchy
│       ├── v2/                # Readwise API v2
│       │   ├── __init__.py
│       │   ├── client.py
│       │   ├── models.py
│       │   ├── highlights.py
│       │   ├── books.py
│       │   └── tags.py
│       ├── v3/                # Reader API v3
│       │   ├── __init__.py
│       │   ├── client.py
│       │   ├── models.py
│       │   └── documents.py
│       ├── managers/          # High-level abstractions
│       │   ├── __init__.py
│       │   ├── highlights.py
│       │   ├── books.py
│       │   ├── documents.py
│       │   └── sync.py
│       ├── workflows/         # Advanced workflows
│       │   ├── __init__.py
│       │   ├── digest.py
│       │   ├── poller.py
│       │   ├── tags.py
│       │   └── inbox.py
│       └── cli/               # CLI (optional)
│           ├── __init__.py
│           └── main.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_client.py
│   ├── v2/
│   ├── v3/
│   ├── managers/
│   └── workflows/
├── pyproject.toml
├── Justfile
├── README.md
└── .github/
    └── workflows/
        └── ci.yml
```

---

## Success Criteria

Each milestone is complete when:
1. All deliverables implemented
2. Unit tests pass with >80% coverage
3. Integration tests pass (when applicable)
4. `just fc` passes (format, lint, type-check, test)
5. Documentation updated
6. GitHub issue closed

## Next Steps

1. Initialize GitHub repository
2. Create GitHub issues for each milestone
3. Begin Milestone 1 implementation
