"""Tests for the base client."""

import httpx
import pytest
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


def test_client_requires_api_key() -> None:
    """Test that client raises error when no API key is provided."""
    with pytest.raises(AuthenticationError, match="API key is required"):
        ReadwiseClient()


def test_client_with_explicit_api_key(api_key: str) -> None:
    """Test client initialization with explicit API key."""
    client = ReadwiseClient(api_key=api_key)
    assert client.api_key == api_key


def test_client_with_env_api_key(mock_env_api_key: str) -> None:
    """Test client initialization with environment API key."""
    client = ReadwiseClient()
    assert client.api_key == mock_env_api_key


def test_client_context_manager(api_key: str) -> None:
    """Test client as context manager."""
    with ReadwiseClient(api_key=api_key) as client:
        assert client._client is None  # Lazy initialization
    # After exiting, client should be closed
    assert client._client is None


@respx.mock
def test_validate_token_success(api_key: str) -> None:
    """Test successful token validation."""
    respx.get(f"{READWISE_API_V2_BASE}/auth/").mock(return_value=httpx.Response(204))

    client = ReadwiseClient(api_key=api_key)
    assert client.validate_token() is True


@respx.mock
def test_validate_token_failure(api_key: str) -> None:
    """Test failed token validation."""
    respx.get(f"{READWISE_API_V2_BASE}/auth/").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    client = ReadwiseClient(api_key=api_key)
    with pytest.raises(AuthenticationError):
        client.validate_token()


@respx.mock
def test_handle_404(api_key: str) -> None:
    """Test 404 response handling."""
    respx.get(f"{READWISE_API_V2_BASE}/highlights/99999/").mock(
        return_value=httpx.Response(404, text="Not found")
    )

    client = ReadwiseClient(api_key=api_key)
    with pytest.raises(NotFoundError):
        client.get(f"{READWISE_API_V2_BASE}/highlights/99999/")


@respx.mock
def test_handle_429_with_retry_after(api_key: str) -> None:
    """Test rate limit response with Retry-After header."""
    respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
        return_value=httpx.Response(
            429,
            text="Rate limited",
            headers={"Retry-After": "60"},
        )
    )

    client = ReadwiseClient(api_key=api_key, max_retries=0)
    with pytest.raises(RateLimitError) as exc_info:
        client.get(f"{READWISE_API_V2_BASE}/highlights/")

    assert exc_info.value.retry_after == 60


@respx.mock
def test_handle_400(api_key: str) -> None:
    """Test validation error response."""
    respx.post(f"{READWISE_API_V2_BASE}/highlights/").mock(
        return_value=httpx.Response(400, text='{"text": "required"}')
    )

    client = ReadwiseClient(api_key=api_key)
    with pytest.raises(ValidationError):
        client.post(f"{READWISE_API_V2_BASE}/highlights/", json={})


@respx.mock
def test_handle_500(api_key: str) -> None:
    """Test server error response."""
    respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
        return_value=httpx.Response(500, text="Internal server error")
    )

    client = ReadwiseClient(api_key=api_key, max_retries=0)
    with pytest.raises(ServerError) as exc_info:
        client.get(f"{READWISE_API_V2_BASE}/highlights/")

    assert exc_info.value.status_code == 500


@respx.mock
def test_pagination(api_key: str) -> None:
    """Test pagination through results."""
    call_count = 0

    def pagination_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 1}, {"id": 2}],
                    "next": f"{READWISE_API_V2_BASE}/highlights/?page=2",
                },
            )
        else:
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 3}],
                    "next": None,
                },
            )

    respx.get(url__startswith=f"{READWISE_API_V2_BASE}/highlights/").mock(
        side_effect=pagination_side_effect
    )

    client = ReadwiseClient(api_key=api_key)
    results = list(client.paginate(f"{READWISE_API_V2_BASE}/highlights/"))

    assert len(results) == 3
    assert results[0]["id"] == 1
    assert results[1]["id"] == 2
    assert results[2]["id"] == 3
    assert call_count == 2


@respx.mock
def test_retry_on_connection_error(api_key: str) -> None:
    """Test retry logic on connection errors."""
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ConnectError("Connection failed")
        return httpx.Response(200, json={"ok": True})

    respx.get(f"{READWISE_API_V2_BASE}/test/").mock(side_effect=side_effect)

    client = ReadwiseClient(api_key=api_key, max_retries=3, retry_backoff=0.01)
    response = client.get(f"{READWISE_API_V2_BASE}/test/")

    assert response.status_code == 200
    assert call_count == 2
