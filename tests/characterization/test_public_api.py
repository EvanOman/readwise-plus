"""Characterize the import surface that exists before the restructure."""

from __future__ import annotations

import importlib

import pytest

import readwise_sdk

ROOT_EXPORTS = [
    "ReadwiseClient",
    "AsyncReadwiseClient",
    "ReadwiseError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
    "Book",
    "BookCategory",
    "Highlight",
    "HighlightColor",
    "Tag",
    "DailyReview",
    "Document",
    "DocumentCategory",
    "DocumentCreate",
    "DocumentLocation",
    "DocumentTag",
    "HighlightManager",
    "BookManager",
    "DocumentManager",
    "SyncManager",
    "SyncState",
    "DigestBuilder",
    "DigestFormat",
    "BackgroundPoller",
    "TagWorkflow",
    "ReadingInbox",
]

PACKAGE_EXPORTS = {
    "readwise_sdk.managers": [
        "HighlightManager",
        "BookManager",
        "DocumentManager",
        "SyncManager",
        "SyncState",
        "AsyncHighlightManager",
        "AsyncBookManager",
        "AsyncDocumentManager",
        "AsyncSyncManager",
    ],
    "readwise_sdk.workflows": [
        "DigestBuilder",
        "DigestFormat",
        "BackgroundPoller",
        "TagWorkflow",
        "ReadingInbox",
    ],
    "readwise_sdk.contrib": [
        "HighlightPusher",
        "AsyncHighlightPusher",
        "SimpleHighlight",
        "PushResult",
        "UpdateResult",
        "DeleteResult",
        "TruncationInfo",
        "FieldTruncation",
        "DocumentImporter",
        "AsyncDocumentImporter",
        "ImportedDocument",
        "ImportResult",
        "BatchSync",
        "AsyncBatchSync",
        "BatchSyncConfig",
        "BatchSyncResult",
    ],
    "readwise_sdk.v2": [
        "ReadwiseV2Client",
        "AsyncReadwiseV2Client",
        "Book",
        "BookCategory",
        "Highlight",
        "HighlightColor",
        "HighlightCreate",
        "HighlightUpdate",
        "Tag",
        "DailyReview",
    ],
    "readwise_sdk.v3": [
        "ReadwiseV3Client",
        "AsyncReadwiseV3Client",
        "Document",
        "DocumentCategory",
        "DocumentLocation",
        "DocumentTag",
        "DocumentCreate",
        "DocumentUpdate",
    ],
}


def test_root_package_exports_are_exact_and_importable() -> None:
    """The root package's declared public names remain stable and usable."""
    assert readwise_sdk.__all__ == ROOT_EXPORTS
    assert isinstance(readwise_sdk.__version__, str)
    for name in ROOT_EXPORTS:
        assert getattr(readwise_sdk, name) is not None


@pytest.mark.parametrize(("module_name", "expected"), PACKAGE_EXPORTS.items())
def test_subpackage_exports_are_exact_and_importable(module_name: str, expected: list[str]) -> None:
    """Manager, workflow, contrib, and versioned imports are public today."""
    module = importlib.import_module(module_name)
    assert module.__all__ == expected
    for name in expected:
        assert getattr(module, name) is not None


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        ("readwise_sdk.client", "ReadwiseClient"),
        ("readwise_sdk.client", "AsyncReadwiseClient"),
        ("readwise_sdk.v2.client", "ReadwiseV2Client"),
        ("readwise_sdk.v2.async_client", "AsyncReadwiseV2Client"),
        ("readwise_sdk.v3.client", "ReadwiseV3Client"),
        ("readwise_sdk.v3.async_client", "AsyncReadwiseV3Client"),
        ("readwise_sdk.managers.highlights", "HighlightManager"),
        ("readwise_sdk.managers.books", "BookManager"),
        ("readwise_sdk.managers.documents", "DocumentManager"),
        ("readwise_sdk.managers.sync", "SyncManager"),
        ("readwise_sdk.workflows.digest", "DigestBuilder"),
        ("readwise_sdk.workflows.poller", "BackgroundPoller"),
        ("readwise_sdk.workflows.tags", "TagWorkflow"),
        ("readwise_sdk.workflows.inbox", "ReadingInbox"),
        ("readwise_sdk.contrib.highlight_push", "HighlightPusher"),
        ("readwise_sdk.contrib.document_import", "DocumentImporter"),
        ("readwise_sdk.contrib.batch_sync", "BatchSync"),
    ],
)
def test_existing_concrete_import_paths_remain_importable(
    module_name: str, class_name: str
) -> None:
    """Concrete module paths used before the refactor continue to resolve."""
    assert getattr(importlib.import_module(module_name), class_name) is not None
