"""Legacy Reader document-import compatibility shims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from readwise_sdk.operations.compat import AsyncDocumentsResource, SyncDocumentsResource, run_sync
from readwise_sdk.operations.imports import (
    DocumentImportOperations,
    DocumentImportResult,
    ImportedDocumentData,
    extract_domain,
    html_to_text,
    import_document_data,
)
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation

if TYPE_CHECKING:
    from readwise_sdk.client import AsyncReadwiseClient, ReadwiseClient

WORDS_PER_MINUTE = 200


@dataclass
class ImportedDocument:
    id: str
    url: str
    title: str | None
    author: str | None
    category: DocumentCategory | None
    location: DocumentLocation | None
    tags: list[str]
    created_at: datetime | None
    updated_at: datetime | None
    html_content: str | None = None
    clean_text: str | None = None
    domain: str | None = None
    word_count: int | None = None
    reading_time_minutes: int | None = None
    summary: str | None = None
    image_url: str | None = None
    reading_progress: float | None = None
    first_opened_at: datetime | None = None
    last_opened_at: datetime | None = None

    @classmethod
    def from_document(
        cls,
        doc: Document,
        *,
        extract_metadata: bool = True,
        clean_html: bool = True,
    ) -> ImportedDocument:
        return _legacy_document(
            import_document_data(
                doc,
                extract_metadata=extract_metadata,
                clean_html=clean_html,
            )
        )


@dataclass
class ImportResult:
    success: bool
    document: ImportedDocument | None = None
    document_id: str | None = None
    error: str | None = None


def _extract_domain(url: str) -> str | None:
    return extract_domain(url)


def _html_to_text(html: str) -> str:
    return html_to_text(html)


def _legacy_document(document: ImportedDocumentData) -> ImportedDocument:
    return ImportedDocument(
        id=document.id,
        url=document.url,
        title=document.title,
        author=document.author,
        category=document.category,
        location=document.location,
        tags=document.tags,
        created_at=document.created_at,
        updated_at=document.updated_at,
        html_content=document.html_content,
        clean_text=document.clean_text,
        domain=document.domain,
        word_count=document.word_count,
        reading_time_minutes=document.reading_time_minutes,
        summary=document.summary,
        image_url=document.image_url,
        reading_progress=document.reading_progress,
        first_opened_at=document.first_opened_at,
        last_opened_at=document.last_opened_at,
    )


def _legacy_result(result: DocumentImportResult) -> ImportResult:
    return ImportResult(
        success=result.success,
        document=_legacy_document(result.document) if result.document is not None else None,
        document_id=result.document_id,
        error=str(result.error) if result.error is not None else None,
    )


class DocumentImporter:
    """Synchronous compatibility wrapper over document import operations."""

    def __init__(
        self,
        client: ReadwiseClient,
        *,
        extract_metadata: bool = True,
        clean_html: bool = True,
    ) -> None:
        self._client = client
        self._extract_metadata = extract_metadata
        self._clean_html = clean_html
        self._operations = DocumentImportOperations(
            SyncDocumentsResource(client),
            extract_metadata=extract_metadata,
            clean_html=clean_html,
        )

    def import_document(
        self,
        document_id: str,
        *,
        with_content: bool = True,
    ) -> ImportedDocument:
        return _legacy_document(
            run_sync(self._operations.import_document(document_id, with_content=with_content))
        )

    def import_batch(
        self,
        document_ids: list[str],
        *,
        with_content: bool = True,
    ) -> list[ImportResult]:
        return [
            _legacy_result(result)
            for result in run_sync(
                self._operations.import_batch(document_ids, with_content=with_content)
            )
        ]

    def list_inbox(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return self._list_location(DocumentLocation.NEW, limit=limit, with_content=with_content)

    def list_reading_list(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return self._list_location(DocumentLocation.LATER, limit=limit, with_content=with_content)

    def list_archive(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return self._list_location(DocumentLocation.ARCHIVE, limit=limit, with_content=with_content)

    def _list_location(
        self,
        location: DocumentLocation,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return [
            _legacy_document(document)
            for document in run_sync(
                self._operations.list(
                    location=location,
                    limit=limit,
                    with_content=with_content,
                )
            )
        ]

    def list_updated_since(
        self,
        since: datetime,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return [
            _legacy_document(document)
            for document in run_sync(
                self._operations.list(
                    updated_after=since,
                    limit=limit,
                    with_content=with_content,
                )
            )
        ]

    def save_url(self, url: str, **kwargs: Any) -> str:
        return run_sync(self._operations.save_url(url, **kwargs))


class AsyncDocumentImporter:
    """Asynchronous compatibility wrapper over document import operations."""

    def __init__(
        self,
        client: AsyncReadwiseClient,
        *,
        extract_metadata: bool = True,
        clean_html: bool = True,
    ) -> None:
        self._client = client
        self._extract_metadata = extract_metadata
        self._clean_html = clean_html
        self._operations = DocumentImportOperations(
            AsyncDocumentsResource(client),
            extract_metadata=extract_metadata,
            clean_html=clean_html,
        )

    async def import_document(
        self,
        document_id: str,
        *,
        with_content: bool = True,
    ) -> ImportedDocument:
        return _legacy_document(
            await self._operations.import_document(document_id, with_content=with_content)
        )

    async def import_batch(
        self,
        document_ids: list[str],
        *,
        with_content: bool = True,
    ) -> list[ImportResult]:
        return [
            _legacy_result(result)
            for result in await self._operations.import_batch(
                document_ids,
                with_content=with_content,
            )
        ]

    async def list_inbox(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return await self._list_location(
            DocumentLocation.NEW,
            limit=limit,
            with_content=with_content,
        )

    async def list_reading_list(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return await self._list_location(
            DocumentLocation.LATER,
            limit=limit,
            with_content=with_content,
        )

    async def list_archive(
        self,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return await self._list_location(
            DocumentLocation.ARCHIVE,
            limit=limit,
            with_content=with_content,
        )

    async def _list_location(
        self,
        location: DocumentLocation,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return [
            _legacy_document(document)
            for document in await self._operations.list(
                location=location,
                limit=limit,
                with_content=with_content,
            )
        ]

    async def list_updated_since(
        self,
        since: datetime,
        *,
        limit: int | None = None,
        with_content: bool = False,
    ) -> list[ImportedDocument]:
        return [
            _legacy_document(document)
            for document in await self._operations.list(
                updated_after=since,
                limit=limit,
                with_content=with_content,
            )
        ]

    async def save_url(self, url: str, **kwargs: Any) -> str:
        return await self._operations.save_url(url, **kwargs)
