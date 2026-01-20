"""Pydantic models for Readwise Reader API v3."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from readwise_sdk._utils import parse_datetime_string


class DocumentLocation(str, Enum):
    """Location/status of a document in Reader."""

    NEW = "new"
    LATER = "later"
    ARCHIVE = "archive"
    FEED = "feed"


class DocumentCategory(str, Enum):
    """Category of a document in Reader."""

    ARTICLE = "article"
    EMAIL = "email"
    RSS = "rss"
    HIGHLIGHT = "highlight"
    NOTE = "note"
    PDF = "pdf"
    EPUB = "epub"
    TWEET = "tweet"
    VIDEO = "video"


class DocumentTag(BaseModel):
    """A tag in Reader."""

    key: str  # The tag identifier/key
    name: str  # The display name

    model_config = {"extra": "ignore"}


class Document(BaseModel):
    """A document in Readwise Reader."""

    id: str
    url: str
    source_url: str | None = None
    title: str | None = None
    author: str | None = None
    source: str | None = None
    category: DocumentCategory | None = None
    location: DocumentLocation | None = None
    tags: list[str] = Field(default_factory=list)  # Tags are just strings in v3
    site_name: str | None = None
    word_count: int | None = None
    reading_time: int | None = None  # In minutes
    created_at: datetime | None = None
    updated_at: datetime | None = None
    published_date: datetime | None = None
    summary: str | None = None
    image_url: str | None = None
    content: str | None = None  # HTML content, only when requested
    notes: str | None = None
    parent_id: str | None = None
    reading_progress: float | None = None
    first_opened_at: datetime | None = None
    last_opened_at: datetime | None = None
    saved_at: datetime | None = None
    last_moved_at: datetime | None = None

    model_config = {"extra": "ignore"}

    @field_validator("category", mode="before")
    @classmethod
    def parse_category(cls, v: Any) -> DocumentCategory | None:
        """Parse category string to enum."""
        if v is None or v == "":
            return None
        try:
            return DocumentCategory(v)
        except ValueError:
            return None

    @field_validator("location", mode="before")
    @classmethod
    def parse_location(cls, v: Any) -> DocumentLocation | None:
        """Parse location string to enum."""
        if v is None or v == "":
            return None
        try:
            return DocumentLocation(v)
        except ValueError:
            return None

    @field_validator(
        "created_at",
        "updated_at",
        "published_date",
        "first_opened_at",
        "last_opened_at",
        "saved_at",
        "last_moved_at",
        mode="before",
    )
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime | None:
        """Parse datetime strings."""
        return parse_datetime_string(v)

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> list[str]:
        """Parse tags which can be dicts or strings."""
        if v is None:
            return []
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict) and "name" in item:
                    result.append(item["name"])
            return result
        return []

    @field_validator("reading_time", mode="before")
    @classmethod
    def parse_reading_time(cls, v: Any) -> int | None:
        """Parse reading_time which can be int or string like '22 mins'."""
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            # Parse strings like "22 mins", "5 min", "1 minute"
            match = re.match(r"(\d+)", v)
            if match:
                return int(match.group(1))
            return None
        return None


class DocumentCreate(BaseModel):
    """Data for creating a new document in Reader."""

    url: str = Field(..., description="Unique identifier URL for the document")
    html: str | None = Field(default=None, description="HTML content (omit to scrape URL)")
    should_clean_html: bool | None = Field(
        default=None, description="Auto-clean HTML and extract metadata"
    )
    title: str | None = Field(default=None, description="Override parsed title")
    author: str | None = Field(default=None, description="Override parsed author")
    summary: str | None = Field(default=None, description="Document summary")
    published_date: datetime | None = Field(default=None, description="ISO 8601 format")
    image_url: str | None = Field(default=None, description="Cover image URL")
    location: DocumentLocation | None = Field(
        default=None, description="new, later, archive, or feed"
    )
    category: DocumentCategory | None = Field(default=None, description="Document category")
    saved_using: str | None = Field(default=None, description="Source identifier")
    tags: list[str] | None = Field(default=None, description="Array of tag strings")
    notes: str | None = Field(default=None, description="Top-level document note")

    model_config = {"extra": "ignore"}

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to API request format."""
        data: dict[str, Any] = {"url": self.url}

        if self.html is not None:
            data["html"] = self.html
        if self.should_clean_html is not None:
            data["should_clean_html"] = self.should_clean_html
        if self.title is not None:
            data["title"] = self.title
        if self.author is not None:
            data["author"] = self.author
        if self.summary is not None:
            data["summary"] = self.summary
        if self.published_date is not None:
            data["published_date"] = self.published_date.isoformat()
        if self.image_url is not None:
            data["image_url"] = self.image_url
        if self.location is not None:
            data["location"] = self.location.value
        if self.category is not None:
            data["category"] = self.category.value
        if self.saved_using is not None:
            data["saved_using"] = self.saved_using
        if self.tags is not None:
            data["tags"] = self.tags
        if self.notes is not None:
            data["notes"] = self.notes

        return data


class DocumentUpdate(BaseModel):
    """Data for updating a document in Reader."""

    title: str | None = None
    author: str | None = None
    summary: str | None = None
    published_date: datetime | None = None
    image_url: str | None = None
    location: DocumentLocation | None = None
    category: DocumentCategory | None = None
    tags: list[str] | None = None

    model_config = {"extra": "ignore"}

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to API request format, only including set fields."""
        data: dict[str, Any] = {}

        if self.title is not None:
            data["title"] = self.title
        if self.author is not None:
            data["author"] = self.author
        if self.summary is not None:
            data["summary"] = self.summary
        if self.published_date is not None:
            data["published_date"] = self.published_date.isoformat()
        if self.image_url is not None:
            data["image_url"] = self.image_url
        if self.location is not None:
            data["location"] = self.location.value
        if self.category is not None:
            data["category"] = self.category.value
        if self.tags is not None:
            data["tags"] = self.tags

        return data


class CreateDocumentResult(BaseModel):
    """Result of creating a document."""

    id: str
    url: str

    model_config = {"extra": "ignore"}
