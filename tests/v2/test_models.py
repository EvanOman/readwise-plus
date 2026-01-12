"""Tests for Readwise API v2 models."""

from datetime import UTC, datetime

from readwise_sdk.v2.models import (
    Book,
    BookCategory,
    DailyReview,
    ExportBook,
    Highlight,
    HighlightColor,
    HighlightCreate,
    HighlightUpdate,
    Tag,
)


class TestTag:
    """Tests for Tag model."""

    def test_basic_tag(self) -> None:
        """Test basic tag creation."""
        tag = Tag(id=1, name="favorite")
        assert tag.id == 1
        assert tag.name == "favorite"

    def test_tag_from_api_response(self) -> None:
        """Test tag parsing from API response."""
        data = {"id": 42, "name": "to-review", "extra_field": "ignored"}
        tag = Tag.model_validate(data)
        assert tag.id == 42
        assert tag.name == "to-review"


class TestHighlight:
    """Tests for Highlight model."""

    def test_minimal_highlight(self) -> None:
        """Test highlight with minimal data."""
        highlight = Highlight(id=1, text="Some highlighted text")
        assert highlight.id == 1
        assert highlight.text == "Some highlighted text"
        assert highlight.note is None
        assert highlight.tags == []

    def test_full_highlight(self) -> None:
        """Test highlight with all fields."""
        data = {
            "id": 123,
            "text": "The quick brown fox",
            "note": "Great quote!",
            "location": 42,
            "location_type": "page",
            "url": "https://example.com/book#123",
            "color": "yellow",
            "highlighted_at": "2024-01-15T10:30:00Z",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-16T08:00:00Z",
            "book_id": 456,
            "tags": [{"id": 1, "name": "favorite"}],
        }
        highlight = Highlight.model_validate(data)

        assert highlight.id == 123
        assert highlight.text == "The quick brown fox"
        assert highlight.note == "Great quote!"
        assert highlight.location == 42
        assert highlight.color == HighlightColor.YELLOW
        assert highlight.book_id == 456
        assert len(highlight.tags) == 1
        assert highlight.tags[0].name == "favorite"
        assert highlight.highlighted_at is not None

    def test_highlight_empty_color(self) -> None:
        """Test highlight with empty color string."""
        data = {"id": 1, "text": "Test", "color": ""}
        highlight = Highlight.model_validate(data)
        assert highlight.color is None

    def test_highlight_invalid_color(self) -> None:
        """Test highlight with invalid color."""
        data = {"id": 1, "text": "Test", "color": "rainbow"}
        highlight = Highlight.model_validate(data)
        assert highlight.color is None

    def test_highlight_datetime_parsing(self) -> None:
        """Test datetime parsing from various formats."""
        data = {
            "id": 1,
            "text": "Test",
            "highlighted_at": "2024-01-15T10:30:00+00:00",
        }
        highlight = Highlight.model_validate(data)
        assert highlight.highlighted_at is not None
        assert highlight.highlighted_at.year == 2024


class TestBook:
    """Tests for Book model."""

    def test_minimal_book(self) -> None:
        """Test book with minimal data."""
        book = Book(id=1, title="Test Book")
        assert book.id == 1
        assert book.title == "Test Book"
        assert book.author is None
        assert book.category is None
        assert book.num_highlights == 0

    def test_full_book(self) -> None:
        """Test book with all fields."""
        data = {
            "id": 789,
            "title": "The Art of Programming",
            "author": "Jane Doe",
            "category": "books",
            "source": "kindle",
            "num_highlights": 42,
            "last_highlight_at": "2024-01-20T15:00:00Z",
            "updated": "2024-01-21T10:00:00Z",
            "cover_image_url": "https://example.com/cover.jpg",
            "highlights_url": "https://readwise.io/api/v2/books/789/highlights",
            "source_url": "https://amazon.com/dp/B123456",
            "asin": "B123456",
            "tags": [{"id": 1, "name": "tech"}],
        }
        book = Book.model_validate(data)

        assert book.id == 789
        assert book.title == "The Art of Programming"
        assert book.author == "Jane Doe"
        assert book.category == BookCategory.BOOKS
        assert book.source == "kindle"
        assert book.num_highlights == 42
        assert len(book.tags) == 1

    def test_book_invalid_category(self) -> None:
        """Test book with invalid category."""
        data = {"id": 1, "title": "Test", "category": "invalid"}
        book = Book.model_validate(data)
        assert book.category is None


class TestDailyReview:
    """Tests for DailyReview model."""

    def test_daily_review(self) -> None:
        """Test daily review parsing."""
        data = {
            "review_id": 12345,
            "review_url": "https://readwise.io/review/12345",
            "review_completed": False,
            "highlights": [
                {"id": 1, "text": "First highlight"},
                {"id": 2, "text": "Second highlight"},
            ],
        }
        review = DailyReview.model_validate(data)

        assert review.review_id == 12345
        assert review.review_url == "https://readwise.io/review/12345"
        assert review.review_completed is False
        assert len(review.highlights) == 2


class TestHighlightCreate:
    """Tests for HighlightCreate model."""

    def test_minimal_create(self) -> None:
        """Test minimal highlight creation."""
        create = HighlightCreate(text="New highlight")
        api_dict = create.to_api_dict()

        assert api_dict == {"text": "New highlight"}

    def test_full_create(self) -> None:
        """Test full highlight creation."""
        create = HighlightCreate(
            text="New highlight",
            title="Book Title",
            author="Author Name",
            source_url="https://example.com",
            source_type="custom_app",
            category=BookCategory.ARTICLES,
            note="My note",
            location=100,
            location_type="page",
            highlighted_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        )
        api_dict = create.to_api_dict()

        assert api_dict["text"] == "New highlight"
        assert api_dict["title"] == "Book Title"
        assert api_dict["author"] == "Author Name"
        assert api_dict["category"] == "articles"
        assert api_dict["location"] == 100
        assert "highlighted_at" in api_dict


class TestHighlightUpdate:
    """Tests for HighlightUpdate model."""

    def test_partial_update(self) -> None:
        """Test partial highlight update."""
        update = HighlightUpdate(note="Updated note")
        api_dict = update.to_api_dict()

        assert api_dict == {"note": "Updated note"}

    def test_color_update(self) -> None:
        """Test highlight color update."""
        update = HighlightUpdate(color=HighlightColor.PINK)
        api_dict = update.to_api_dict()

        assert api_dict == {"color": "pink"}


class TestExportBook:
    """Tests for ExportBook model."""

    def test_export_book(self) -> None:
        """Test export book parsing."""
        data = {
            "user_book_id": 123,
            "title": "Test Book",
            "author": "Test Author",
            "readable_title": "Test Book by Test Author",
            "source": "kindle",
            "category": "books",
            "highlights": [
                {"id": 1, "text": "Highlight 1"},
                {"id": 2, "text": "Highlight 2"},
            ],
        }
        export_book = ExportBook.model_validate(data)

        assert export_book.user_book_id == 123
        assert export_book.title == "Test Book"
        assert len(export_book.highlights) == 2
