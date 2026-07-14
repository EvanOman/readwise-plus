"""Shared pagination engines and endpoint-aware page decoders."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

import httpx

type Params = dict[str, Any]


class SyncPageGetter(Protocol):
    """Callable shape used to fetch one synchronous page."""

    def __call__(self, url: str, params: Params | None = None) -> httpx.Response: ...


class AsyncPageGetter(Protocol):
    """Callable shape used to fetch one asynchronous page."""

    def __call__(self, url: str, params: Params | None = None) -> Awaitable[httpx.Response]: ...


@dataclass(frozen=True, slots=True)
class DecodedPage:
    """Results and continuation value decoded from one response page."""

    results: Any
    next_cursor: Any


class PageDecoder(Protocol):
    """Decode one endpoint's results and continuation cursor."""

    def decode(self, data: Any) -> DecodedPage: ...

    def next_request(
        self,
        next_cursor: Any,
        current_url: str,
        current_params: Params,
    ) -> tuple[str, Params]: ...


@dataclass(frozen=True, slots=True)
class KeyedPage:
    """Compatibility decoder for callers supplying response key names."""

    results_key: str = "results"
    cursor_key: str = "next"

    def decode(self, data: Any) -> DecodedPage:
        return DecodedPage(
            results=data.get(self.results_key, []),
            next_cursor=data.get(self.cursor_key),
        )

    def next_request(
        self,
        next_cursor: Any,
        current_url: str,
        current_params: Params,
    ) -> tuple[str, Params]:
        return parse_pagination_cursor(next_cursor, current_url, current_params)


class StandardV2Page(KeyedPage):
    """Decode standard Readwise v2 pages using the ``next`` URL."""

    def __init__(self) -> None:
        super().__init__(results_key="results", cursor_key="next")


class ExportV2Page(KeyedPage):
    """Decode Readwise v2 export pages using integer continuation cursors."""

    def __init__(self) -> None:
        super().__init__(results_key="results", cursor_key="nextPageCursor")


class ReaderV3Page(KeyedPage):
    """Decode Reader v3 pages using string continuation cursors."""

    def __init__(self) -> None:
        super().__init__(results_key="results", cursor_key="nextPageCursor")


def parse_pagination_cursor(
    next_cursor: Any,
    current_url: str,
    current_params: Params,
) -> tuple[str, Params]:
    """Parse a full next URL or add a scalar cursor to existing parameters."""
    next_cursor = str(next_cursor)  # Handle integer cursors from export API
    if next_cursor.startswith("http"):
        parsed = urlparse(next_cursor)
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        return url, params
    params = current_params.copy()
    params["pageCursor"] = next_cursor
    return current_url, params


def paginate(
    get_page: SyncPageGetter,
    url: str,
    params: Params | None = None,
    *,
    decoder: PageDecoder | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield items from every page using a synchronous page getter."""
    current_params = params.copy() if params else {}
    page_decoder = decoder or StandardV2Page()

    while True:
        response = get_page(url, params=current_params)
        page = page_decoder.decode(response.json())

        yield from page.results

        if not page.next_cursor:
            break

        url, current_params = page_decoder.next_request(
            page.next_cursor,
            url,
            current_params,
        )


async def paginate_async(
    get_page: AsyncPageGetter,
    url: str,
    params: Params | None = None,
    *,
    decoder: PageDecoder | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield items from every page using an asynchronous page getter."""
    current_params = params.copy() if params else {}
    page_decoder = decoder or StandardV2Page()

    while True:
        response = await get_page(url, params=current_params)
        page = page_decoder.decode(response.json())

        for item in page.results:
            yield item

        if not page.next_cursor:
            break

        url, current_params = page_decoder.next_request(
            page.next_cursor,
            url,
            current_params,
        )


__all__ = [
    "DecodedPage",
    "ExportV2Page",
    "KeyedPage",
    "PageDecoder",
    "ReaderV3Page",
    "StandardV2Page",
    "paginate",
    "paginate_async",
    "parse_pagination_cursor",
]
