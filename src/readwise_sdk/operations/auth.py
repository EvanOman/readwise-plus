"""Canonical authentication operations."""

from __future__ import annotations

from typing import Protocol


class TokenResource(Protocol):
    async def validate_token(self) -> bool: ...


class AuthOperations:
    """Own authentication checks independently of compatibility adapters."""

    def __init__(self, resource: TokenResource) -> None:
        self._resource = resource

    async def validate_token(self) -> bool:
        return await self._resource.validate_token()


__all__ = ["AuthOperations", "TokenResource"]
