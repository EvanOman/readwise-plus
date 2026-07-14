"""Persistence contract for synchronization checkpoints."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from readwise_sdk.models import SyncCheckpoint


@runtime_checkable
class StateStore(Protocol):
    """Load and save the checkpoint used by synchronization operations."""

    def load(self) -> SyncCheckpoint:
        """Return the persisted checkpoint, or an empty checkpoint when absent."""
        ...

    def save(self, checkpoint: SyncCheckpoint) -> None:
        """Persist a checkpoint."""
        ...


class MemoryStateStore:
    """Keep a synchronization checkpoint in memory."""

    def __init__(self, checkpoint: SyncCheckpoint | None = None) -> None:
        self._checkpoint = checkpoint or SyncCheckpoint()

    def load(self) -> SyncCheckpoint:
        """Return the current in-memory checkpoint."""
        return self._checkpoint

    def save(self, checkpoint: SyncCheckpoint) -> None:
        """Replace the current in-memory checkpoint."""
        self._checkpoint = checkpoint


__all__ = ["MemoryStateStore", "StateStore"]
