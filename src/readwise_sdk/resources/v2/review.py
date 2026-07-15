"""Asynchronous access to the Readwise v2 daily-review endpoint."""

from __future__ import annotations

from readwise_sdk.models.readwise import DailyReview
from readwise_sdk.transport.async_ import AsyncTransport


class AsyncReviewResource:
    """Build the daily-review request and decode its model."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(self) -> DailyReview:
        response = await self._transport.get(f"{self._transport.config.v2_base_url}/review/")
        return DailyReview.model_validate(response.json())


__all__ = ["AsyncReviewResource"]
