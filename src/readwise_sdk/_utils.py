"""Internal utility functions shared across the SDK.

These utilities are not part of the public API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from readwise_sdk.transport.errors import handle_response as handle_response
from readwise_sdk.transport.pagination import (
    parse_pagination_cursor as parse_pagination_cursor,
)


def parse_datetime_string(value: Any) -> datetime | None:
    """Parse a datetime value from various formats.

    Args:
        value: A datetime, string, or None.

    Returns:
        Parsed datetime or None.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle Z suffix for UTC
        v = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


def truncate_string(value: str | None, max_length: int) -> tuple[str | None, bool]:
    """Truncate a string to max length with ellipsis.

    Args:
        value: The string to truncate, or None.
        max_length: Maximum length including ellipsis.

    Returns:
        Tuple of (truncated_value, was_truncated).
    """
    if value is None:
        return None, False
    if len(value) <= max_length:
        return value, False
    return value[: max_length - 3] + "...", True
