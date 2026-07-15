"""Guard the dependency boundary: importing the core package must not pull in
the optional CLI (Typer/Rich) or MCP (FastMCP) dependencies.

Run in a fresh subprocess rather than in-process: by the time this test would
run inside the main pytest session, other test modules (e.g. ``tests/mcp/``)
have almost certainly already imported ``typer``/``rich``/``mcp`` into
``sys.modules``, which would make an in-process check meaningless.

The subprocess also blocks ``typer``/``rich``/``mcp`` (and their transitive
CLI-only helpers ``click``/``pygments``) at import time before importing the
core package. This is deliberate: ``httpx`` itself has an optional bundled
CLI (the ``httpx`` command) that opportunistically imports ``click``/``rich``/
``pygments`` *if they happen to already be installed*, wrapped in its own
``try/except ImportError``. In this project's dev environment they ARE
installed (as CLI/MCP test dependencies), so a plain "was it imported"
check would fail on that unrelated httpx behavior rather than on anything
readwise_sdk does. Blocking the imports simulates the real-world case of a
core-only install (no ``[cli]``/``[mcp]`` extras) and lets httpx's own
graceful fallback do its job, while still failing loudly if any
readwise_sdk core module tries to import one of these names directly.
"""

from __future__ import annotations

import subprocess
import sys

_PROBE = """
import sys

_BLOCKED = {"typer", "rich", "mcp", "fastmcp", "click", "pygments"}


class _BlockOptionalAdapterDeps:
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in _BLOCKED:
            raise ImportError(f"blocked for core-isolation probe: {fullname}")
        return None


sys.meta_path.insert(0, _BlockOptionalAdapterDeps())

import readwise_sdk  # noqa: F401
import readwise_sdk.operations  # noqa: F401
from readwise_sdk.sdk import AsyncReadwise, Readwise  # noqa: F401

leaked = sorted(name for name in ("typer", "rich", "mcp") if name in sys.modules)
print(",".join(leaked))
"""


def test_core_import_does_not_load_cli_or_mcp_dependencies() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"importing readwise_sdk core requires an optional CLI/MCP dependency:\n{result.stderr}"
    )
    leaked = result.stdout.strip()
    assert leaked == "", f"importing readwise_sdk core pulled in optional dependencies: {leaked}"
