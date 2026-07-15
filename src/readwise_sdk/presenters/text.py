"""Plain-text digest presentation."""

from __future__ import annotations

from readwise_sdk.operations.digests import DigestData, DigestGrouping


def render(digest: DigestData) -> str:
    """Render digest data using the legacy plain-text contract."""
    lines = [
        digest.title,
        "=" * len(digest.title),
        "",
        f"{len(digest.highlights)} highlights",
        "",
    ]
    if digest.grouping in {DigestGrouping.DATE, DigestGrouping.BOOK}:
        for name, highlights in digest.groups:
            lines.extend([name, "-" * len(name)])
            for highlight in highlights:
                lines.append(f"  {highlight.text}")
                if highlight.note:
                    lines.append(f"  Note: {highlight.note}")
                lines.append("")
    else:
        for highlight in digest.highlights:
            lines.append(highlight.text)
            if highlight.note:
                lines.append(f"Note: {highlight.note}")
            lines.append("")
    return "\n".join(lines)


__all__ = ["render"]
