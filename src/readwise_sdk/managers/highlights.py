"""Legacy highlight manager compatibility shim."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from readwise_sdk.operations.compat import (
    SyncHighlightsResource,
    bulk_result_map,
    iter_sync,
    run_sync,
)
from readwise_sdk.operations.highlights import HighlightOperations
from readwise_sdk.v2.models import Highlight, HighlightCreate

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from readwise_sdk.client import ReadwiseClient


class HighlightManager:
    """Compatibility wrapper over canonical highlight operations."""

    def __init__(self, client: ReadwiseClient) -> None:
        self._client = client
        resource = SyncHighlightsResource(client)
        self._operations = HighlightOperations(resource, resource, resource)

    def get_all_highlights(self) -> list[Highlight]:
        return run_sync(self._operations.list())

    def get_highlights_since(
        self,
        *,
        days: int | None = None,
        hours: int | None = None,
        since: datetime | None = None,
    ) -> list[Highlight]:
        return run_sync(self._operations.since(days=days, hours=hours, since=since))

    def get_highlights_by_book(self, book_id: int) -> list[Highlight]:
        return run_sync(self._operations.list(book_id=book_id))

    def get_highlights_with_notes(self) -> list[Highlight]:
        return run_sync(self._operations.with_notes())

    def search_highlights(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
    ) -> list[Highlight]:
        return run_sync(self._operations.search_items(query, case_sensitive=case_sensitive))

    def filter_highlights(
        self,
        predicate: Callable[[Highlight], bool],
    ) -> Iterator[Highlight]:
        return iter_sync(self._operations.filter(predicate))

    def bulk_tag(self, highlight_ids: list[int], tag: str) -> dict[int, bool]:
        result = run_sync(self._operations.bulk_tag(highlight_ids, tag))
        return bulk_result_map(highlight_ids, result)

    def bulk_untag(self, highlight_ids: list[int], tag: str) -> dict[int, bool]:
        result = run_sync(self._operations.bulk_untag(highlight_ids, tag))
        return bulk_result_map(highlight_ids, result)

    def create_highlight(
        self,
        text: str,
        *,
        title: str | None = None,
        author: str | None = None,
        note: str | None = None,
        source_url: str | None = None,
    ) -> int:
        request = HighlightCreate(
            text=text,
            title=title,
            author=author,
            note=note,
            source_url=source_url,
        )
        ids = run_sync(self._operations.create(request))
        return ids[0] if ids else 0

    def get_highlight_count(self) -> int:
        return run_sync(self._operations.count())
