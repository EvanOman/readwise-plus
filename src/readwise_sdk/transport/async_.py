"""Canonical asynchronous HTTP transport for the Readwise APIs."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from readwise_sdk.config import ClientConfig
from readwise_sdk.errors import AuthenticationError, RateLimitError, ReadwiseError
from readwise_sdk.transport.errors import handle_response
from readwise_sdk.transport.retry import (
    RETRYABLE_NETWORK_EXCEPTIONS,
    calculate_retry_delay,
    is_retryable_exception,
)


class AsyncTransport:
    """Own asynchronous HTTP construction, retries, and response translation."""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def raw_client(self) -> httpx.AsyncClient | None:
        """Return the initialized HTTP client without creating one."""
        return self._client

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily construct the configured HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Token {self.config.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": self.config.user_agent,
                },
            )
        return self._client

    async def close(self) -> None:
        """Close and discard the initialized HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated request with the existing retry behavior."""
        if not self.config.api_key:
            raise AuthenticationError(
                "API key is required. Set READWISE_API_KEY or pass api_key parameter."
            )

        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self.client.request(method, url, params=params, json=json)
                return handle_response(response)
            except RETRYABLE_NETWORK_EXCEPTIONS as error:
                last_error = error
                if attempt < self.config.max_retries and is_retryable_exception(error):
                    wait_time = calculate_retry_delay(
                        error,
                        self.config.retry_backoff,
                        attempt,
                    )
                    if wait_time is not None:
                        await asyncio.sleep(wait_time)
            except RateLimitError as error:
                last_error = error
                if attempt < self.config.max_retries and is_retryable_exception(error):
                    wait_time = calculate_retry_delay(
                        error,
                        self.config.retry_backoff,
                        attempt,
                    )
                    if wait_time is not None:
                        await asyncio.sleep(wait_time)
                else:
                    raise

        raise ReadwiseError(
            f"Request failed after {self.config.max_retries + 1} attempts: {last_error}"
        )

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", url, params=params)

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", url, json=json)

    async def patch(
        self,
        url: str,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make a PATCH request."""
        return await self.request("PATCH", url, json=json)

    async def delete(self, url: str) -> httpx.Response:
        """Make a DELETE request."""
        return await self.request("DELETE", url)


__all__ = ["AsyncTransport"]
