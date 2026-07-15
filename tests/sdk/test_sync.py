"""Public contract tests for the preferred synchronous SDK facade."""

from __future__ import annotations

import asyncio
import inspect
import threading
from concurrent.futures import CancelledError
from functools import partial

import anyio
import httpx
import pytest
import respx

from readwise_sdk.models import DocumentSearch, DocumentSearchResult
from readwise_sdk.v2.client import ReadwiseV2Client
from readwise_sdk.v3.client import ReadwiseV3Client

V3_BASE = "https://readwise.io/api/v3"


@pytest.fixture(autouse=True)
def _wake_portal_loop_in_restricted_test_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep AnyIO responsive where the sandbox blocks asyncio's self-pipe write."""
    import readwise_sdk.sdk.sync as sync_sdk

    start_blocking_portal = sync_sdk.start_blocking_portal

    def loop_factory() -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()

        def wakeup() -> None:
            loop.call_later(0.01, wakeup)

        loop.call_soon(wakeup)
        return loop

    monkeypatch.setattr(
        sync_sdk,
        "start_blocking_portal",
        partial(
            start_blocking_portal,
            backend_options={"loop_factory": loop_factory},
        ),
    )


def test_readwise_is_importable_from_the_package_root() -> None:
    """The preferred sync facade is available through the documented import."""
    from readwise_sdk import Readwise

    assert Readwise.__module__ == "readwise_sdk.sdk.sync"


@respx.mock
def test_ordinary_sync_use_returns_a_bounded_operation_result() -> None:
    """A synchronous operation materializes the async-first service result."""
    from readwise_sdk import Readwise

    route = respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "doc-1",
                        "url": "https://reader/doc-1",
                        "source_url": "https://example.test/python",
                        "title": "Python",
                    }
                ],
                "nextPageCursor": None,
            },
        )
    )

    with Readwise(api_key="token") as readwise:
        result = readwise.documents.search(DocumentSearch(query="python", limit=1))

    assert isinstance(result, DocumentSearchResult)
    assert [item.id for item in result.items] == ["doc-1"]
    assert result.truncated is True
    assert len(route.calls) == 1


@pytest.mark.asyncio
async def test_sync_use_inside_a_running_event_loop_uses_its_own_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling the sync facade from an active loop neither reuses nor nests that loop."""
    from readwise_sdk import Readwise

    caller_thread = threading.get_ident()
    caller_loop = asyncio.get_running_loop()

    with Readwise(api_key="token") as readwise:

        async def search(search_input: DocumentSearch) -> tuple[int, asyncio.AbstractEventLoop]:
            assert search_input.query == "threaded"
            return threading.get_ident(), asyncio.get_running_loop()

        monkeypatch.setattr(readwise._async.documents, "search", search)
        worker_thread, worker_loop = readwise.documents.search(DocumentSearch(query="threaded"))

    assert worker_thread != caller_thread
    assert worker_loop is not caller_loop


def test_context_manager_owns_and_closes_every_lifecycle_resource() -> None:
    """The facade closes its async client, portal thread, and native raw client."""
    from readwise_sdk import Readwise

    readwise = Readwise(api_key="token")

    with readwise as entered:
        async_transport = entered._async._client.client
        raw_transport = entered.raw._client.client
        portal = entered._portal
        assert entered is readwise
        assert async_transport.is_closed is False
        assert raw_transport.is_closed is False
        assert portal is not None

    assert async_transport.is_closed is True
    assert raw_transport.is_closed is True
    assert readwise._async._client._client is None
    assert readwise.raw._client._client is None
    assert readwise._portal is None
    with pytest.raises(RuntimeError, match="portal is not running"):
        portal.call(lambda: None)


@respx.mock
def test_repeated_operations_reuse_one_facade_instance() -> None:
    """One entered facade supports multiple calls through the same portal and client."""
    from readwise_sdk import Readwise

    route = respx.get(f"{V3_BASE}/list/").mock(
        return_value=httpx.Response(200, json={"results": [], "nextPageCursor": None})
    )

    with Readwise(api_key="token") as readwise:
        portal = readwise._portal
        async_transport = readwise._async._client.client
        first = readwise.documents.search(DocumentSearch(query="first"))
        second = readwise.documents.search(DocumentSearch(query="second"))

        assert readwise._portal is portal
        assert readwise._async._client.client is async_transport

    assert first.items == []
    assert second.items == []
    assert len(route.calls) == 2


def test_exception_crosses_the_portal_with_its_type_and_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operation exceptions are not wrapped or translated by the sync bridge."""
    from readwise_sdk import Readwise

    class PortalError(Exception):
        pass

    error = PortalError("operation failed")

    with Readwise(api_key="token") as readwise:

        async def get(document_id: str, *, with_content: bool = False) -> None:
            assert document_id == "doc-1"
            assert with_content is True
            raise error

        monkeypatch.setattr(readwise._async.documents, "get", get)
        with pytest.raises(PortalError, match="operation failed") as captured:
            readwise.documents.get("doc-1", with_content=True)

    assert captured.value is error


def test_close_cancels_an_in_flight_operation_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing cannot hang behind unfinished portal work and safely tolerates repeats."""
    from readwise_sdk import Readwise

    readwise = Readwise(api_key="token")
    readwise.__enter__()
    started = threading.Event()
    outcome: list[BaseException] = []

    async def get(document_id: str, *, with_content: bool = False) -> None:
        del document_id, with_content
        started.set()
        await anyio.sleep_forever()

    monkeypatch.setattr(readwise._async.documents, "get", get)

    def call_operation() -> None:
        try:
            readwise.documents.get("doc-1")
        except BaseException as error:
            outcome.append(error)

    operation_thread = threading.Thread(target=call_operation, daemon=True)
    operation_thread.start()
    assert started.wait(timeout=2)

    close_thread = threading.Thread(target=readwise.close, daemon=True)
    close_thread.start()
    close_thread.join(timeout=2)
    operation_thread.join(timeout=2)

    assert close_thread.is_alive() is False
    assert operation_thread.is_alive() is False
    assert len(outcome) == 1
    assert isinstance(outcome[0], CancelledError)
    assert readwise._portal is None
    readwise.close()


def test_operations_require_an_open_context() -> None:
    """A facade that has not entered its owned portal fails with a direct message."""
    from readwise_sdk import Readwise

    readwise = Readwise(api_key="token")

    with pytest.raises(RuntimeError, match="Readwise is not open; use it as a context manager"):
        readwise.books.count()


def test_raw_retains_the_native_synchronous_compatibility_clients() -> None:
    """The raw escape hatch retains legacy sync iterators instead of bridging streams."""
    from readwise_sdk import Readwise

    readwise = Readwise(api_key="token")

    assert isinstance(readwise.raw.v2, ReadwiseV2Client)
    assert isinstance(readwise.raw.v3, ReadwiseV3Client)
    assert readwise.raw.v2 is readwise.raw.v2
    assert readwise.raw.v3 is readwise.raw.v3
    assert readwise.raw.v2._client is readwise.raw._client
    assert readwise.raw.v3._client is readwise.raw._client


def test_sync_surface_exposes_stage_fourteen_operation_groups() -> None:
    """The synchronous facade exposes synchronization with the other groups."""
    from readwise_sdk import Readwise

    readwise = Readwise(api_key="token")

    assert readwise.tags is readwise.tags
    assert readwise.digests is readwise.digests
    assert readwise.sync is readwise.sync
    assert readwise.documents is readwise.documents
    assert readwise.highlights is readwise.highlights
    assert readwise.books is readwise.books
    assert readwise.raw is readwise.raw


def test_sync_operation_groups_do_not_expose_async_streaming() -> None:
    """The new sync API includes bounded methods but does not bridge async iterators."""
    from readwise_sdk import Readwise

    readwise = Readwise(api_key="token")

    assert not hasattr(readwise.highlights, "filter")
    for operation_group in (
        readwise.documents,
        readwise.highlights,
        readwise.books,
        readwise.tags,
        readwise.digests,
        readwise.sync,
    ):
        assert not any(
            inspect.iscoroutinefunction(value)
            for name, value in vars(type(operation_group)).items()
            if not name.startswith("_") and callable(value)
        )


def test_constructor_arguments_reach_async_operations_and_native_raw_clients() -> None:
    """Both owned clients receive the facade's complete transport configuration."""
    from readwise_sdk import Readwise

    readwise = Readwise("token", 12.5, 7, 1.25)
    expected = ("token", 12.5, 7, 1.25)

    assert (
        readwise._async._client.api_key,
        readwise._async._client.timeout,
        readwise._async._client.max_retries,
        readwise._async._client.retry_backoff,
    ) == expected
    assert (
        readwise.raw._client.api_key,
        readwise.raw._client.timeout,
        readwise.raw._client.max_retries,
        readwise.raw._client.retry_backoff,
    ) == expected
