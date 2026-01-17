"""Tests for DocumentImporter."""

from datetime import datetime

import httpx
import respx

from readwise_sdk.client import READWISE_API_V3_BASE, ReadwiseClient
from readwise_sdk.contrib.document_import import (
    DocumentImporter,
    ImportedDocument,
    ImportResult,
    _extract_domain,
    _html_to_text,
)
from readwise_sdk.v3.models import Document, DocumentCategory, DocumentLocation


class TestExtractDomain:
    """Tests for _extract_domain helper."""

    def test_extract_simple_domain(self) -> None:
        """Test extracting domain from simple URL."""
        assert _extract_domain("https://example.com/article") == "example.com"

    def test_extract_domain_with_www(self) -> None:
        """Test extracting domain strips www prefix."""
        assert _extract_domain("https://www.example.com/page") == "example.com"

    def test_extract_domain_with_subdomain(self) -> None:
        """Test extracting domain with subdomain."""
        assert _extract_domain("https://blog.example.com/post") == "blog.example.com"

    def test_extract_domain_with_port(self) -> None:
        """Test extracting domain with port."""
        assert _extract_domain("https://example.com:8080/page") == "example.com:8080"

    def test_extract_domain_invalid_url(self) -> None:
        """Test extracting domain from invalid URL."""
        assert _extract_domain("not-a-url") is None

    def test_extract_domain_empty(self) -> None:
        """Test extracting domain from empty string."""
        assert _extract_domain("") is None


class TestHtmlToText:
    """Tests for _html_to_text helper."""

    def test_simple_html(self) -> None:
        """Test converting simple HTML to text."""
        html = "<p>Hello <strong>world</strong>!</p>"
        text = _html_to_text(html)
        assert "Hello" in text
        assert "world" in text
        assert "<p>" not in text

    def test_html_with_script_tags(self) -> None:
        """Test that script tags are removed."""
        html = "<p>Content</p><script>alert('bad');</script><p>More</p>"
        text = _html_to_text(html)
        assert "alert" not in text
        assert "Content" in text

    def test_html_with_style_tags(self) -> None:
        """Test that style tags are removed."""
        html = "<style>body { color: red; }</style><p>Content</p>"
        text = _html_to_text(html)
        assert "color" not in text
        assert "Content" in text

    def test_html_entities(self) -> None:
        """Test HTML entity decoding."""
        html = "<p>Tom &amp; Jerry &lt;3</p>"
        text = _html_to_text(html)
        assert "&" in text
        assert "<3" in text
        assert "&amp;" not in text

    def test_whitespace_normalization(self) -> None:
        """Test whitespace is normalized."""
        html = "<p>Hello</p>\n\n\n<p>World</p>"
        text = _html_to_text(html)
        # Should not have excessive whitespace
        assert "   " not in text


class TestImportedDocument:
    """Tests for ImportedDocument dataclass."""

    def test_from_document_minimal(self) -> None:
        """Test creating ImportedDocument from minimal Document."""
        doc = Document(
            id="doc123",
            url="https://example.com/article",
            title="Test Article",
            author=None,
            source=None,
            category=None,
            location=None,
            tags=[],
            site_name=None,
            word_count=None,
            reading_time=None,
            published_date=None,
            summary=None,
            image_url=None,
            content=None,
            source_url=None,
            notes=None,
            parent_id=None,
            reading_progress=None,
            first_opened_at=None,
            last_opened_at=None,
            saved_at=None,
            last_moved_at=None,
            created_at=None,
            updated_at=None,
        )

        imported = ImportedDocument.from_document(doc)

        assert imported.id == "doc123"
        assert imported.url == "https://example.com/article"
        assert imported.title == "Test Article"
        assert imported.domain == "example.com"

    def test_from_document_with_content(self) -> None:
        """Test creating ImportedDocument with HTML content extraction."""
        doc = Document(
            id="doc456",
            url="https://www.test.com/page",
            title="Test Page",
            author="Test Author",
            source=None,
            category=DocumentCategory.ARTICLE,
            location=DocumentLocation.NEW,
            tags=["tag1", "tag2"],
            site_name=None,
            word_count=None,
            reading_time=None,
            published_date=None,
            summary="A summary",
            image_url="https://example.com/img.jpg",
            content="<p>This is the content with some words.</p>",
            source_url=None,
            notes=None,
            parent_id=None,
            reading_progress=0.5,
            first_opened_at=datetime(2024, 1, 1),
            last_opened_at=datetime(2024, 1, 2),
            saved_at=None,
            last_moved_at=None,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 2),
        )

        imported = ImportedDocument.from_document(doc, extract_metadata=True, clean_html=True)

        assert imported.id == "doc456"
        assert imported.domain == "test.com"  # www stripped
        assert imported.clean_text is not None
        assert "content" in imported.clean_text.lower()
        assert imported.html_content == "<p>This is the content with some words.</p>"
        assert imported.reading_progress == 0.5
        assert imported.summary == "A summary"

    def test_from_document_word_count_calculation(self) -> None:
        """Test word count and reading time calculation."""
        # Create content with ~300 words
        words = " ".join(["word"] * 300)
        content = f"<p>{words}</p>"

        doc = Document(
            id="doc789",
            url="https://example.com",
            title="Test",
            author=None,
            source=None,
            category=None,
            location=None,
            tags=[],
            site_name=None,
            word_count=None,  # Not provided
            reading_time=None,  # Not provided
            published_date=None,
            summary=None,
            image_url=None,
            content=content,
            source_url=None,
            notes=None,
            parent_id=None,
            reading_progress=None,
            first_opened_at=None,
            last_opened_at=None,
            saved_at=None,
            last_moved_at=None,
            created_at=None,
            updated_at=None,
        )

        imported = ImportedDocument.from_document(doc, extract_metadata=True, clean_html=True)

        assert imported.word_count is not None
        assert imported.word_count >= 300
        assert imported.reading_time_minutes is not None
        # 300 words at 200 wpm = 1.5 minutes, rounded down to 1
        assert imported.reading_time_minutes >= 1

    def test_from_document_no_metadata_extraction(self) -> None:
        """Test creating ImportedDocument without metadata extraction."""
        doc = Document(
            id="doc_no_meta",
            url="https://example.com",
            title="Test",
            author=None,
            source=None,
            category=None,
            location=None,
            tags=[],
            site_name=None,
            word_count=None,
            reading_time=None,
            published_date=None,
            summary=None,
            image_url=None,
            content="<p>Content</p>",
            source_url=None,
            notes=None,
            parent_id=None,
            reading_progress=None,
            first_opened_at=None,
            last_opened_at=None,
            saved_at=None,
            last_moved_at=None,
            created_at=None,
            updated_at=None,
        )

        imported = ImportedDocument.from_document(doc, extract_metadata=False, clean_html=False)

        assert imported.domain is None
        assert imported.clean_text is None
        assert imported.word_count is None


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful import result."""
        doc = ImportedDocument(
            id="doc123",
            url="https://example.com",
            title="Test",
            author=None,
            category=None,
            location=None,
            tags=[],
            created_at=None,
            updated_at=None,
        )
        result = ImportResult(success=True, document=doc, document_id="doc123")

        assert result.success is True
        assert result.document is doc
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed import result."""
        result = ImportResult(success=False, document_id="doc_fail", error="Not found")

        assert result.success is False
        assert result.document is None
        assert result.error == "Not found"


class TestDocumentImporter:
    """Tests for DocumentImporter."""

    @respx.mock
    def test_import_document(self, api_key: str) -> None:
        """Test importing a single document."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc123",
                            "url": "https://example.com/article",
                            "title": "Test Article",
                            "author": "Test Author",
                            "category": "article",
                            "location": "new",
                            "tags": [],
                        }
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        doc = importer.import_document("doc123")

        assert doc.id == "doc123"
        assert doc.title == "Test Article"
        assert doc.domain == "example.com"

    @respx.mock
    def test_import_document_not_found(self, api_key: str) -> None:
        """Test importing a non-existent document."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        try:
            importer.import_document("nonexistent")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "not found" in str(e).lower()

    @respx.mock
    def test_import_batch(self, api_key: str) -> None:
        """Test importing multiple documents."""
        # First document
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "results": [
                            {"id": "doc1", "url": "https://a.com", "title": "Doc 1", "tags": []}
                        ],
                        "nextPageCursor": None,
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "results": [
                            {"id": "doc2", "url": "https://b.com", "title": "Doc 2", "tags": []}
                        ],
                        "nextPageCursor": None,
                    },
                ),
            ]
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        results = importer.import_batch(["doc1", "doc2"])

        assert len(results) == 2
        assert results[0].success is True
        assert results[0].document is not None
        assert results[0].document.id == "doc1"
        assert results[1].success is True
        assert results[1].document is not None
        assert results[1].document.id == "doc2"

    @respx.mock
    def test_import_batch_with_failure(self, api_key: str) -> None:
        """Test batch import with one failure."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "results": [
                            {"id": "doc1", "url": "https://a.com", "title": "Doc 1", "tags": []}
                        ],
                        "nextPageCursor": None,
                    },
                ),
                httpx.Response(
                    200,
                    json={"results": [], "nextPageCursor": None},  # Not found
                ),
            ]
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        results = importer.import_batch(["doc1", "doc_missing"])

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error is not None
        assert "not found" in results[1].error.lower()

    @respx.mock
    def test_list_inbox(self, api_key: str) -> None:
        """Test listing inbox documents."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "title": "Inbox 1", "tags": []},
                        {"id": "doc2", "url": "https://b.com", "title": "Inbox 2", "tags": []},
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        docs = importer.list_inbox(limit=10)

        assert len(docs) == 2
        assert docs[0].id == "doc1"
        request = route.calls.last.request
        assert "location=new" in str(request.url)

    @respx.mock
    def test_list_reading_list(self, api_key: str) -> None:
        """Test listing reading list documents."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "title": "Later 1", "tags": []}
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        docs = importer.list_reading_list()

        assert len(docs) == 1
        request = route.calls.last.request
        assert "location=later" in str(request.url)

    @respx.mock
    def test_list_archive(self, api_key: str) -> None:
        """Test listing archived documents."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "title": "Archived", "tags": []}
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        docs = importer.list_archive()

        assert len(docs) == 1
        request = route.calls.last.request
        assert "location=archive" in str(request.url)

    @respx.mock
    def test_list_updated_since(self, api_key: str) -> None:
        """Test listing documents updated since a timestamp."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "title": "Updated", "tags": []}
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        since = datetime(2024, 1, 1)
        docs = importer.list_updated_since(since)

        assert len(docs) == 1
        request = route.calls.last.request
        assert "updatedAfter" in str(request.url)

    @respx.mock
    def test_save_url(self, api_key: str) -> None:
        """Test saving a URL."""
        respx.post(f"{READWISE_API_V3_BASE}/save/").mock(
            return_value=httpx.Response(
                200,
                json={"id": "new_doc_id", "url": "https://example.com/article"},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        doc_id = importer.save_url("https://example.com/article")

        assert doc_id == "new_doc_id"

    @respx.mock
    def test_list_with_limit(self, api_key: str) -> None:
        """Test listing with limit parameter."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": f"doc{i}",
                            "url": f"https://{i}.com",
                            "title": f"Doc {i}",
                            "tags": [],
                        }
                        for i in range(10)
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        importer = DocumentImporter(client)

        docs = importer.list_inbox(limit=3)

        assert len(docs) == 3

    def test_importer_options(self, api_key: str) -> None:
        """Test importer configuration options."""
        client = ReadwiseClient(api_key=api_key)

        # Default options
        importer1 = DocumentImporter(client)
        assert importer1._extract_metadata is True
        assert importer1._clean_html is True

        # Custom options
        importer2 = DocumentImporter(client, extract_metadata=False, clean_html=False)
        assert importer2._extract_metadata is False
        assert importer2._clean_html is False
