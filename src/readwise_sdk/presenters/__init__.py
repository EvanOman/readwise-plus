"""Protocol-neutral presenters for SDK operation results."""

from __future__ import annotations

from enum import Enum

from readwise_sdk.operations.digests import DigestData
from readwise_sdk.presenters import csv as csv_presenter
from readwise_sdk.presenters import json as json_presenter
from readwise_sdk.presenters import markdown as markdown_presenter
from readwise_sdk.presenters import text as text_presenter


class DigestFormat(str, Enum):
    """Supported legacy digest output formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"
    TEXT = "text"


def render_digest(digest: DigestData, output_format: DigestFormat) -> str:
    """Render digest data with the selected presenter."""
    if output_format is DigestFormat.JSON:
        return json_presenter.render(digest)
    if output_format is DigestFormat.CSV:
        return csv_presenter.render(digest)
    if output_format is DigestFormat.TEXT:
        return text_presenter.render(digest)
    return markdown_presenter.render(digest)


__all__ = ["DigestFormat", "render_digest"]
