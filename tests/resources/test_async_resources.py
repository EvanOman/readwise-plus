"""Tests for asynchronous resource composition and compatibility delegation."""

from __future__ import annotations

import pytest

from readwise_sdk.client import AsyncReadwiseClient
from readwise_sdk.resources.v2.books import AsyncBooksResource
from readwise_sdk.resources.v2.export import AsyncExportResource
from readwise_sdk.resources.v2.highlights import AsyncHighlightsResource
from readwise_sdk.resources.v2.review import AsyncReviewResource
from readwise_sdk.resources.v2.tags import AsyncTagsResource as AsyncV2TagsResource
from readwise_sdk.resources.v3.documents import AsyncDocumentsResource
from readwise_sdk.resources.v3.tags import AsyncTagsResource as AsyncV3TagsResource
from readwise_sdk.v2.models import Highlight
from readwise_sdk.v3.models import Document


def test_async_versioned_clients_compose_endpoint_resources() -> None:
    """The legacy versioned clients are compatibility facades over resources."""
    client = AsyncReadwiseClient("token")

    assert isinstance(client.v2._highlights, AsyncHighlightsResource)
    assert isinstance(client.v2._books, AsyncBooksResource)
    assert isinstance(client.v2._tags, AsyncV2TagsResource)
    assert isinstance(client.v2._export, AsyncExportResource)
    assert isinstance(client.v2._review, AsyncReviewResource)
    assert isinstance(client.v3._documents, AsyncDocumentsResource)
    assert isinstance(client.v3._tags, AsyncV3TagsResource)


@pytest.mark.asyncio
async def test_async_versioned_clients_delegate_model_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatibility methods return the exact model objects supplied by resources."""
    client = AsyncReadwiseClient("token")
    highlight = Highlight(id=7, text="delegated highlight")
    document = Document(id="doc-7", url="https://example.test/doc-7")

    async def get_highlight(highlight_id: int) -> Highlight:
        assert highlight_id == 7
        return highlight

    async def get_document(document_id: str, *, with_content: bool = False) -> Document | None:
        assert document_id == "doc-7"
        assert with_content is True
        return document

    monkeypatch.setattr(client.v2._highlights, "get", get_highlight)
    monkeypatch.setattr(client.v3._documents, "get", get_document)

    assert await client.v2.get_highlight(7) is highlight
    assert await client.v3.get_document("doc-7", with_content=True) is document
