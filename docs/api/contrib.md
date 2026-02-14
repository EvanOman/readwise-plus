# Contrib

The contrib module provides specialized interfaces for common integration patterns.

## HighlightPusher

Simplified interface for pushing highlights to Readwise. Designed for highlight_helper and similar projects.

```python
from readwise_sdk import ReadwiseClient
from readwise_sdk.contrib import HighlightPusher, SimpleHighlight

client = ReadwiseClient()
pusher = HighlightPusher(client)
```

### Methods

#### push

Push a single highlight:

```python
result = pusher.push(
    text="This is my highlight",
    title="Article Title",
    author="John Doe",
    note="My note about this",
)

if result.success:
    print(f"Created highlight {result.highlight_id}")
else:
    print(f"Failed: {result.error}")
```

#### push_highlight

Push a SimpleHighlight object:

```python
highlight = SimpleHighlight(
    text="Important quote",
    title="Book Title",
    author="Author Name",
    note="Why this matters",
    tags=["important", "review"],
)

result = pusher.push_highlight(highlight)
```

#### push_batch

Push multiple highlights at once:

```python
highlights = [
    SimpleHighlight(text="First highlight", title="Book 1"),
    SimpleHighlight(text="Second highlight", title="Book 2"),
    SimpleHighlight(text="Third highlight", title="Book 3"),
]

results = pusher.push_batch(highlights)
for result in results:
    if result.success:
        print(f"Created: {result.highlight_id}")
    else:
        print(f"Failed: {result.error}")
```

### Features

- **Auto-truncation**: Automatically truncates fields to Readwise limits
- **Batch operations**: Push multiple highlights efficiently
- **Individual error handling**: Failures don't affect other highlights

### Models

#### SimpleHighlight

```python
@dataclass
class SimpleHighlight:
    text: str
    title: str
    author: str | None = None
    source_url: str | None = None
    source_type: str = "readwise_sdk"
    category: BookCategory | None = None
    note: str | None = None
    location: int | None = None
    location_type: str | None = None
    highlighted_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
```

#### PushResult

```python
@dataclass
class PushResult:
    success: bool
    highlight_id: int | None = None
    book_id: int | None = None
    error: str | None = None
    original: SimpleHighlight | None = None
    was_truncated: bool = False
```

#### update

Update an existing highlight:

```python
result = pusher.update(
    highlight_id=123,
    text="Updated highlight text",
    note="Updated note",
    location=50,
    location_type="page",
)

if result.success:
    print(f"Updated highlight {result.highlight_id}")
    print(f"New text: {result.highlight.text}")
```

#### update_batch

Update multiple highlights:

```python
# Each tuple: (highlight_id, text, note, location, location_type)
# Pass None for fields you don't want to update
updates = [
    (1, "New text for highlight 1", None, None, None),
    (2, None, "New note for highlight 2", None, None),
    (3, "New text", "New note", 100, "page"),
]

results = pusher.update_batch(updates)
for result in results:
    if result.success:
        print(f"Updated: {result.highlight_id}")
    else:
        print(f"Failed {result.highlight_id}: {result.error}")
```

#### delete

Delete a highlight:

```python
result = pusher.delete(highlight_id=123)

if result.success:
    print(f"Deleted highlight {result.highlight_id}")
else:
    print(f"Failed: {result.error}")
```

#### delete_batch

Delete multiple highlights:

```python
results = pusher.delete_batch([1, 2, 3])

for result in results:
    if result.success:
        print(f"Deleted: {result.highlight_id}")
    else:
        print(f"Failed {result.highlight_id}: {result.error}")
```

#### UpdateResult

```python
@dataclass
class UpdateResult:
    success: bool
    highlight_id: int
    highlight: Highlight | None = None  # Updated highlight if successful
    error: str | None = None
    was_truncated: bool = False
```

#### DeleteResult

```python
@dataclass
class DeleteResult:
    success: bool
    highlight_id: int
    error: str | None = None
```

### AsyncHighlightPusher

An async version of HighlightPusher for non-blocking I/O operations.

```python
import asyncio
from readwise_sdk import AsyncReadwiseClient
from readwise_sdk.contrib import AsyncHighlightPusher, SimpleHighlight

async def main():
    async with AsyncReadwiseClient() as client:
        pusher = AsyncHighlightPusher(client)

        # Push a single highlight
        result = await pusher.push(
            text="This is my highlight",
            title="Article Title",
            author="John Doe",
        )

        if result.success:
            print(f"Created highlight {result.highlight_id}")

        # Push a SimpleHighlight object
        highlight = SimpleHighlight(
            text="Important quote",
            title="Book Title",
            author="Author Name",
            tags=["important"],
        )
        result = await pusher.push_highlight(highlight)

        # Push multiple highlights concurrently
        highlights = [
            SimpleHighlight(text="First", title="Book 1"),
            SimpleHighlight(text="Second", title="Book 2"),
            SimpleHighlight(text="Third", title="Book 3"),
        ]
        results = await pusher.push_batch(highlights)

asyncio.run(main())
```

All methods from `HighlightPusher` are available as async versions:

**Create:**
- `await pusher.push(...)` - Push a single highlight
- `await pusher.push_highlight(highlight)` - Push a SimpleHighlight object
- `await pusher.push_batch(highlights)` - Push multiple highlights

**Update:**
- `await pusher.update(highlight_id, text=..., note=...)` - Update a highlight
- `await pusher.update_batch(updates)` - Update multiple highlights

**Delete:**
- `await pusher.delete(highlight_id)` - Delete a highlight
- `await pusher.delete_batch(highlight_ids)` - Delete multiple highlights

```python
async def main():
    async with AsyncReadwiseClient() as client:
        pusher = AsyncHighlightPusher(client)

        # Update
        result = await pusher.update(
            highlight_id=123,
            text="Updated text",
            note="Updated note",
        )

        # Batch update
        results = await pusher.update_batch([
            (1, "New text 1", None, None, None),
            (2, "New text 2", "New note", None, None),
        ])

        # Delete
        result = await pusher.delete(highlight_id=123)

        # Batch delete
        results = await pusher.delete_batch([1, 2, 3])
```

---

## DocumentImporter

Interface for importing documents from Readwise Reader with metadata extraction. Designed for sane_reader and similar projects.

```python
from readwise_sdk import ReadwiseClient
from readwise_sdk.contrib import DocumentImporter

client = ReadwiseClient()
importer = DocumentImporter(client)
```

### Methods

#### import_document

Import a single document with full content:

```python
doc = importer.import_document("doc_id_here", with_content=True)

print(f"Title: {doc.title}")
print(f"Clean text: {doc.clean_text[:200]}...")
print(f"Domain: {doc.domain}")
print(f"Reading time: {doc.reading_time_minutes} mins")
```

#### import_batch

Import multiple documents:

```python
results = importer.import_batch(["doc1", "doc2", "doc3"])
for result in results:
    if result.success:
        print(f"Imported: {result.document.title}")
    else:
        print(f"Failed {result.document_id}: {result.error}")
```

#### list_inbox / list_reading_list / list_archive

List documents from specific locations:

```python
# Inbox documents
inbox = importer.list_inbox(limit=50)

# Reading list
reading_list = importer.list_reading_list(limit=50)

# Archive
archive = importer.list_archive(limit=50)
```

#### list_updated_since

List documents updated since a timestamp:

```python
from datetime import datetime, timedelta

since = datetime.now() - timedelta(days=7)
recent = importer.list_updated_since(since, limit=100)
```

#### save_url

Save a URL to Readwise Reader:

```python
doc_id = importer.save_url("https://example.com/article")
print(f"Saved document: {doc_id}")
```

### Features

- **HTML to text conversion**: Automatically extracts clean text from HTML
- **Metadata extraction**: Extracts domain, calculates word count and reading time
- **Batch operations**: Import multiple documents efficiently
- **BeautifulSoup support**: Uses BeautifulSoup if installed for better HTML parsing

### Models

#### ImportedDocument

```python
@dataclass
class ImportedDocument:
    # Core fields
    id: str
    url: str
    title: str | None
    author: str | None
    category: DocumentCategory | None
    location: DocumentLocation | None
    tags: list[str]
    created_at: datetime | None
    updated_at: datetime | None

    # Content
    html_content: str | None = None
    clean_text: str | None = None

    # Extracted metadata
    domain: str | None = None
    word_count: int | None = None
    reading_time_minutes: int | None = None
    summary: str | None = None
    image_url: str | None = None

    # Reading progress
    reading_progress: float | None = None
    first_opened_at: datetime | None = None
    last_opened_at: datetime | None = None
```

#### ImportResult

```python
@dataclass
class ImportResult:
    success: bool
    document: ImportedDocument | None = None
    document_id: str | None = None
    error: str | None = None
```

---

## BatchSync

Efficient batch synchronization with state tracking. Designed for readwise_digest and similar projects.

```python
from readwise_sdk import ReadwiseClient
from readwise_sdk.contrib import BatchSync, BatchSyncConfig

client = ReadwiseClient()

config = BatchSyncConfig(
    batch_size=100,
    state_file="sync_state.json",
)

sync = BatchSync(client, config=config)
```

### Methods

#### sync_highlights

Sync highlights with callbacks:

```python
def on_highlight(highlight):
    print(f"New: {highlight.text[:50]}...")
    # Save to database, etc.

result = sync.sync_highlights(on_item=on_highlight)
print(f"Synced {result.new_items} new highlights")
```

With batch callback:

```python
def on_batch(highlights):
    # Process batch of highlights
    for h in highlights:
        save_to_db(h)

result = sync.sync_highlights(on_batch=on_batch)
```

Full sync (ignore last sync timestamp):

```python
result = sync.sync_highlights(full_sync=True)
```

#### sync_books

Sync books with callbacks:

```python
def on_book(book):
    print(f"Book: {book.title}")

result = sync.sync_books(on_item=on_book)
print(f"Synced {result.new_items} books")
```

#### sync_all

Sync both highlights and books:

```python
highlight_result, book_result = sync.sync_all(
    on_highlight=process_highlight,
    on_book=process_book,
)
```

#### reset_state

Reset sync state (next sync will be full sync):

```python
sync.reset_state()
```

#### get_stats

Get sync statistics:

```python
stats = sync.get_stats()
print(f"Last sync: {stats['last_sync_time']}")
print(f"Total highlights: {stats['total_highlights_synced']}")
print(f"Errors: {stats['error_count']}")
```

### Configuration

```python
@dataclass
class BatchSyncConfig:
    batch_size: int = 100           # Items per batch
    state_file: Path | str | None = None  # Path to save state
    continue_on_error: bool = True  # Continue if individual items fail
```

### Models

#### SyncState

```python
@dataclass
class SyncState:
    last_highlight_sync: datetime | None = None
    last_book_sync: datetime | None = None
    last_document_sync: datetime | None = None
    total_highlights_synced: int = 0
    total_books_synced: int = 0
    total_documents_synced: int = 0
    last_sync_time: datetime | None = None
    errors: list[str] = field(default_factory=list)
```

#### BatchSyncResult

```python
@dataclass
class BatchSyncResult:
    success: bool
    new_items: int = 0
    updated_items: int = 0
    failed_items: int = 0
    errors: list[str] = field(default_factory=list)
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))
```

### AsyncBatchSync

An async version of BatchSync for non-blocking I/O operations.

```python
import asyncio
from readwise_sdk import AsyncReadwiseClient
from readwise_sdk.contrib import AsyncBatchSync, BatchSyncConfig

async def main():
    async with AsyncReadwiseClient() as client:
        config = BatchSyncConfig(
            batch_size=100,
            state_file="sync_state.json",
        )

        sync = AsyncBatchSync(client, config=config)

        # Sync highlights with async callback
        async def on_highlight(highlight):
            print(f"New: {highlight.text[:50]}...")
            await save_to_database(highlight)

        result = await sync.sync_highlights(on_item=on_highlight)
        print(f"Synced {result.new_items} new highlights")

asyncio.run(main())
```

All methods from `BatchSync` are available as async versions:

- `await sync.sync_highlights(on_item=..., on_batch=..., full_sync=False)` - Sync highlights
- `await sync.sync_books(on_item=..., on_batch=..., full_sync=False)` - Sync books
- `await sync.sync_all(on_highlight=..., on_book=..., full_sync=False)` - Sync both
- `sync.reset_state()` - Reset state (sync method)
- `sync.get_stats()` - Get statistics (sync method)

**Callback Support:**

AsyncBatchSync supports both sync and async callbacks:

```python
async with AsyncReadwiseClient() as client:
    sync = AsyncBatchSync(client)

    # Sync callback works
    def sync_callback(highlight):
        print(f"Got: {highlight.text}")

    # Async callback also works
    async def async_callback(highlight):
        await process_highlight(highlight)

    # Either can be used
    await sync.sync_highlights(on_item=sync_callback)
    await sync.sync_highlights(on_item=async_callback)
```
