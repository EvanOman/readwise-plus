"""JSON file persistence for synchronization checkpoints."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from readwise_sdk.models import SyncCheckpoint

STATE_VERSION = 1

_CHECKPOINT_KEYS = {
    "last_highlight_sync",
    "last_book_sync",
    "last_document_sync",
    "last_sync_time",
}
_SYNC_MANAGER_KEYS = {"total_syncs"}
_BATCH_SYNC_KEYS = {
    "total_highlights_synced",
    "total_books_synced",
    "total_documents_synced",
    "errors",
}
_POLLER_KEYS = {"last_poll_time", "poll_count", "error_count", "last_error"}
_LEGACY_KEYS = _CHECKPOINT_KEYS | _SYNC_MANAGER_KEYS | _BATCH_SYNC_KEYS | _POLLER_KEYS


class JsonFileStateStore:
    """Persist versioned checkpoints and migrate every existing JSON schema."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> SyncCheckpoint:
        """Load canonical or recognized legacy state without masking bad files."""
        if not self.path.exists():
            return SyncCheckpoint()

        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Unable to load sync state from {self.path}") from error

        if not isinstance(data, dict):
            raise ValueError(f"Unknown sync state schema in {self.path}")

        version = data.get("version")
        if version is not None:
            if type(version) is not int or version != STATE_VERSION:
                raise ValueError(f"Unknown sync state version {version!r} in {self.path}")
        elif not (_LEGACY_KEYS & data.keys()):
            raise ValueError(f"Unknown sync state schema in {self.path}")

        checkpoint_data = {key: data.get(key) for key in _CHECKPOINT_KEYS}
        if "last_poll_time" in data and checkpoint_data["last_sync_time"] is None:
            checkpoint_data["last_sync_time"] = data.get("last_poll_time")

        try:
            return SyncCheckpoint.model_validate(checkpoint_data)
        except ValidationError as error:
            raise ValueError(f"Invalid sync checkpoint in {self.path}") from error

    def save(self, checkpoint: SyncCheckpoint) -> None:
        """Write the canonical versioned JSON schema with legacy ISO formatting."""
        data: dict[str, object] = {"version": STATE_VERSION}
        for key in _CHECKPOINT_KEYS:
            value = getattr(checkpoint, key)
            data[key] = value.isoformat() if value is not None else None
        self._write(data)

    def load_legacy[StateT](
        self,
        factory: Callable[[dict[str, Any]], StateT],
        default: Callable[[], StateT],
    ) -> StateT:
        """Load a compatibility state using its historical error suppression."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if not isinstance(data, dict):
                    return default()
                return factory(data)
            except Exception:
                pass
        return default()

    def save_legacy(self, data: Mapping[str, object]) -> None:
        """Write an unversioned compatibility schema exactly as supplied."""
        self._write(data)

    def _write(self, data: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(dict(data), indent=2))


__all__ = ["JsonFileStateStore", "STATE_VERSION"]
