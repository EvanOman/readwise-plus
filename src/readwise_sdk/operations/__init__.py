"""Canonical async-first operations for Readwise concepts."""

from readwise_sdk.operations.books import (
    BookOperations,
    BookSearchResult,
    BookWithHighlights,
    ReadingStatistics,
)
from readwise_sdk.operations.digests import DigestData, DigestGrouping, DigestOperations
from readwise_sdk.operations.documents import DocumentOperations, DocumentStatistics
from readwise_sdk.operations.highlights import (
    FieldTruncation,
    HighlightCreateResult,
    HighlightDeleteResult,
    HighlightExportGroup,
    HighlightExportResult,
    HighlightOperations,
    HighlightPushInput,
    HighlightPushResult,
    HighlightSearchResult,
    HighlightUpdateInput,
    HighlightUpdateResult,
    TruncationInfo,
)
from readwise_sdk.operations.service import ReadwiseService
from readwise_sdk.operations.sync import BatchSyncOutcome, SyncOperations
from readwise_sdk.operations.tags import (
    TagCleanupResult,
    TagOperations,
    TagPattern,
    TagReport,
)

__all__ = [
    "BookOperations",
    "BookSearchResult",
    "BookWithHighlights",
    "DocumentOperations",
    "DocumentStatistics",
    "DigestData",
    "DigestGrouping",
    "DigestOperations",
    "FieldTruncation",
    "HighlightCreateResult",
    "HighlightDeleteResult",
    "HighlightExportGroup",
    "HighlightExportResult",
    "HighlightOperations",
    "HighlightPushInput",
    "HighlightPushResult",
    "HighlightSearchResult",
    "HighlightUpdateInput",
    "HighlightUpdateResult",
    "ReadingStatistics",
    "ReadwiseService",
    "BatchSyncOutcome",
    "SyncOperations",
    "TagCleanupResult",
    "TagOperations",
    "TagPattern",
    "TagReport",
    "TruncationInfo",
]
