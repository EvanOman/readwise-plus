"""Exception hierarchy for the Readwise SDK."""

from __future__ import annotations


class ReadwiseError(Exception):
    """Base exception for all Readwise SDK errors."""

    def __init__(
        self, message: str, status_code: int | None = None, response_body: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class AuthenticationError(ReadwiseError):
    """Raised when authentication fails (401 Unauthorized)."""

    def __init__(
        self, message: str = "Invalid or missing API token", response_body: str | None = None
    ) -> None:
        super().__init__(message, status_code=401, response_body=response_body)


class RateLimitError(ReadwiseError):
    """Raised when rate limit is exceeded (429 Too Many Requests)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message, status_code=429, response_body=response_body)
        self.retry_after = retry_after

    def __str__(self) -> str:
        base = super().__str__()
        if self.retry_after:
            return f"{base} (retry after {self.retry_after}s)"
        return base


class NotFoundError(ReadwiseError):
    """Raised when a requested resource is not found (404 Not Found)."""

    def __init__(
        self, message: str = "Resource not found", response_body: str | None = None
    ) -> None:
        super().__init__(message, status_code=404, response_body=response_body)


class ValidationError(ReadwiseError):
    """Raised when request validation fails (400 Bad Request)."""

    def __init__(self, message: str = "Validation error", response_body: str | None = None) -> None:
        super().__init__(message, status_code=400, response_body=response_body)


class ServerError(ReadwiseError):
    """Raised when the server returns an error (5xx)."""

    def __init__(
        self,
        message: str = "Server error",
        status_code: int = 500,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response_body=response_body)
