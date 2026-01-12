"""Pydantic models for Readwise API v2."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BookCategory(str, Enum):
    """Categories for books/sources in Readwise."""

    BOOKS = "books"
    ARTICLES = "articles"
    TWEETS = "tweets"
    PODCASTS = "podcasts"
    SUPPLEMENTALS = "supplementals"


class HighlightColor(str, Enum):
    """Available highlight colors."""

    YELLOW = "yellow"
    BLUE = "blue"
    PINK = "pink"
    ORANGE = "orange"
    GREEN = "green"
    PURPLE = "purple"


class Tag(BaseModel):
    """A tag attached to a highlight or book."""

    id: int
    name: str

    model_config = {"extra": "ignore"}


class Highlight(BaseModel):
    """A highlight from a book or article."""

    id: int
    text: str
    note: str | None = None
    location: int | None = None
    location_type: str | None = None
    url: str | None = None
    color: HighlightColor | None = None
    highlighted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    book_id: int | None = None
    tags: list[Tag] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @field_validator("color", mode="before")
    @classmethod
    def parse_color(cls, v: Any) -> HighlightColor | None:
        """Parse color string to enum, returning None if invalid."""
        if v is None or v == "":
            return None
        try:
            return HighlightColor(v)
        except ValueError:
            return None

    @field_validator("highlighted_at", "created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime | None:
        """Parse datetime strings."""
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Handle Z suffix for UTC
            v = v.replace("Z", "+00:00")
            return datetime.fromisoformat(v)
        return None


class Book(BaseModel):
    """A book or source containing highlights."""

    id: int
    title: str
    author: str | None = None
    category: BookCategory | None = None
    source: str | None = None
    num_highlights: int = 0
    last_highlight_at: datetime | None = None
    updated: datetime | None = None
    cover_image_url: str | None = None
    highlights_url: str | None = None
    source_url: str | None = None
    asin: str | None = None
    tags: list[Tag] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @field_validator("category", mode="before")
    @classmethod
    def parse_category(cls, v: Any) -> BookCategory | None:
        """Parse category string to enum, returning None if invalid."""
        if v is None or v == "":
            return None
        try:
            return BookCategory(v)
        except ValueError:
            return None

    @field_validator("last_highlight_at", "updated", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime | None:
        """Parse datetime strings."""
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            v = v.replace("Z", "+00:00")
            return datetime.fromisoformat(v)
        return None


class DailyReview(BaseModel):
    """A daily review containing selected highlights."""

    review_id: int
    review_url: str
    review_completed: bool = False
    highlights: list[Highlight] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class HighlightCreate(BaseModel):
    """Data for creating a new highlight."""

    text: str = Field(..., max_length=8191)
    title: str | None = Field(default=None, max_length=511)
    author: str | None = Field(default=None, max_length=1024)
    source_url: str | None = Field(default=None, max_length=2047)
    source_type: str | None = Field(default=None, min_length=3, max_length=64)
    category: BookCategory | None = None
    note: str | None = Field(default=None, max_length=8191)
    location: int | None = None
    location_type: str | None = None
    highlighted_at: datetime | None = None
    highlight_url: str | None = None
    image_url: str | None = None

    model_config = {"extra": "ignore"}

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to API request format."""
        data: dict[str, Any] = {"text": self.text}

        if self.title:
            data["title"] = self.title
        if self.author:
            data["author"] = self.author
        if self.source_url:
            data["source_url"] = self.source_url
        if self.source_type:
            data["source_type"] = self.source_type
        if self.category:
            data["category"] = self.category.value
        if self.note:
            data["note"] = self.note
        if self.location is not None:
            data["location"] = self.location
        if self.location_type:
            data["location_type"] = self.location_type
        if self.highlighted_at:
            data["highlighted_at"] = self.highlighted_at.isoformat()
        if self.highlight_url:
            data["highlight_url"] = self.highlight_url
        if self.image_url:
            data["image_url"] = self.image_url

        return data


class HighlightUpdate(BaseModel):
    """Data for updating an existing highlight."""

    text: str | None = Field(default=None, max_length=8191)
    note: str | None = Field(default=None, max_length=8191)
    location: int | None = None
    url: str | None = None
    color: HighlightColor | None = None

    model_config = {"extra": "ignore"}

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to API request format, only including set fields."""
        data: dict[str, Any] = {}

        if self.text is not None:
            data["text"] = self.text
        if self.note is not None:
            data["note"] = self.note
        if self.location is not None:
            data["location"] = self.location
        if self.url is not None:
            data["url"] = self.url
        if self.color is not None:
            data["color"] = self.color.value

        return data


class ExportBook(BaseModel):
    """A book with highlights from the export endpoint."""

    user_book_id: int
    title: str
    author: str | None = None
    readable_title: str | None = None
    source: str | None = None
    cover_image_url: str | None = None
    unique_url: str | None = None
    book_tags: list[Tag] = Field(default_factory=list)
    category: BookCategory | None = None
    document_note: str | None = None
    readwise_url: str | None = None
    source_url: str | None = None
    asin: str | None = None
    highlights: list[Highlight] = Field(default_factory=list)

    model_config = {"extra": "ignore"}

    @field_validator("category", mode="before")
    @classmethod
    def parse_category(cls, v: Any) -> BookCategory | None:
        """Parse category string to enum."""
        if v is None or v == "":
            return None
        try:
            return BookCategory(v)
        except ValueError:
            return None
