"""Canonical Reader document import operations."""

from __future__ import annotations

import builtins
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from readwise_sdk.models.reader import Document, DocumentCategory, DocumentLocation

WORDS_PER_MINUTE = 200


class ImportDocumentsResource(Protocol):
    async def get(self, document_id: str, *, with_content: bool = False) -> Document | None: ...

    def iter(self, **kwargs: Any) -> AsyncIterator[Document]: ...

    async def save_url(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class ImportedDocumentData:
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


@dataclass(frozen=True, slots=True)
class DocumentImportResult:
    document_id: str
    document: ImportedDocumentData | None = None
    error: Exception | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.document is not None


def extract_domain(url: str) -> str | None:
    """Extract a domain using the importer's pinned lenient behavior."""
    try:
        domain = urlparse(url).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or None
    except Exception:
        return None


def html_to_text(html: str) -> str:
    """Convert HTML to text using BeautifulSoup when it is installed."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-not-found]

        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        return soup.get_text(separator=" ", strip=True)
    except ImportError:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        return re.sub(r"\s+", " ", text).strip()


def import_document_data(
    document: Document,
    *,
    extract_metadata: bool = True,
    clean_html: bool = True,
) -> ImportedDocumentData:
    """Project a Reader document into the importer contract."""
    clean_text = html_to_text(document.content) if clean_html and document.content else None
    word_count = document.word_count
    reading_time = document.reading_time
    if extract_metadata and clean_text:
        if word_count is None:
            word_count = len(clean_text.split())
        if reading_time is None and word_count:
            reading_time = max(1, word_count // WORDS_PER_MINUTE)
    return ImportedDocumentData(
        id=document.id,
        url=document.url,
        title=document.title,
        author=document.author,
        category=document.category,
        location=document.location,
        tags=document.tags,
        created_at=document.created_at,
        updated_at=document.updated_at,
        html_content=document.content,
        clean_text=clean_text,
        domain=extract_domain(document.url) if extract_metadata and document.url else None,
        word_count=word_count,
        reading_time_minutes=reading_time,
        summary=document.summary,
        image_url=document.image_url,
        reading_progress=document.reading_progress,
        first_opened_at=document.first_opened_at,
        last_opened_at=document.last_opened_at,
    )


class DocumentImportOperations:
    """Own import projection, batching, limits, and partial failures."""

    def __init__(
        self,
        resource: ImportDocumentsResource,
        *,
        extract_metadata: bool = True,
        clean_html: bool = True,
    ) -> None:
        self._resource = resource
        self._extract_metadata = extract_metadata
        self._clean_html = clean_html

    def project(self, document: Document) -> ImportedDocumentData:
        return import_document_data(
            document,
            extract_metadata=self._extract_metadata,
            clean_html=self._clean_html,
        )

    async def import_document(
        self,
        document_id: str,
        *,
        with_content: bool = True,
    ) -> ImportedDocumentData:
        document = await self._resource.get(document_id, with_content=with_content)
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        return self.project(document)

    async def import_batch(
        self,
        document_ids: builtins.list[str],
        *,
        with_content: bool = True,
    ) -> builtins.list[DocumentImportResult]:
        results: builtins.list[DocumentImportResult] = []
        for document_id in document_ids:
            try:
                document = await self.import_document(document_id, with_content=with_content)
                results.append(DocumentImportResult(document_id, document=document))
            except Exception as error:
                results.append(DocumentImportResult(document_id, error=error))
        return results

    async def list(
        self,
        *,
        location: DocumentLocation | None = None,
        updated_after: datetime | None = None,
        limit: int | None = None,
        with_content: bool = False,
    ) -> builtins.list[ImportedDocumentData]:
        results: builtins.list[ImportedDocumentData] = []
        index = 0
        async for document in self._resource.iter(
            location=location,
            updated_after=updated_after,
            with_content=with_content,
        ):
            if limit and index >= limit:
                break
            results.append(self.project(document))
            index += 1
        return results

    async def save_url(self, url: str, **kwargs: Any) -> str:
        return (await self._resource.save_url(url, **kwargs)).id


__all__ = [
    "DocumentImportOperations",
    "DocumentImportResult",
    "ImportedDocumentData",
    "extract_domain",
    "html_to_text",
    "import_document_data",
]
