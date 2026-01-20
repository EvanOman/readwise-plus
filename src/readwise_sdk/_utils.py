"""Internal utility functions shared across the SDK.

These utilities are not part of the public API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from readwise_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ReadwiseError,
    ServerError,
    ValidationError,
)


def handle_response(response: httpx.Response) -> httpx.Response:
    """Handle HTTP response and raise appropriate exceptions.

    Args:
        response: The HTTP response to handle.

    Returns:
        The response if successful.

    Raises:
        AuthenticationError: If status is 401.
        NotFoundError: If status is 404.
        RateLimitError: If status is 429.
        ValidationError: If status is 400.
        ServerError: If status is 5xx.
        ReadwiseError: For other error statuses.
    """
    if response.is_success:
        return response

    body = response.text
    status = response.status_code

    if status == 401:
        raise AuthenticationError(response_body=body)
    if status == 404:
        raise NotFoundError(response_body=body)
    if status == 429:
        retry_after = response.headers.get("Retry-After")
        raise RateLimitError(
            retry_after=int(retry_after) if retry_after else None,
            response_body=body,
        )
    if status == 400:
        raise ValidationError(message=f"Validation error: {body}", response_body=body)
    if status >= 500:
        raise ServerError(
            message=f"Server error: {body}",
            status_code=status,
            response_body=body,
        )
    raise ReadwiseError(
        message=f"Unexpected error: {body}",
        status_code=status,
        response_body=body,
    )


def parse_pagination_cursor(
    next_cursor: str,
    current_url: str,
    current_params: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Parse a pagination cursor, handling both full URLs and cursor strings.

    Args:
        next_cursor: The next cursor value (URL or cursor string).
        current_url: The current URL being paginated.
        current_params: The current query parameters.

    Returns:
        Tuple of (url, params) for the next request.
    """
    if next_cursor.startswith("http"):
        parsed = urlparse(next_cursor)
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        return url, params
    params = current_params.copy()
    params["pageCursor"] = next_cursor
    return current_url, params


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
