"""Translate HTTP responses into Readwise SDK exceptions."""

from __future__ import annotations

import httpx


def handle_response(response: httpx.Response) -> httpx.Response:
    """Return successful responses and map error statuses to SDK exceptions."""
    # Import locally so ``readwise_sdk.errors`` can re-export this compatibility
    # helper without creating an import cycle.
    from readwise_sdk.errors import (
        AuthenticationError,
        NotFoundError,
        RateLimitError,
        ReadwiseError,
        ServerError,
        ValidationError,
    )

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


__all__ = ["handle_response"]
