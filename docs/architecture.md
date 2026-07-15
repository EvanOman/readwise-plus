# Architecture

A short map of the `0.3` layering for contributors. Dependencies point downward only — nothing in a lower layer imports from a higher one.

```
Public models and errors
          ↓
Transport and pagination        (readwise_sdk.transport)
          ↓
Low-level resource clients      (readwise_sdk.resources.v2 / .v3)
          ↓
Operations / service core       (readwise_sdk.operations, readwise_sdk.operations.service.ReadwiseService)
          ↓
SDK facade | CLI adapter | MCP adapter
          (readwise_sdk.sdk)   (readwise_sdk.cli)   (readwise_sdk.mcp)
```

- **Resource clients** (`readwise_sdk.resources.v2`, `readwise_sdk.resources.v3`) know Readwise/Reader endpoints only: build requests, decode models, expose raw pagination. No filtering, formatting, or multi-request composition.
- **Operations** (`readwise_sdk.operations.*`, composed by `ReadwiseService`) own everything that used to be scattered across managers, workflows, contrib, the CLI, and the MCP server: search filtering, limits, bulk-operation semantics, digest data selection, sync checkpoints. Operations return typed result models (`DocumentSearchResult`, `HighlightSearchResult`, `BulkResult`, `SyncResult`, ...), never Rich objects or JSON strings.
- **Adapters** — the `Readwise`/`AsyncReadwise` facade (`readwise_sdk.sdk`), the CLI (`readwise_sdk.cli`), and the MCP server (`readwise_sdk.mcp`) — each call the same operations and own only their own protocol concerns: argument parsing, credential discovery, human/JSON rendering, exit codes or MCP error envelopes.
- **`readwise.raw.v2` / `readwise.raw.v3`** on the facade are an explicit low-level escape hatch onto the same resource clients used everywhere else — not a second implementation.

## Compatibility layer

`ReadwiseClient`/`AsyncReadwiseClient`, the `managers`, `workflows`, and `contrib` packages, and the `v2.models`/`v3.models` modules are compatibility wrappers: they delegate to the operations layer (often through a synchronous `run_sync` bridge) and translate results back into their original pre-0.3 return shapes. They are not a parallel implementation to keep in sync by hand. New behavior is added to the operations layer first; a compatibility method is added only if it needs to preserve an existing pre-0.3 signature. See [MIGRATION.md](../MIGRATION.md) for the full old→new mapping and removal timeline.

## Sync vs. async

The operations layer is async-first (MCP and network I/O are naturally async). `AsyncReadwise` uses it directly. `Readwise` runs the same async operations through a dedicated `anyio` blocking portal on its own event-loop thread (`readwise_sdk.sdk.sync`) rather than reimplementing each operation synchronously — so `Readwise` and `AsyncReadwise` cannot drift from each other by construction. The portal is owned and closed by the facade's context manager; using `Readwise` outside a `with` block raises rather than silently leaking a thread.
