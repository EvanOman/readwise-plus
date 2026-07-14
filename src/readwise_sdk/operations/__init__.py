"""Canonical async-first operations for Readwise concepts."""

from readwise_sdk.operations.books import (
    BookOperations,
    BookSearchResult,
    BookWithHighlights,
    ReadingStatistics,
)
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

__all__ = [
    "BookOperations",
    "BookSearchResult",
    "BookWithHighlights",
    "DocumentOperations",
    "DocumentStatistics",
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
    "TruncationInfo",
]
