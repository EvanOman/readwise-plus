"""Base HTTP client for Readwise API."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import httpx

from readwise_sdk.config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    ClientConfig,
    resolve_api_key,
)
from readwise_sdk.config import (
    READWISE_API_V2_BASE as CONFIG_READWISE_API_V2_BASE,
)
from readwise_sdk.config import (
    READWISE_API_V3_BASE as CONFIG_READWISE_API_V3_BASE,
)
from readwise_sdk.errors import AuthenticationError, RateLimitError, ReadwiseError
from readwise_sdk.transport.async_ import AsyncTransport
from readwise_sdk.transport.errors import handle_response
from readwise_sdk.transport.pagination import KeyedPage, paginate, paginate_async
from readwise_sdk.transport.retry import (
    RETRYABLE_NETWORK_EXCEPTIONS,
    calculate_retry_delay,
    is_retryable_exception,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from readwise_sdk.v2.async_client import AsyncReadwiseV2Client
    from readwise_sdk.v2.client import ReadwiseV2Client
    from readwise_sdk.v3.async_client import AsyncReadwiseV3Client
    from readwise_sdk.v3.client import ReadwiseV3Client

# Compatibility alias for the previous module-level user agent.
_USER_AGENT = DEFAULT_USER_AGENT
READWISE_API_V2_BASE = CONFIG_READWISE_API_V2_BASE
READWISE_API_V3_BASE = CONFIG_READWISE_API_V3_BASE


class BaseClient:
    """Base HTTP client with authentication and error handling."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        *,
        _defer_validation: bool = False,
    ) -> None:
        """Initialize the client.

        Args:
            api_key: Readwise API token. If not provided, reads from READWISE_API_KEY env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Base backoff time between retries (exponential).
            _defer_validation: Internal flag used by create_optional(). Do not use directly.
        """
        resolved_api_key = resolve_api_key(api_key)
        if not resolved_api_key and not _defer_validation:
            raise AuthenticationError(
                "API key is required. Set READWISE_API_KEY or pass api_key parameter."
            )

        self._config = ClientConfig(
            api_key=resolved_api_key,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )

        self._client: httpx.Client | None = None

    @property
    def config(self) -> ClientConfig:
        """Return the immutable canonical client configuration."""
        return self._config

    @property
    def api_key(self) -> str | None:
        """Return the configured API key."""
        return self._config.api_key

    @api_key.setter
    def api_key(self, value: str | None) -> None:
        self._config = replace(self._config, api_key=value)

    @property
    def timeout(self) -> float:
        """Return the request timeout in seconds."""
        return self._config.timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._config = replace(self._config, timeout=value)

    @property
    def max_retries(self) -> int:
        """Return the maximum number of request retries."""
        return self._config.max_retries

    @max_retries.setter
    def max_retries(self, value: int) -> None:
        self._config = replace(self._config, max_retries=value)

    @property
    def retry_backoff(self) -> float:
        """Return the base exponential retry backoff in seconds."""
        return self._config.retry_backoff

    @retry_backoff.setter
    def retry_backoff(self, value: float) -> None:
        self._config = replace(self._config, retry_backoff=value)

    @property
    def is_configured(self) -> bool:
        """Check whether the client has an API key configured.

        Returns:
            True if an API key is set, False otherwise.
        """
        return bool(self.api_key)

    @property
    def client(self) -> httpx.Client:
        """Lazily initialize and return the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": self.config.user_agent,
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

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic."""
        if not self.api_key:
            raise AuthenticationError(
                "API key is required. Set READWISE_API_KEY or pass api_key parameter."
            )

        import time

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, url, params=params, json=json)
                return handle_response(response)
            except RETRYABLE_NETWORK_EXCEPTIONS as e:
                last_error = e
                if attempt < self.max_retries and is_retryable_exception(e):
                    wait_time = calculate_retry_delay(e, self.retry_backoff, attempt)
                    if wait_time is not None:
                        time.sleep(wait_time)
            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries and is_retryable_exception(e):
                    wait_time = calculate_retry_delay(e, self.retry_backoff, attempt)
                    if wait_time is not None:
                        time.sleep(wait_time)
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

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        *,
        _defer_validation: bool = False,
    ) -> None:
        """Initialize the client."""
        super().__init__(
            api_key, timeout, max_retries, retry_backoff, _defer_validation=_defer_validation
        )
        self._v2: ReadwiseV2Client | None = None
        self._v3: ReadwiseV3Client | None = None

    @classmethod
    def create_optional(
        cls,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> ReadwiseClient:
        """Create a client that does not raise if no API key is available.

        This factory method creates a client instance even when no API key is
        provided. Use the ``is_configured`` property to check whether the client
        can make requests. An ``AuthenticationError`` is raised at request time
        if the client is used without a valid key.

        This is useful for optional integrations where you want to check whether
        Readwise is configured before attempting to use it.

        Example::

            client = ReadwiseClient.create_optional()
            if client.is_configured:
                highlights = list(client.v2.list_highlights())

        Args:
            api_key: Readwise API token. If not provided, reads from READWISE_API_KEY env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Base backoff time between retries (exponential).

        Returns:
            A ReadwiseClient instance that may or may not be configured.
        """
        return cls(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            _defer_validation=True,
        )

    @property
    def v2(self) -> ReadwiseV2Client:
        """Access the Readwise API v2 client for highlights, books, and tags."""
        if self._v2 is None:
            from readwise_sdk.v2.client import ReadwiseV2Client

            self._v2 = ReadwiseV2Client(self)
        return self._v2

    @property
    def v3(self) -> ReadwiseV3Client:
        """Access the Readwise Reader API v3 client for documents."""
        if self._v3 is None:
            from readwise_sdk.v3.client import ReadwiseV3Client

            self._v3 = ReadwiseV3Client(self)
        return self._v3

    def validate_token(self) -> bool:
        """Validate the API token.

        Returns:
            True if the token is valid, False otherwise.
        """
        try:
            response = self.get(f"{self.config.v2_base_url}/auth/")
            return response.status_code == 204
        except AuthenticationError:
            return False

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
        yield from paginate(
            self.get,
            url,
            params,
            decoder=KeyedPage(results_key=results_key, cursor_key=cursor_key),
        )


class AsyncReadwiseClient:
    """Asynchronous Readwise client with access to v2 and v3 APIs.

    This client provides the same functionality as ReadwiseClient but with
    async/await support for non-blocking I/O operations.

    Example:
        async with AsyncReadwiseClient() as client:
            async for highlight in client.v2.list_highlights():
                print(highlight.text)

            # Concurrent requests with asyncio.gather
            docs = await asyncio.gather(
                client.v3.get_document("doc1"),
                client.v3.get_document("doc2"),
            )
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        *,
        _defer_validation: bool = False,
    ) -> None:
        """Initialize the async client.

        Args:
            api_key: Readwise API token. If not provided, reads from READWISE_API_KEY env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Base backoff time between retries (exponential).
            _defer_validation: Internal flag used by create_optional(). Do not use directly.
        """
        resolved_api_key = resolve_api_key(api_key)
        if not resolved_api_key and not _defer_validation:
            raise AuthenticationError(
                "API key is required. Set READWISE_API_KEY or pass api_key parameter."
            )

        self._config = ClientConfig(
            api_key=resolved_api_key,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )

        self._transport = AsyncTransport(self._config)
        self._v2: AsyncReadwiseV2Client | None = None
        self._v3: AsyncReadwiseV3Client | None = None

    @property
    def _client(self) -> httpx.AsyncClient | None:
        """Retain the legacy observable reference to the raw HTTP client."""
        return self._transport.raw_client

    @property
    def config(self) -> ClientConfig:
        """Return the immutable canonical client configuration."""
        return self._config

    @property
    def api_key(self) -> str | None:
        """Return the configured API key."""
        return self._config.api_key

    @api_key.setter
    def api_key(self, value: str | None) -> None:
        self._config = replace(self._config, api_key=value)
        self._transport.config = self._config

    @property
    def timeout(self) -> float:
        """Return the request timeout in seconds."""
        return self._config.timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._config = replace(self._config, timeout=value)
        self._transport.config = self._config

    @property
    def max_retries(self) -> int:
        """Return the maximum number of request retries."""
        return self._config.max_retries

    @max_retries.setter
    def max_retries(self, value: int) -> None:
        self._config = replace(self._config, max_retries=value)
        self._transport.config = self._config

    @property
    def retry_backoff(self) -> float:
        """Return the base exponential retry backoff in seconds."""
        return self._config.retry_backoff

    @retry_backoff.setter
    def retry_backoff(self, value: float) -> None:
        self._config = replace(self._config, retry_backoff=value)
        self._transport.config = self._config

    @property
    def is_configured(self) -> bool:
        """Check whether the client has an API key configured.

        Returns:
            True if an API key is set, False otherwise.
        """
        return bool(self.api_key)

    @classmethod
    def create_optional(
        cls,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> AsyncReadwiseClient:
        """Create an async client that does not raise if no API key is available.

        This factory method creates a client instance even when no API key is
        provided. Use the ``is_configured`` property to check whether the client
        can make requests. An ``AuthenticationError`` is raised at request time
        if the client is used without a valid key.

        This is useful for optional integrations where you want to check whether
        Readwise is configured before attempting to use it.

        Example::

            client = AsyncReadwiseClient.create_optional()
            if client.is_configured:
                async for highlight in client.v2.list_highlights():
                    print(highlight.text)

        Args:
            api_key: Readwise API token. If not provided, reads from READWISE_API_KEY env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff: Base backoff time between retries (exponential).

        Returns:
            An AsyncReadwiseClient instance that may or may not be configured.
        """
        return cls(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            _defer_validation=True,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the async HTTP client."""
        return self._transport.client

    @property
    def v2(self) -> AsyncReadwiseV2Client:
        """Access the async Readwise API v2 client for highlights, books, and tags."""
        if self._v2 is None:
            from readwise_sdk.v2.async_client import AsyncReadwiseV2Client

            self._v2 = AsyncReadwiseV2Client(self)
        return self._v2

    @property
    def v3(self) -> AsyncReadwiseV3Client:
        """Access the async Readwise Reader API v3 client for documents."""
        if self._v3 is None:
            from readwise_sdk.v3.async_client import AsyncReadwiseV3Client

            self._v3 = AsyncReadwiseV3Client(self)
        return self._v3

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._transport.close()

    async def __aenter__(self) -> AsyncReadwiseClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an async HTTP request with retry logic."""
        return await self._transport.request(method, url, params=params, json=json)

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
            True if the token is valid, False otherwise.
        """
        try:
            response = await self.get(f"{self.config.v2_base_url}/auth/")
            return response.status_code == 204
        except AuthenticationError:
            return False

    async def paginate(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        results_key: str = "results",
        cursor_key: str = "next",
    ) -> AsyncIterator[dict[str, Any]]:
        """Iterate through paginated results asynchronously.

        Args:
            url: The API endpoint URL.
            params: Optional query parameters.
            results_key: Key in response containing the results list.
            cursor_key: Key in response containing the next page URL/cursor.

        Yields:
            Individual result items from each page.
        """
        async for item in paginate_async(
            self.get,
            url,
            params,
            decoder=KeyedPage(results_key=results_key, cursor_key=cursor_key),
        ):
            yield item
