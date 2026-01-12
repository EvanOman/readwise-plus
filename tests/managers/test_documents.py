"""Tests for DocumentManager."""

import httpx
import respx

from readwise_sdk.client import READWISE_API_V3_BASE, ReadwiseClient
from readwise_sdk.managers.documents import DocumentManager
from readwise_sdk.v3.models import DocumentCategory


class TestDocumentManager:
    """Tests for DocumentManager."""

    @respx.mock
    def test_get_inbox(self, api_key: str) -> None:
        """Test getting inbox documents."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://example.com/1", "location": "new"},
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = DocumentManager(client)
        docs = manager.get_inbox()

        assert len(docs) == 1
        request = route.calls.last.request
        assert "location=new" in str(request.url)

    @respx.mock
    def test_get_reading_list(self, api_key: str) -> None:
        """Test getting reading list documents."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = DocumentManager(client)
        manager.get_reading_list()

        request = route.calls.last.request
        assert "location=later" in str(request.url)

    @respx.mock
    def test_bulk_archive(self, api_key: str) -> None:
        """Test bulk archiving documents."""
        respx.patch(url__startswith=f"{READWISE_API_V3_BASE}/update/").mock(
            return_value=httpx.Response(
                200,
                json={"id": "doc1", "url": "https://readwise.io/reader/doc1"},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = DocumentManager(client)
        results = manager.bulk_archive(["doc1", "doc2"])

        assert results["doc1"] is True
        assert results["doc2"] is True

    @respx.mock
    def test_search_documents(self, api_key: str) -> None:
        """Test searching documents."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "title": "Python Tutorial"},
                        {"id": "doc2", "url": "https://b.com", "title": "JavaScript Guide"},
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = DocumentManager(client)
        results = manager.search_documents("python")

        assert len(results) == 1
        assert results[0].title is not None
        assert "Python" in results[0].title

    @respx.mock
    def test_get_inbox_stats(self, api_key: str) -> None:
        """Test getting inbox statistics."""
        call_count = 0

        def mock_response(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "doc1",
                                "url": "https://a.com",
                                "category": "article",
                                "created_at": "2024-01-10T00:00:00Z",
                            },
                            {
                                "id": "doc2",
                                "url": "https://b.com",
                                "category": "article",
                                "created_at": "2024-01-15T00:00:00Z",
                            },
                        ],
                        "nextPageCursor": None,
                    },
                )
            elif call_count == 2:
                return httpx.Response(
                    200,
                    json={
                        "results": [{"id": "doc3", "url": "https://c.com", "category": "article"}],
                        "nextPageCursor": None,
                    },
                )
            else:
                return httpx.Response(200, json={"results": [], "nextPageCursor": None})

        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(side_effect=mock_response)

        client = ReadwiseClient(api_key=api_key)
        manager = DocumentManager(client)
        stats = manager.get_inbox_stats()

        assert stats.inbox_count == 2
        assert stats.reading_list_count == 1
        assert stats.by_category["article"] == 3  # 2 inbox + 1 reading list

    @respx.mock
    def test_get_documents_by_category(self, api_key: str) -> None:
        """Test getting documents by category."""
        route = respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            )
        )

        client = ReadwiseClient(api_key=api_key)
        manager = DocumentManager(client)
        manager.get_documents_by_category(DocumentCategory.ARTICLE)

        request = route.calls.last.request
        assert "category=article" in str(request.url)
