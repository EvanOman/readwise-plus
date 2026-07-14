# Migrating to the 0.3 concept-oriented API

`readwise-plus` `0.3` introduces `Readwise` and `AsyncReadwise` as the preferred SDK entry points, backed by a shared async-first operations layer that the CLI and MCP server now also call. **Nothing is removed.** Every import, class, and method that worked before `0.3` still works — the old surfaces (`ReadwiseClient`, `.v2`/`.v3`, managers, workflows, contrib) are now documented as compatibility APIs rather than the primary path.

You do not need to migrate existing code. Migrate incrementally, or only when touching a piece of code anyway.

## Why change

Before `0.3`, the SDK exposed multiple overlapping ways to do the same thing (`.v2.list_highlights()` vs. `HighlightManager.get_all_highlights()` vs. `HighlightPusher`), and the CLI and MCP server each reimplemented their own filtering, limits, and error handling on top of the low-level clients. `0.3` introduces one canonical operations layer — `readwise.documents`, `readwise.highlights`, `readwise.books`, `readwise.tags`, `readwise.digests`, `readwise.sync` — that the SDK facade, CLI, and MCP server all call, so behavior is consistent across every surface. `.v2`/`.v3` remain available as an explicit, documented low-level escape hatch (`.raw.v2` / `.raw.v3` from the new facade).

## Mapping: old → new

| Old | New | Notes |
|---|---|---|
| `from readwise_sdk import ReadwiseClient, AsyncReadwiseClient` | `from readwise_sdk import Readwise, AsyncReadwise` | Both old and new root imports work; `Readwise`/`AsyncReadwise` are now the documented entry points. |
| `client.v2.list_highlights(...)` | `readwise.highlights.search(HighlightSearch(...))` or `.list(...)` | `search()` takes a validated `HighlightSearch` input and returns a `HighlightSearchResult`; `.list()` takes the same filters as plain keyword arguments and returns `list[Highlight]`. |
| `client.v2.list_books(...)` | `readwise.books.search(BookSearch(...))` or `.list(...)` | Same pattern as highlights. |
| `client.v3.list_documents(...)` | `readwise.documents.search(DocumentSearch(...))` | Returns a `DocumentSearchResult` of `DocumentSummary` items (bounded, projected) rather than an unbounded iterator of full `Document` objects. Use `readwise.documents.get(id, with_content=True)` for the full document. |
| `client.v3.save_url(url, ...)` | `readwise.documents.save(DocumentCreate(url=url, ...))` | |
| `client.v3.update_document(id, update)` | `readwise.documents.update(id, update)` | |
| `client.v2.export_highlights(...)` | `readwise.highlights.export(...)` | |
| `client.v2.get_daily_review()` | No direct operation yet — use `readwise.raw.v2.get_daily_review()` | Daily review has not been ported to the operations layer; the low-level client still exposes it. |
| `HighlightManager(client)` / `BookManager(client)` / `DocumentManager(client)` | `readwise.highlights` / `readwise.books` / `readwise.documents` | Managers are now thin synchronous compatibility wrappers that delegate to the same operations the facade uses. |
| `DigestBuilder(client)` | `readwise.digests` (data) + `readwise_sdk.presenters.render_digest` (formatting) | `DigestBuilder` is now a compatibility wrapper combining a digest operation call with a presenter call. |
| `TagWorkflow(client)` | `readwise.tags` | |
| `ReadingInbox(client)` | `readwise.documents` (`.inbox()`, `.later()`, `.archive()`, `.statistics()`) | |
| `BackgroundPoller(client)` | `readwise.sync` (`.poll_once()`, `.full()`, `.incremental()`) | |
| `HighlightPusher(client)` | `readwise.highlights.push_batch(...)` / `.create_from_fields(...)` | |
| `DocumentImporter(client)` | `readwise.documents.save(...)` / `.get(..., with_content=True)` | |
| `BatchSync(client, config=...)` | `readwise.sync.batch_highlights(...)` / `.batch_books(...)` / `.batch_documents(...)` | |
| `readwise_sdk.v2.models.HighlightCreate` | `readwise_sdk.models.readwise.HighlightCreate` | `v2.models` and `v3.models` are now identity-preserving re-export modules — the same classes, importable from either path. |
| `readwise_sdk.v3.models.DocumentCreate` | `readwise_sdk.models.reader.DocumentCreate` | Same re-export relationship as above. |

### CLI

The command tree is unchanged in spirit and additive in practice — every pre-0.3 command still works with its original defaults (human-readable table output, no `--output` flag needed). New in `0.3`:

- A global `--output table|json|jsonl` option (must precede the subcommand, e.g. `readwise --output json sync full`), plus `--no-color` and `--quiet`.
- `readwise documents ...` alongside the original `readwise reader ...` (kept as a deprecated alias — it still works, and emits a stderr warning in table mode).
- New subcommands: `documents get/update/delete/move/tag`, `highlights update/delete/tag/untag`, `books show` (with highlights), `digest custom`, `sync status/reset`, `tags untagged/report`.

### MCP server

Unchanged. All nine tool names, argument schemas, and JSON return shapes are the same as before `0.3` — the tools now call the shared operations layer internally, but this is not observable from the MCP client side.

## Deprecation timeline

- **`0.3.0`** (this release): adds `Readwise`/`AsyncReadwise` and the operations layer; every pre-existing import, class, and method keeps working unchanged as a compatibility surface. No warnings are emitted yet.
- **Later `0.3.x`**: a `DeprecationWarning` will be added on construction of the legacy `ReadwiseClient`/`AsyncReadwiseClient` and the managers/workflows/contrib classes, pointing at the equivalent `Readwise`/`AsyncReadwise` operation. Import paths (`readwise_sdk.v2.models`, `readwise_sdk.managers`, etc.) keep working with no warning.
- **`0.4+`**: no new features land on the compatibility surface; new capabilities are added to the operations layer and facade only.
- **`1.0.0`**: the compatibility surface (`ReadwiseClient`/`AsyncReadwiseClient`, managers, workflows, contrib, and the `v2.models`/`v3.models` re-export modules) is removed. `.raw.v2`/`.raw.v3` on the facade remain as the supported low-level access path.

If you have code depending on the compatibility surface, there is no urgency: it is fully supported through the entire `0.x` series and will only be removed at a `1.0.0` release announced separately.
