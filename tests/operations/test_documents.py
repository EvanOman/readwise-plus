"""Unit tests for canonical document operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from readwise_sdk.errors import NotFoundError
from readwise_sdk.models import DocumentSearch
from readwise_sdk.operations.documents import DocumentOperations
from readwise_sdk.operations.service import ReadwiseService
from readwise_sdk.v3.models import (
    CreateDocumentResult,
    Document,
    DocumentCategory,
    DocumentCreate,
    DocumentLocation,
    DocumentUpdate,
)


class FakeDocumentsResource:
    """Small in-memory seam matching the document resource contract."""

    def __init__(self, documents: list[Document] | None = None) -> None:
        self.documents = documents or []
        self.documents_by_id = {document.id: document for document in self.documents}
        self.iter_calls: list[dict[str, object]] = []
        self.get_calls: list[tuple[str, bool]] = []
        self.create_calls: list[DocumentCreate] = []
        self.update_calls: list[tuple[str, DocumentUpdate]] = []
        self.delete_calls: list[str] = []
        self.fail_updates: dict[str, Exception] = {}
        self.result = CreateDocumentResult(id="result-id", url="https://reader/result-id")

    async def iter(
        self,
        *,
        location: DocumentLocation | None = None,
        category: DocumentCategory | None = None,
        updated_after: datetime | None = None,
        tags: list[str] | None = None,
        with_content: bool = False,
    ) -> AsyncIterator[Document]:
        self.iter_calls.append(
            {
                "location": location,
                "category": category,
                "updated_after": updated_after,
                "tags": tags,
                "with_content": with_content,
            }
        )
        for document in self.documents:
            if location is not None and document.location is not location:
                continue
            if category is not None and document.category is not category:
                continue
            yield document

    async def get(self, document_id: str, *, with_content: bool = False) -> Document | None:
        self.get_calls.append((document_id, with_content))
        return self.documents_by_id.get(document_id)

    async def create(self, document: DocumentCreate) -> CreateDocumentResult:
        self.create_calls.append(document)
        return self.result

    async def update(
        self,
        document_id: str,
        update: DocumentUpdate,
    ) -> CreateDocumentResult:
        self.update_calls.append((document_id, update))
        if error := self.fail_updates.get(document_id):
            raise error
        return self.result.model_copy(update={"id": document_id})

    async def delete(self, document_id: str) -> None:
        self.delete_calls.append(document_id)


def document(
    document_id: str,
    *,
    title: str | None = None,
    author: str | None = None,
    summary: str | None = None,
    source_url: str | None = None,
    location: DocumentLocation = DocumentLocation.NEW,
    category: DocumentCategory | None = DocumentCategory.ARTICLE,
    tags: list[str] | None = None,
    created_at: datetime | None = None,
) -> Document:
    """Build a compact Reader document fixture."""
    return Document(
        id=document_id,
        url=f"https://reader/{document_id}",
        source_url=source_url,
        title=title,
        author=author,
        summary=summary,
        location=location,
        category=category,
        tags=tags or [],
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_search_ports_mcp_filters_projection_limit_and_resource_arguments() -> None:
    """Search is title-only, case-insensitive, bounded, and returns MCP summary fields."""
    updated_after = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)
    resource = FakeDocumentsResource(
        [
            document(
                "matching",
                title="A PYTHON Guide",
                author="Nobody",
                source_url="https://source/article",
                location=DocumentLocation.LATER,
                tags=["python"],
            ),
            document(
                "author-only",
                title="Unrelated",
                author="Python Author",
                location=DocumentLocation.LATER,
            ),
            # Characterizes current MCP behavior: a missing title is not rejected by a query.
            document("missing-title", title=None, location=DocumentLocation.LATER),
        ]
    )
    operations = DocumentOperations(resource)

    result = await operations.search(
        DocumentSearch(
            location=DocumentLocation.LATER,
            category=DocumentCategory.ARTICLE,
            updated_after=updated_after,
            tags=("python", "sdk"),
            query="python",
            limit=2,
        )
    )

    assert [item.id for item in result.items] == ["matching", "missing-title"]
    assert result.items[0].url == "https://source/article"
    assert result.items[0].tags == ("python",)
    assert result.truncated is True
    assert resource.iter_calls == [
        {
            "location": DocumentLocation.LATER,
            "category": DocumentCategory.ARTICLE,
            "updated_after": updated_after,
            "tags": ["python", "sdk"],
            "with_content": False,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("provided", "expected"), [(0, 1), (1000, 100)])
async def test_search_uses_stage_five_limit_clamping(provided: int, expected: int) -> None:
    """The canonical input preserves MCP's inclusive 1..100 limit clamp."""
    resource = FakeDocumentsResource([document(str(index), title="match") for index in range(101)])

    result = await DocumentOperations(resource).search(
        DocumentSearch(query="match", limit=provided)
    )

    assert len(result.items) == expected


@pytest.mark.asyncio
async def test_get_save_update_delete_and_move_delegate_typed_results() -> None:
    """CRUD and movement preserve the resource models and location update semantics."""
    existing = document("doc-1", title="Old")
    resource = FakeDocumentsResource([existing])
    operations = DocumentOperations(resource)
    update = DocumentUpdate(title="New")

    assert await operations.get("doc-1", with_content=True) is existing
    saved = await operations.save(DocumentCreate(url="https://example.com", title="Saved"))
    updated = await operations.update("doc-1", update)
    moved = await operations.move("doc-1", DocumentLocation.ARCHIVE)
    assert saved is resource.result
    assert updated.id == "doc-1"
    assert moved.id == "doc-1"
    await operations.delete("doc-1")

    assert resource.get_calls == [("doc-1", True)]
    assert resource.create_calls[0].title == "Saved"
    assert resource.update_calls == [
        ("doc-1", update),
        ("doc-1", DocumentUpdate(location=DocumentLocation.ARCHIVE)),
    ]
    assert resource.delete_calls == ["doc-1"]


@pytest.mark.asyncio
async def test_save_intentionally_drops_category_to_preserve_current_mcp_bug() -> None:
    """The accepted save category remains absent from the resource payload in PR 6."""
    resource = FakeDocumentsResource()
    operations = DocumentOperations(resource)
    create = DocumentCreate(
        url="https://example.com",
        category=DocumentCategory.ARTICLE,
        location=DocumentLocation.LATER,
        saved_using="readwise-mcp",
    )

    await operations.save(create)

    # Characterizes current (buggy) behavior; a later stage fixes category handling.
    assert resource.create_calls[0].category is None
    assert resource.create_calls[0].location is DocumentLocation.LATER
    assert resource.create_calls[0].saved_using == "readwise-mcp"


@pytest.mark.asyncio
async def test_set_add_and_remove_tags_preserve_order_duplicates_and_not_found() -> None:
    """Tag composition matches v3: set replaces, add deduplicates one tag, remove removes all."""
    existing = document("doc-1", tags=["one", "duplicate", "duplicate"])
    resource = FakeDocumentsResource([existing])
    operations = DocumentOperations(resource)

    await operations.set_tags("doc-1", ["raw", "raw"])
    await operations.add_tag("doc-1", "two")
    await operations.add_tag("doc-1", "one")
    await operations.remove_tag("doc-1", "duplicate")

    assert [update.tags for _, update in resource.update_calls] == [
        ["raw", "raw"],
        ["one", "duplicate", "duplicate", "two"],
        ["one", "duplicate", "duplicate"],
        ["one"],
    ]

    with pytest.raises(NotFoundError, match="Document missing not found"):
        await operations.add_tag("missing", "tag")
    with pytest.raises(NotFoundError, match="Document missing not found"):
        await operations.remove_tag("missing", "tag")


@pytest.mark.asyncio
async def test_location_views_materialize_documents_with_cli_and_importer_limits() -> None:
    """Inbox/later/archive are raw document views with optional content and bounded results."""
    resource = FakeDocumentsResource(
        [
            document("new-1"),
            document("new-2"),
            document("later", location=DocumentLocation.LATER),
            document("archive", location=DocumentLocation.ARCHIVE),
        ]
    )
    operations = DocumentOperations(resource)

    assert [item.id for item in await operations.inbox(limit=1, with_content=True)] == ["new-1"]
    assert await operations.inbox(limit=0) == []
    assert [item.id for item in await operations.later()] == ["later"]
    assert [item.id for item in await operations.archive()] == ["archive"]
    assert resource.iter_calls[0]["with_content"] is True


@pytest.mark.asyncio
async def test_statistics_combines_manager_and_reading_inbox_semantics() -> None:
    """Statistics retain counts, category grouping, inbox extrema, and queue age thresholds."""
    now = datetime.now(UTC)
    newest = document("newest", created_at=now - timedelta(days=1))
    oldest = document(
        "oldest",
        category=None,
        created_at=now - timedelta(days=31),
    )
    later = document(
        "later",
        location=DocumentLocation.LATER,
        category=DocumentCategory.PDF,
        created_at=now - timedelta(days=91),
    )
    archived = document("archived", location=DocumentLocation.ARCHIVE)
    resource = FakeDocumentsResource([newest, oldest, later, archived])

    stats = await DocumentOperations(resource).statistics()

    assert stats.inbox_count == 2
    assert stats.reading_list_count == 1
    assert stats.archive_count == 1
    assert stats.total_count == 4
    assert stats.total_unread == 3
    assert stats.by_category == {"article": 1, "unknown": 1, "pdf": 1}
    assert stats.oldest_inbox_item is oldest
    assert stats.newest_inbox_item is newest
    assert stats.oldest_item_age_days == 91
    assert stats.average_age_days == pytest.approx(41.0)
    assert stats.items_older_than_30_days == 2
    assert stats.items_older_than_90_days == 1


@pytest.mark.asyncio
async def test_bulk_move_and_set_tags_keep_partial_failures_and_continue() -> None:
    """Broad per-item failure suppression is retained in a declared BulkResult."""
    resource = FakeDocumentsResource()
    archive_error = RuntimeError("archive failed")
    tag_error = RuntimeError("tag failed")
    resource.fail_updates = {"archive-bad": archive_error, "tag-bad": tag_error}
    operations = DocumentOperations(resource)

    moved = await operations.bulk_move(["archive-ok", "archive-bad"], DocumentLocation.ARCHIVE)
    tagged = await operations.bulk_set_tags(["tag-bad", "tag-ok"], ["one"])

    assert moved.succeeded == ["archive-ok"]
    assert moved.failures[0].item == "archive-bad"
    assert moved.failures[0].error is archive_error
    assert tagged.succeeded == ["tag-ok"]
    assert tagged.failures[0].item == "tag-bad"
    assert tagged.failures[0].error is tag_error


def test_service_wires_the_canonical_document_operations() -> None:
    """The operation container exposes one DocumentOperations instance."""
    resource = FakeDocumentsResource()

    service = ReadwiseService(documents=resource)

    assert isinstance(service.documents, DocumentOperations)
