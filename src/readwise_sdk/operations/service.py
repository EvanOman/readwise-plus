"""Container for canonical operation groups."""

from __future__ import annotations

from readwise_sdk.operations.documents import DocumentOperations, DocumentsResource


class ReadwiseService:
    """Compose canonical operations from low-level resources."""

    def __init__(self, *, documents: DocumentsResource) -> None:
        self.documents = DocumentOperations(documents)


__all__ = ["ReadwiseService"]
