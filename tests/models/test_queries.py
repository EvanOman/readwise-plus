"""Tests for operation input models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from readwise_sdk.models.queries import BookSearch, DocumentSearch, HighlightSearch
from readwise_sdk.v2.models import BookCategory
from readwise_sdk.v3.models import DocumentCategory, DocumentLocation


class TestDocumentSearch:
    """Tests for document search inputs."""

    def test_normalizes_whitespace_and_tags(self) -> None:
        """Surrounding whitespace and empty or duplicate tags are normalized."""
        updated_after = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)

        search = DocumentSearch(
            location=DocumentLocation.LATER,
            category=DocumentCategory.ARTICLE,
            updated_after=updated_after,
            tags=("  python ", "", "ai", "python", "   "),
            query="  Python SDK  ",
        )

        assert search.location is DocumentLocation.LATER
        assert search.category is DocumentCategory.ARTICLE
        assert search.updated_after is updated_after
        assert search.tags == ("python", "ai")
        assert search.query == "Python SDK"

    @pytest.mark.parametrize(("provided", "expected"), [(-10, 1), (0, 1), (101, 100)])
    def test_clamps_limit(self, provided: int, expected: int) -> None:
        """Document result limits stay within the operation's 1..100 bounds."""
        assert DocumentSearch(limit=provided).limit == expected

    def test_converts_whitespace_only_query_to_none(self) -> None:
        """A query with no searchable content is treated as absent."""
        assert DocumentSearch(query=" \n\t ").query is None


class TestHighlightSearch:
    """Tests for highlight search inputs."""

    def test_normalizes_query_and_clamps_limit(self) -> None:
        """Highlight search owns query trimming and its 1..200 limit bounds."""
        search = HighlightSearch(query="  systems thinking ", limit=500)

        assert search.query == "systems thinking"
        assert search.limit == 200

    def test_rejects_non_positive_book_id(self) -> None:
        """A book filter must identify an actual positive Readwise book ID."""
        with pytest.raises(ValidationError):
            HighlightSearch(book_id=0)


class TestBookSearch:
    """Tests for book search inputs."""

    def test_normalizes_optional_text_filters(self) -> None:
        """Source and query filters are stripped, with blank values removed."""
        search = BookSearch(category=BookCategory.BOOKS, source="  kindle ", query="   ")

        assert search.category is BookCategory.BOOKS
        assert search.source == "kindle"
        assert search.query is None

    @pytest.mark.parametrize(("provided", "expected"), [(-1, 1), (0, 1), (101, 100)])
    def test_clamps_limit(self, provided: int, expected: int) -> None:
        """Book result limits stay within the operation's 1..100 bounds."""
        assert BookSearch(limit=provided).limit == expected
