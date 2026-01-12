"""Tests for exception classes."""

from readwise_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ReadwiseError,
    ServerError,
    ValidationError,
)


def test_readwise_error_basic() -> None:
    """Test basic ReadwiseError."""
    error = ReadwiseError("Something went wrong")
    assert str(error) == "Something went wrong"
    assert error.status_code is None
    assert error.response_body is None


def test_readwise_error_with_status_code() -> None:
    """Test ReadwiseError with status code."""
    error = ReadwiseError("Something went wrong", status_code=418)
    assert str(error) == "[418] Something went wrong"
    assert error.status_code == 418


def test_readwise_error_with_response_body() -> None:
    """Test ReadwiseError with response body."""
    error = ReadwiseError("Error", response_body='{"detail": "oops"}')
    assert error.response_body == '{"detail": "oops"}'


def test_authentication_error() -> None:
    """Test AuthenticationError defaults."""
    error = AuthenticationError()
    assert str(error) == "[401] Invalid or missing API token"
    assert error.status_code == 401


def test_rate_limit_error_without_retry_after() -> None:
    """Test RateLimitError without retry_after."""
    error = RateLimitError()
    assert str(error) == "[429] Rate limit exceeded"
    assert error.retry_after is None


def test_rate_limit_error_with_retry_after() -> None:
    """Test RateLimitError with retry_after."""
    error = RateLimitError(retry_after=60)
    assert str(error) == "[429] Rate limit exceeded (retry after 60s)"
    assert error.retry_after == 60


def test_not_found_error() -> None:
    """Test NotFoundError defaults."""
    error = NotFoundError()
    assert str(error) == "[404] Resource not found"
    assert error.status_code == 404


def test_validation_error() -> None:
    """Test ValidationError defaults."""
    error = ValidationError()
    assert str(error) == "[400] Validation error"
    assert error.status_code == 400


def test_server_error() -> None:
    """Test ServerError defaults."""
    error = ServerError()
    assert str(error) == "[500] Server error"
    assert error.status_code == 500


def test_server_error_custom_status() -> None:
    """Test ServerError with custom status code."""
    error = ServerError(message="Bad gateway", status_code=502)
    assert str(error) == "[502] Bad gateway"
    assert error.status_code == 502
