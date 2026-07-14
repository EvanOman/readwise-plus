"""CSV digest presentation."""

from __future__ import annotations

import csv
from io import StringIO

from readwise_sdk.operations.digests import DigestData


def render(digest: DigestData) -> str:
    """Render digest data using the legacy CSV contract."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "text", "note", "location", "book_id", "highlighted_at", "tags"])
    for highlight in digest.highlights:
        writer.writerow(
            [
                highlight.id,
                highlight.text,
                highlight.note or "",
                highlight.location or "",
                highlight.book_id or "",
                highlight.highlighted_at.isoformat() if highlight.highlighted_at else "",
                ",".join(tag.name for tag in (highlight.tags or [])),
            ]
        )
    return output.getvalue()


__all__ = ["render"]
