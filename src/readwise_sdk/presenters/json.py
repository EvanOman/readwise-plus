"""JSON digest presentation."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from readwise_sdk.operations.digests import DigestData


def render(digest: DigestData) -> str:
    """Render digest data using the legacy indented JSON contract."""
    data = {
        "title": digest.title,
        "generated_at": datetime.now(UTC).isoformat(),
        "count": len(digest.highlights),
        "highlights": [
            {
                "id": highlight.id,
                "text": highlight.text,
                "note": highlight.note,
                "location": highlight.location,
                "book_id": highlight.book_id,
                "highlighted_at": (
                    highlight.highlighted_at.isoformat() if highlight.highlighted_at else None
                ),
                "tags": [tag.name for tag in (highlight.tags or [])],
            }
            for highlight in digest.highlights
        ],
    }
    return json.dumps(data, indent=2)


__all__ = ["render"]
