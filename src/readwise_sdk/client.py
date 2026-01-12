"""Base HTTP client for Readwise API."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx

from readwise_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ReadwiseError,
    ServerError,
    ValidationError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

# API base URLs
READWISE_API_V2_BASE = "https://readwise.io/api/v2"
READWISE_API_V3_BASE = "https://readwise.io/api/v3"

# Default configuration
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 0.5


class BaseClient:
    """Base HTTP client with authentication and error handling."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> None:
        """Initialize the client.

        Args:
            api_key: Readwise API token. If not provided, reads from READWISE_API_KEY env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Base backoff time between retries (exponential).
        """
        self.api_key = api_key or os.environ.get("READWISE_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "API key is required. Set READWISE_API_KEY or pass api_key parameter."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazily initialize and return the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "readwise-sdk/0.1.0",
                },
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> BaseClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.is_success:
            return response

        body = response.text
        status = response.status_code

        if status == 401:
            raise AuthenticationError(response_body=body)
        elif status == 404:
            raise NotFoundError(response_body=body)
        elif status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                retry_after=int(retry_after) if retry_after else None,
                response_body=body,
            )
        elif status == 400:
            raise ValidationError(message=f"Validation error: {body}", response_body=body)
        elif status >= 500:
            raise ServerError(
                message=f"Server error: {body}",
                status_code=status,
                response_body=body,
            )
        else:
            raise ReadwiseError(
                message=f"Unexpected error: {body}",
                status_code=status,
                response_body=body,
            )

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic."""
        import time

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, url, params=params, json=json)
                return self._handle_response(response)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff * (2**attempt)
                    time.sleep(wait_time)
            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries and e.retry_after:
                    time.sleep(e.retry_after)
                else:
                    raise

        raise ReadwiseError(f"Request failed after {self.max_retries + 1} attempts: {last_error}")

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Make a GET request."""
        return self._request("GET", url, params=params)

    def post(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Make a POST request."""
        return self._request("POST", url, json=json)

    def patch(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Make a PATCH request."""
        return self._request("PATCH", url, json=json)

    def delete(self, url: str) -> httpx.Response:
        """Make a DELETE request."""
        return self._request("DELETE", url)


class ReadwiseClient(BaseClient):
    """Synchronous Readwise client with access to v2 and v3 APIs."""

    def validate_token(self) -> bool:
        """Validate the API token.

        Returns:
            True if the token is valid.

        Raises:
            AuthenticationError: If the token is invalid.
        """
        response = self.get(f"{READWISE_API_V2_BASE}/auth/")
        return response.status_code == 204

    def paginate(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        results_key: str = "results",
        cursor_key: str = "next",
    ) -> Iterator[dict[str, Any]]:
        """Iterate through paginated results.

        Args:
            url: The API endpoint URL.
            params: Optional query parameters.
            results_key: Key in response containing the results list.
            cursor_key: Key in response containing the next page URL/cursor.

        Yields:
            Individual result items from each page.
        """
        params = params.copy() if params else {}

        while True:
            response = self.get(url, params=params)
            data = response.json()

            results = data.get(results_key, [])
            yield from results

            next_cursor = data.get(cursor_key)
            if not next_cursor:
                break

            # Handle both full URLs and cursor strings
            if next_cursor.startswith("http"):
                # Extract path and query from full URL
                from urllib.parse import parse_qs, urlparse

                parsed = urlparse(next_cursor)
                url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            else:
                params["pageCursor"] = next_cursor


class AsyncReadwiseClient:
    """Asynchronous Readwise client with access to v2 and v3 APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> None:
        """Initialize the async client.

        Args:
            api_key: Readwise API token. If not provided, reads from READWISE_API_KEY env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Base backoff time between retries (exponential).
        """
        self.api_key = api_key or os.environ.get("READWISE_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "API key is required. Set READWISE_API_KEY or pass api_key parameter."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "readwise-sdk/0.1.0",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> AsyncReadwiseClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.is_success:
            return response

        body = response.text
        status = response.status_code

        if status == 401:
            raise AuthenticationError(response_body=body)
        elif status == 404:
            raise NotFoundError(response_body=body)
        elif status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                retry_after=int(retry_after) if retry_after else None,
                response_body=body,
            )
        elif status == 400:
            raise ValidationError(message=f"Validation error: {body}", response_body=body)
        elif status >= 500:
            raise ServerError(
                message=f"Server error: {body}",
                status_code=status,
                response_body=body,
            )
        else:
            raise ReadwiseError(
                message=f"Unexpected error: {body}",
                status_code=status,
                response_body=body,
            )

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an async HTTP request with retry logic."""
        import asyncio

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, params=params, json=json)
                return self._handle_response(response)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff * (2**attempt)
                    await asyncio.sleep(wait_time)
            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries and e.retry_after:
                    await asyncio.sleep(e.retry_after)
                else:
                    raise

        raise ReadwiseError(f"Request failed after {self.max_retries + 1} attempts: {last_error}")

    async def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Make an async GET request."""
        return await self._request("GET", url, params=params)

    async def post(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Make an async POST request."""
        return await self._request("POST", url, json=json)

    async def patch(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Make an async PATCH request."""
        return await self._request("PATCH", url, json=json)

    async def delete(self, url: str) -> httpx.Response:
        """Make an async DELETE request."""
        return await self._request("DELETE", url)

    async def validate_token(self) -> bool:
        """Validate the API token.

        Returns:
            True if the token is valid.

        Raises:
            AuthenticationError: If the token is invalid.
        """
        response = await self.get(f"{READWISE_API_V2_BASE}/auth/")
        return response.status_code == 204
