# Target Architecture for `readwise-plus`

## Executive Decision

**Introduce one canonical, async-first operations layer and make the SDK facade, CLI, and MCP server thin adapters over it.**

The existing v2/v3 clients should become low-level resource clients, not the primary place where user-facing behavior is composed. Managers, workflows, contrib helpers, CLI commands, and MCP tools should progressively delegate to the operations layer.

I recommend **Option A: an aggressive internal restructure released as `0.3.0`**, while retaining inexpensive compatibility shims throughout the `0.x` series. Remove deprecated APIs only at `1.0.0`.

The primary target API becomes:

```python
from readwise_sdk import AsyncReadwise

async with AsyncReadwise() as readwise:
    documents = await readwise.documents.search(
        query="python",
        location="later",
        limit=20,
    )
```

And synchronously:

```python
from readwise_sdk import Readwise

with Readwise() as readwise:
    documents = readwise.documents.search(
        query="python",
        location="later",
        limit=20,
    )
```

The CLI and MCP server call those same operations.

---

# 1. Current-State Assessment

## Strengths

### Clear external API boundaries

The repository correctly recognizes that Readwise v2 and Reader v3 are different APIs:

- v2 highlights, books, tags, export, and review live in `src/readwise_sdk/v2/client.py:24`.
- Reader documents and Reader tags live in `src/readwise_sdk/v3/client.py:23`.
- Their models are separated in `src/readwise_sdk/v2/models.py:14` and `src/readwise_sdk/v3/models.py:15`.

That distinction should remain at the resource layer.

### Useful typed models

The Pydantic models provide:

- Typed enums.
- Tolerant parsing of unknown categories and colors.
- API payload conversion through `to_api_dict()`.
- Normalization of Reader tags and HTML content.

Examples include:

- `HighlightCreate.to_api_dict()` in `src/readwise_sdk/v2/models.py:146`.
- `Document.merge_html_content()` in `src/readwise_sdk/v3/models.py:79`.
- `DocumentCreate.to_api_dict()` in `src/readwise_sdk/v3/models.py:183`.

These are good foundations. They need relocation and clearer naming more than replacement.

### Shared basic transport behavior

Authentication, retrying, response handling, and pagination are at least partially centralized:

- Retry behavior: `src/readwise_sdk/client.py:103` and `src/readwise_sdk/client.py:424`.
- HTTP status translation: `src/readwise_sdk/_utils.py:24`.
- Cursor parsing: `src/readwise_sdk/_utils.py:72`.
- Pagination: `src/readwise_sdk/client.py:245` and `src/readwise_sdk/client.py:487`.

### Strong behavioral coverage

Tests cover each major layer separately:

- Low-level clients.
- Sync and async managers.
- Workflows.
- Contrib helpers.
- CLI commands.
- All nine MCP tools.

That makes a staged restructuring practical, provided characterization tests are added before moving public contracts.

### Packaging boundaries are already sound

The package keeps optional surfaces separate:

- Core: `httpx`, `pydantic`.
- CLI: Typer and Rich.
- MCP: FastMCP.
- Console scripts remain distinct in `pyproject.toml`.

The target architecture should preserve those dependency boundaries.

---

## Structural Problems

### 1. `client.py` combines too many responsibilities

`src/readwise_sdk/client.py` currently owns:

- Authentication configuration.
- HTTP client construction.
- Retry policy.
- response handling.
- pagination.
- API client composition through `.v2` and `.v3`.
- public context-manager lifecycle.
- both sync and async implementations.

The sync and async implementations repeat almost the same request and pagination algorithms at `src/readwise_sdk/client.py:103` and `src/readwise_sdk/client.py:424`.

This is simultaneously a transport, client facade, retry engine, pagination engine, and dependency container.

### 2. Sync and async code are maintained as parallel copies

The duplication is substantial:

- `src/readwise_sdk/v2/client.py`: 395 lines.
- `src/readwise_sdk/v2/async_client.py`: 418 lines.
- `src/readwise_sdk/v3/client.py`: 311 lines.
- `src/readwise_sdk/v3/async_client.py`: 336 lines.
- `src/readwise_sdk/managers/async_managers.py`: 800 lines, largely mirroring the four synchronous manager modules.

For example, `HighlightManager.search_highlights()` at `src/readwise_sdk/managers/highlights.py:81` is repeated asynchronously at `src/readwise_sdk/managers/async_managers.py:97`.

Any semantic fix must currently be made at least twice, often more.

### 3. Managers are mostly alternate client APIs, not a distinct layer

Many manager methods simply materialize low-level iterators or rename an existing operation:

```python
return list(self._client.v2.list_highlights())
```

That pattern appears in `src/readwise_sdk/managers/highlights.py:27`, with similar wrappers for books and documents.

Other manager methods introduce business behavior, such as:

- Local text search.
- Bulk operations.
- Statistics.
- Date-range calculation.
- partial-failure handling.

Those two categories are mixed together. The result is an ambiguous layer: users cannot tell whether a manager is required, optional, or merely another spelling of `.v2`.

### 4. Workflows, managers, and contrib overlap heavily

There are multiple implementations of synchronization:

- `SyncManager` in `src/readwise_sdk/managers/sync.py:74`.
- `BackgroundPoller` in `src/readwise_sdk/workflows/poller.py:75`.
- `BatchSync` in `src/readwise_sdk/contrib/batch_sync.py:113`.
- Async counterparts in `async_managers.py` and `batch_sync.py`.

They each maintain related state, JSON persistence, timestamps, and callbacks, but with separate data models and behavior.

Other overlaps include:

- `HighlightManager.create_highlight()` versus `HighlightPusher`.
- `DocumentManager` versus `DocumentImporter`.
- Manager search methods versus MCP-local search.
- `TagWorkflow` versus manager bulk tagging and low-level tag methods.

The current directory names describe historical intent rather than architectural roles.

### 5. CLI and MCP implement operations independently

The CLI directly queries low-level clients:

- Highlight filtering and limiting: `src/readwise_sdk/cli/main.py:68`.
- Book listing: `src/readwise_sdk/cli/main.py:180`.
- Reader inbox listing: `src/readwise_sdk/cli/main.py:247`.
- Reader save/archive: `src/readwise_sdk/cli/main.py:285` and `src/readwise_sdk/cli/main.py:302`.

The MCP server independently implements:

- Enum validation.
- limit clamping.
- datetime parsing.
- local substring search.
- result projections.
- error translation.
- operation composition.

For example, document search is defined locally in `src/readwise_sdk/mcp/server.py:231`; highlight search repeats the same pattern at `src/readwise_sdk/mcp/server.py:402`; book search does so again at `src/readwise_sdk/mcp/server.py:549`.

These are operations, not MCP protocol concerns.

### 6. Presentation logic is mixed into business objects

`DigestBuilder` both queries data and renders Markdown, JSON, CSV, and text in `src/readwise_sdk/workflows/digest.py:27`.

Similarly:

- The CLI constructs bespoke JSON objects and Rich tables.
- MCP constructs different summary dictionaries in `src/readwise_sdk/mcp/server.py:79`.
- Neither output shape is a declared, reusable contract.

Data acquisition, business composition, and rendering should be independently testable.

### 7. Error behavior is inconsistent and sometimes hidden

Observed patterns include:

- `get_document()` returns `None` for missing documents at `src/readwise_sdk/v3/client.py:78`.
- Update and delete raise `NotFoundError`.
- Bulk manager operations catch `Exception` and return `False`.
- Tag workflows silently suppress tag failures at `src/readwise_sdk/workflows/tags.py:103`.
- Sync callbacks silently suppress arbitrary callback exceptions at `src/readwise_sdk/managers/sync.py:121`.
- MCP converts SDK errors into JSON strings.
- CLI frequently allows exceptions to escape through Typer.

There is no declared rule for whether an operation raises, returns a partial result, or suppresses errors.

### 8. Pagination is nominally generic but still ad hoc

`paginate()` accepts arbitrary result and cursor keys, and `parse_pagination_cursor()` handles URLs and cursor values. However, endpoint-specific assumptions leak into callers:

- V2 standard pagination uses `next`.
- V2 export uses integer cursors.
- V3 uses `nextPageCursor`.
- Reader filters accept a tag list, but `list_documents()` only sends the first tag at `src/readwise_sdk/v3/client.py:65`.

Pagination semantics should be represented by endpoint-specific page decoders, not string arguments passed around the package.

### 9. High-level code leaks API-version terminology

High-level operations import directly from `v2.models` and `v3.models`. The MCP server does this at `src/readwise_sdk/mcp/server.py:24`.

Versions are appropriate at the transport/resource boundary. User concepts should normally be called `highlights`, `books`, `documents`, and `reader_tags`.

### 10. The adapter layers are excluded from type checking

`just type` excludes the CLI and MCP packages in `Justfile:18`.

These are now first-class published surfaces. Their exclusion makes drift between the core, CLI, and MCP more likely.

### 11. One documented MCP parameter is currently ignored

`save_to_reader()` accepts `category` at `src/readwise_sdk/mcp/server.py:179`, but the constructed `DocumentCreate` at `src/readwise_sdk/mcp/server.py:211` does not include it.

Because MCP behavior must remain identical during restructuring, this discrepancy should first receive a characterization test. Fixing it should be a separate, explicit behavior-change PR.

---

# 2. Target Architecture

## Layering

```text
Public models and errors
          ↓
Transport and pagination
          ↓
Low-level resource clients
          ↓
Operations / service core
          ↓
SDK facade | CLI adapter | MCP adapter
```

Dependencies must point downward only.

The CLI and MCP packages must not call resource clients directly. Managers, workflows, and contrib compatibility classes should delegate to operations rather than reach into `.v2` or `.v3`.

---

## Proposed Layout

```text
src/readwise_sdk/
├── __init__.py
├── config.py
├── errors.py
├── models/
│   ├── __init__.py
│   ├── readwise.py
│   ├── reader.py
│   ├── queries.py
│   └── results.py
├── transport/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── retry.py
│   ├── pagination.py
│   ├── sync.py
│   └── async_.py
├── resources/
│   ├── __init__.py
│   ├── v2/
│   │   ├── highlights.py
│   │   ├── books.py
│   │   ├── tags.py
│   │   ├── export.py
│   │   └── review.py
│   └── v3/
│       ├── documents.py
│       └── tags.py
├── operations/
│   ├── __init__.py
│   ├── service.py
│   ├── documents.py
│   ├── highlights.py
│   ├── books.py
│   ├── tags.py
│   ├── digests.py
│   ├── imports.py
│   └── sync.py
├── state/
│   ├── __init__.py
│   ├── store.py
│   └── json_file.py
├── sdk/
│   ├── __init__.py
│   ├── async_.py
│   └── sync.py
├── presenters/
│   ├── __init__.py
│   ├── json.py
│   ├── tables.py
│   └── digests.py
├── cli/
│   ├── main.py
│   ├── context.py
│   ├── output.py
│   └── commands/
│       ├── documents.py
│       ├── highlights.py
│       ├── books.py
│       ├── tags.py
│       ├── digests.py
│       └── sync.py
├── mcp/
│   ├── server.py
│   ├── context.py
│   ├── output.py
│   └── tools/
│       ├── documents.py
│       ├── highlights.py
│       └── books.py
└── compat/
    ├── clients.py
    ├── managers.py
    ├── workflows.py
    └── contrib.py
```

Compatibility modules at the current paths should re-export or wrap these implementations.

---

## Core Abstractions

### `ClientConfig`

One immutable configuration object should own:

- API key.
- timeout.
- retry count.
- retry backoff.
- user agent.
- optional base-URL overrides for testing.

```python
@dataclass(frozen=True, slots=True)
class ClientConfig:
    api_key: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff: float = 0.5
```

CLI and MCP credential resolution may differ, but both must ultimately produce this same configuration.

### Transport

Provide native sync and async transports with identical interfaces:

```python
class AsyncTransport(Protocol):
    async def request(self, request: Request) -> Response: ...

class SyncTransport(Protocol):
    def request(self, request: Request) -> Response: ...
```

Shared components should own:

- Header construction.
- retry classification.
- backoff calculation.
- HTTP-to-SDK exception mapping.
- page decoding rules.

Only the actual `httpx.Client.request()` versus `httpx.AsyncClient.request()` call and sleeping mechanism should differ.

### Resource clients

Resources represent the exact remote APIs. They should:

- Build endpoint-specific requests.
- Decode API models.
- Expose raw pagination.
- Perform no local text search.
- Perform no Rich/JSON formatting.
- Perform no multi-resource workflow.
- Avoid broad exception suppression.

Examples:

```python
await resources.documents.get(document_id, with_content=True)
resources.highlights.iter(updated_after=...)
await resources.documents.update(document_id, update)
```

The v2/v3 distinction remains inside `resources/`.

### Operation inputs

Use explicit Pydantic input models or frozen dataclasses:

```python
class DocumentSearch:
    location: DocumentLocation | None
    category: DocumentCategory | None
    updated_after: datetime | None
    tags: tuple[str, ...]
    query: str | None
    limit: int
```

These types provide one place for:

- limit bounds.
- whitespace normalization.
- semantic validation.
- mutually exclusive options.
- default behavior.

Do not use Typer or FastMCP parameter objects in this layer.

### Operation results

Operations should return typed domain models or declared result types, never Rich objects or JSON strings.

Examples:

```python
class DocumentSearchResult(BaseModel):
    items: list[DocumentSummary]
    truncated: bool

class BulkResult[T](BaseModel):
    succeeded: list[T]
    failures: list[OperationFailure]

class SyncResult(BaseModel):
    highlights: list[Highlight]
    books: list[Book]
    documents: list[Document]
    checkpoint: SyncCheckpoint
```

`DocumentSummary`, `HighlightSummary`, and `BookSummary` are legitimate shared read models because CLI and MCP need the same semantic projection. Protocol-specific JSON shaping remains in the adapters.

### `ReadwiseService`

The service is the single public operation container:

```python
class ReadwiseService:
    documents: DocumentOperations
    highlights: HighlightOperations
    books: BookOperations
    tags: TagOperations
    digests: DigestOperations
    sync: SyncOperations
```

Representative operation definitions:

```python
result = await service.documents.search(input)
document = await service.documents.get(document_id, with_content=True)
created = await service.documents.save(input)
updated = await service.documents.update(document_id, input)

result = await service.highlights.search(input)
export = await service.highlights.export(input)
created = await service.highlights.create(input)

result = await service.books.search(input)
```

Each is defined once and used from three surfaces.

---

## What Belongs in the Operations Layer

Operations should own:

- Search filtering.
- result limits.
- bulk operation semantics.
- date-window calculation.
- multi-request composition.
- partial-failure policy.
- tag merging and normalization.
- digest data selection and grouping.
- synchronization and checkpoints.
- import and truncation policies.

Adapters should own:

- Reading command-line or MCP arguments.
- credential discovery.
- human rendering.
- JSON serialization.
- exit codes or MCP error envelopes.
- protocol lifecycle.

Resource clients should own only API calls.

---

## SDK as an Adapter

The SDK public API is itself an adapter over the service core.

### New preferred facade

```python
from readwise_sdk import AsyncReadwise, Readwise
```

Expose concept-oriented attributes:

```python
readwise.documents
readwise.highlights
readwise.books
readwise.tags
readwise.digests
readwise.sync
```

For advanced users, provide an explicitly low-level escape hatch:

```python
readwise.raw.v2
readwise.raw.v3
```

Do not retain `.v2` and `.v3` as the primary recommended API. They force users to know endpoint versions and encourage bypassing the operation core.

---

# 3. CLI Design

## Keep Typer

Retain Typer because:

- It already supports the current nested command structure.
- It is a published optional dependency.
- Existing tests use `CliRunner`.
- Replacing it would create migration cost without solving the architectural problem.

The problem is not Typer. The problem is that `cli/main.py` currently contains command declaration, client creation, API calls, formatting, and error behavior in one 752-line module.

Split command modules and make each command invoke exactly one service operation.

---

## Proposed Command Tree

```text
readwise
├── auth
│   └── check
├── documents
│   ├── list
│   ├── get
│   ├── save
│   ├── update
│   ├── delete
│   ├── move
│   └── tag
├── highlights
│   ├── list
│   ├── get
│   ├── create
│   ├── update
│   ├── delete
│   ├── export
│   ├── tag
│   └── untag
├── books
│   ├── list
│   └── get
├── tags
│   ├── list
│   ├── search
│   ├── report
│   ├── auto
│   ├── rename
│   ├── merge
│   └── delete
├── digest
│   ├── daily
│   ├── weekly
│   ├── book
│   └── custom
├── sync
│   ├── full
│   ├── incremental
│   ├── status
│   └── reset
└── version
```

### Compatibility aliases

Retain `readwise reader ...` as a deprecated alias for `readwise documents ...` throughout `0.x`.

Existing commands such as `reader inbox`, `reader save`, and `reader archive` should continue to work but emit a warning to stderr in human mode.

---

## Global Output Contract

Add a consistent global option:

```text
--output table|json|jsonl
```

Recommended defaults:

- Interactive terminal: `table`.
- Redirected stdout: still `table` unless explicitly requested; avoid surprising scripts.
- Automation and agents: `--output json` or `--output jsonl`.

Additional options:

```text
--pretty / --no-pretty
--no-color
--quiet
--api-key
```

### Output rules

- Machine-readable data goes to stdout.
- Warnings, progress, and errors go to stderr.
- JSON output never contains Rich markup or progress text.
- JSON contains full values; truncation is only a human-table concern.
- JSON uses stable named fields from result models.
- Streaming list commands support JSONL.
- Exit codes are consistent:
  - `0`: success.
  - `1`: SDK/API failure.
  - `2`: invalid command input.
  - `3`: not found.
  - `4`: partial bulk failure.

### Command implementation pattern

```python
@documents_app.command("list")
def list_documents(options: DocumentOptions) -> None:
    result = run_operation(
        lambda service: service.documents.search(options.to_input())
    )
    output.render(result)
```

No command should directly call `.v2`, `.v3`, or an HTTP client.

---

# 4. MCP Mapping

The nine existing MCP tool names and return behavior remain unchanged.

| Existing MCP tool | Core operation |
|---|---|
| `save_to_reader` | `service.documents.save()` |
| `search_documents` | `service.documents.search()` |
| `get_document` | `service.documents.get()` |
| `update_document` | `service.documents.update()` |
| `delete_document` | `service.documents.delete()` |
| `get_highlights` | `service.highlights.search()` |
| `export_highlights` | `service.highlights.export()` |
| `create_highlight` | `service.highlights.create()` |
| `get_books` | `service.books.search()` |

Each MCP function should contain only:

1. Protocol argument adaptation.
2. One service call.
3. Existing JSON-envelope rendering.
4. Existing MCP-compatible error translation.

Example target:

```python
@mcp.tool()
async def search_documents(...) -> str:
    try:
        result = await get_service().documents.search(
            DocumentSearchInput(...)
        )
        return render_mcp_documents(result)
    except ReadwiseError as error:
        return render_mcp_error(error)
```

## Behavior that must remain identical

Characterization tests should lock:

- Tool names and argument names.
- default and maximum limits.
- compact JSON strings.
- omission of `None` fields.
- not-found message text.
- invalid-enum error envelopes.
- current lenient datetime parsing.
- current summary fields.
- per-call client lifecycle, unless tests establish that reuse is invisible.
- current `save_to_reader(category=...)` behavior until separately approved.

The MCP-specific projections in `_doc_summary`, `_highlight_summary`, and `_book_summary` may remain MCP presenters. They are presentation policy, not duplicated operation logic.

---

# 5. Sync Versus Async

## Recommendation: Async canonical core, explicit sync bridge

MCP is async, and network operations are naturally async. Therefore the canonical operations implementation should be async.

The new `Readwise` synchronous facade should execute the async service through a dedicated blocking portal running on its own event-loop thread. `anyio` is the most suitable implementation dependency.

```python
with Readwise() as readwise:
    result = readwise.documents.search(...)
```

Internally:

```python
portal.call(async_service.documents.search, input)
```

## Why not `asyncio.run()` per method?

It fails when called from a thread already running an event loop, and it repeatedly creates clients and event loops. That is unsuitable for notebooks and mixed async applications.

## Why not keep handwritten parallel operation layers?

That is the current failure mode. It guarantees semantic drift across:

- managers.
- async managers.
- workflows.
- contrib.
- CLI.
- MCP.

## Caveat: streaming

Bridging an async iterator to a synchronous iterator requires queueing across the portal and complicates lifecycle management.

Therefore:

- Core user-facing operations should normally return bounded result objects.
- Advanced raw resources may retain native sync and async iterators.
- Sync streaming can be added deliberately later if required.
- Existing generator APIs remain available through compatibility clients.

## Transitional strategy

During `0.3`:

- New `AsyncReadwise` uses the canonical operations directly.
- New `Readwise` uses the blocking portal.
- Existing `ReadwiseClient` and `AsyncReadwiseClient` remain as compatibility facades.
- Existing low-level sync clients continue working until `1.0`.

This avoids forcing the transport/resource migration and public sync migration into one risky step.

---

# 6. Migration Options

## Option A — Aggressive Restructure

### Description

Introduce the new concept-oriented API and move all new development to it. Existing modules become compatibility layers.

### Breaking-change inventory

Without shims, the following are public breaks.

#### Root imports

Current imports include:

```python
from readwise_sdk import ReadwiseClient, AsyncReadwiseClient
from readwise_sdk import HighlightManager, DigestBuilder
```

Target imports become:

```python
from readwise_sdk import Readwise, AsyncReadwise
```

#### Client attributes

Current:

```python
client.v2.list_highlights()
client.v3.list_documents()
```

Target:

```python
client.highlights.search()
client.documents.search()
client.raw.v2...
client.raw.v3...
```

#### Versioned client imports

These paths would move:

```python
readwise_sdk.v2.client.ReadwiseV2Client
readwise_sdk.v2.async_client.AsyncReadwiseV2Client
readwise_sdk.v3.client.ReadwiseV3Client
readwise_sdk.v3.async_client.AsyncReadwiseV3Client
```

#### Models

Current MCP and external users may import:

```python
from readwise_sdk.v2.models import HighlightCreate
from readwise_sdk.v3.models import DocumentCreate, DocumentUpdate
```

Target canonical paths:

```python
from readwise_sdk.models.readwise import HighlightCreate
from readwise_sdk.models.reader import DocumentCreate, DocumentUpdate
```

The existing paths should remain re-export modules until `1.0`.

#### Managers and workflows

These become deprecated operation wrappers:

```python
readwise_sdk.managers.*
readwise_sdk.workflows.*
readwise_sdk.contrib.*
```

#### Return and failure semantics

Some current APIs return:

- iterators.
- lists.
- `None`.
- `dict[id, bool]`.
- formatted strings.

The target operations return declared typed result objects. Compatibility wrappers must preserve old return values.

#### MCP internal imports

The MCP server currently imports `AsyncReadwiseClient` from the package root and request models from `v2.models`/`v3.models` at `src/readwise_sdk/mcp/server.py:19`.

It should migrate to `AsyncReadwise` and canonical model/input paths, while compatibility re-exports preserve external integrations.

### Deprecation plan

- `0.3.0`: add the new API and aggressively restructure internals.
- `0.3.x`: emit `DeprecationWarning` for legacy constructors and manager/workflow creation.
- Keep old module paths as re-exports.
- Keep `.v2` and `.v3` functional but document them as low-level compatibility APIs.
- `0.4+`: no new features on deprecated surfaces.
- `1.0.0`: remove deprecated managers/workflows and old client names after a documented migration window.

Warnings should be emitted on object construction or deprecated method use, not merely importing a module. Import-time warnings are noisy and difficult for downstream users to control.

### Version

Use **`0.3.0`**, not `1.0.0`.

The project is currently `0.2.1` and classified as alpha. A breaking minor release is semantically legitimate before 1.0. The new architecture should prove itself across one or more `0.x` releases before declaring a stable 1.0 contract.

---

## Option B — Conservative Refactor

### Description

Keep `ReadwiseClient`, `.v2`, `.v3`, managers, workflows, and contrib as the documented API. Internally route CLI and MCP through a newly added service layer.

### Advantages

- Minimal downstream migration.
- Lower short-term release risk.
- Documentation changes can be incremental.
- Existing users see little disruption.

### Disadvantages

- The package retains two competing public abstractions.
- `.v2/.v3` remains the easiest and most visible route.
- Manager/workflow naming remains ambiguous.
- New service capabilities must coexist indefinitely with obsolete organization.
- It becomes harder to remove sync/async duplication later.
- The “single source of truth” exists internally but not conceptually for users.

---

## Recommendation

**Choose Option A.**

This package is still at `0.2.1`, the codebase is modest in size, and MCP has exposed the cost of the current architecture. This is the correct time to establish a coherent public model.

Be aggressive about internal organization and the new recommended API, but pragmatic about compatibility:

- Preserve old imports through re-exports.
- Preserve old return values through wrappers.
- Do not preserve old internals.
- Remove the compatibility surface only at 1.0.

---

# 7. Staged Execution Plan

Each stage is intended to be one PR or a small cluster of tightly related PRs. Every stage ends with `just fc` passing.

## PR 1 — Add characterization contracts

Before moving code, lock observable behavior.

Add tests for:

- Root exports and import paths.
- `ReadwiseClient` constructor, context manager, `.v2`, `.v3`, and `create_optional()`.
- Sync and async pagination cursor behavior.
- Existing manager return types.
- sync-state JSON file formats.
- CLI stdout, stderr, exit codes, and JSON structures.
- All nine MCP tools, including exact error envelopes and field omission.
- MCP limit clamping and lenient invalid-datetime behavior.
- `save_to_reader(category=...)` request payload as currently implemented.
- callback exception suppression where currently documented by behavior.
- bulk-operation partial-failure maps.

No production behavior changes.

## PR 2 — Introduce canonical config and errors

Add:

- `config.py`.
- `errors.py`.
- immutable client configuration.
- credential resolution utilities shared where appropriate.
- error classification helpers.

Keep `exceptions.py` as a re-export.

Existing clients delegate to the new configuration and exception definitions.

## PR 3 — Extract retry and pagination infrastructure

Move shared logic from `client.py` and `_utils.py` into:

- `transport/retry.py`.
- `transport/pagination.py`.
- `transport/errors.py`.

Introduce endpoint-aware page decoders:

```python
StandardV2Page
ExportV2Page
ReaderV3Page
```

Keep `ReadwiseClient.paginate()` and `AsyncReadwiseClient.paginate()` as compatibility wrappers.

Characterization tests must confirm identical requests and retry timing decisions.

## PR 4 — Introduce async transport and resources

Create canonical async resources for:

- v2 highlights.
- v2 books.
- v2 tags.
- v2 export/review.
- v3 documents.
- v3 tags.

Make `AsyncReadwiseV2Client` and `AsyncReadwiseV3Client` delegate to them.

Do not change public methods or return types.

## PR 5 — Add operation inputs and result models

Introduce:

- search input models.
- create/update inputs where existing API models are insufficient.
- summary read models.
- `BulkResult`.
- `OperationFailure`.
- unified `SyncCheckpoint` and `SyncResult`.

This PR should be mostly additive and model-level.

## PR 6 — Implement document operations

Create canonical operations for:

- search.
- get.
- save.
- update.
- delete.
- move.
- set/add/remove tags.
- inbox/archive/later views.
- statistics.

Port semantics from:

- `DocumentManager`.
- `ReadingInbox`.
- `DocumentImporter`.
- MCP document tools.
- CLI Reader commands.

Test operations directly with fake resources where possible and with `respx` integration tests where transport behavior matters.

## PR 7 — Implement highlight and book operations

Create canonical operations for:

- highlight search/list/get/create/update/delete.
- bulk tag and untag.
- export.
- book search/list/get.
- book-with-highlights.
- reading statistics.
- highlight truncation and partial-failure policies.

Port semantics from:

- highlight and book managers.
- `HighlightPusher`.
- CLI.
- MCP.

Do not yet delete legacy implementations.

## PR 8 — Migrate the nine MCP tools

Change each MCP tool to call one operation.

Move presentation helpers to `mcp/output.py`.

Preserve:

- names.
- argument schemas.
- return strings.
- error JSON.
- summary fields.
- limits.
- documented per-tool behavior.

Run the MCP tool tests after migrating each tool group rather than waiting for all nine.

## PR 9 — Add the new async SDK facade

Add `AsyncReadwise` composed from the canonical service.

Expose:

```python
.documents
.highlights
.books
.tags
.digests
.sync
.raw
```

Add public facade tests and documentation examples.

Keep `AsyncReadwiseClient` unchanged externally but let it share resources.

## PR 10 — Add the synchronous SDK facade

Add `Readwise` using a dedicated AnyIO blocking portal.

Test:

- ordinary synchronous use.
- use from a thread with an already running event loop.
- context-manager cleanup.
- repeated operations.
- exceptions crossing the portal.
- cancellation and close behavior.

Do not convert legacy synchronous iterators yet.

## PR 11 — Rebuild the CLI shell

Split `cli/main.py` into command modules.

Add:

- global `--output`.
- common output renderer.
- consistent errors and exit codes.
- service context/lifecycle.
- strict stdout/stderr separation.

Initially migrate direct equivalents only:

- documents.
- highlights.
- books.
- version/auth.

Keep old command names and output defaults.

## PR 12 — Expand the CLI

Add missing core-backed commands:

- document get/update/delete/move/tag.
- highlight create/update/delete/tag/untag.
- custom digest.
- sync status/reset.
- JSONL output.
- global no-color and quiet behavior.

Add deprecated `reader` aliases for `documents`.

## PR 13 — Consolidate tags and digests

Move:

- `TagWorkflow`.
- digest data selection.
- grouping logic.

into operations.

Move Markdown, text, CSV, and JSON rendering into presenters.

`DigestBuilder` becomes a compatibility wrapper that calls digest operations plus a presenter.

## PR 14 — Consolidate synchronization and persistence

Replace duplicated state handling with:

```python
class StateStore(Protocol):
    def load(self) -> SyncCheckpoint: ...
    def save(self, checkpoint: SyncCheckpoint) -> None: ...
```

Provide `JsonFileStateStore`.

Rebuild:

- full sync.
- incremental sync.
- poll-once.
- batch callbacks.
- background scheduling.

on the same sync operation.

Keep legacy state-file readers capable of loading current formats.

## PR 15 — Convert managers, workflows, and contrib to shims

Replace implementation bodies with delegation.

For example:

```python
class HighlightManager:
    def search_highlights(...):
        warn_deprecated(...)
        return self._client.operations.highlights.search_legacy(...)
```

Preserve old return types and failure behavior.

Once delegation is complete, delete duplicated implementation code.

## PR 16 — Canonicalize model paths

Move canonical definitions to:

- `models/readwise.py`.
- `models/reader.py`.

Keep:

- `v2/models.py`.
- `v3/models.py`.

as re-export modules.

Update internal code, including MCP, to import only canonical paths.

## PR 17 — Tighten typing and packaging

- Remove CLI and MCP exclusions from `Justfile:18`.
- Type-check adapters.
- Ensure importing core does not import Typer, Rich, or MCP.
- Verify wheels with core only, `[cli]`, and `[mcp]`.
- Verify both console scripts.
- Add a `py.typed` marker if not already included.
- Build with Hatchling and inspect wheel contents.

## PR 18 — Documentation and deprecation release

Update:

- README.
- `llms.txt`.
- API guides.
- CLI documentation.
- migration guide.
- deprecation timeline.
- architecture contributor guide.

Release as:

```text
feat!: introduce unified Readwise operations architecture
```

Version: `0.3.0`.

---

# 8. Risks and De-Risking

## Public API breakage

**Risk:** Downstream users may import undocumented-but-accessible classes and models.

**Mitigation:**

- Keep old modules as re-exports.
- Add import-contract tests.
- Search README, docs, tests, and release history for every promoted import.
- Publish a migration table.
- Delay removals until 1.0.

## Behavioral drift in MCP

**Risk:** Moving validation, filtering, and serialization changes tool output.

**Mitigation:**

- Treat current MCP JSON as a wire contract.
- Add exact characterization tests before migration.
- Migrate one tool group at a time.
- Keep MCP presenters separate from general JSON presenters.
- Make behavior fixes in separate PRs after the refactor.

## Sync bridge complexity

**Risk:** Threaded portal lifecycle, exceptions, and streaming can be subtle.

**Mitigation:**

- Keep the sync facade deliberately small.
- Avoid sync streaming in the new operation API initially.
- Retain legacy native-sync raw clients.
- Add tests for running-event-loop environments.
- Make ownership explicit: the facade owns and closes its portal and async client.

## State-file incompatibility

**Risk:** Users may have persisted `SyncManager`, `BatchSync`, or poller state.

**Mitigation:**

- Add version fields to new state files.
- Write migration readers for all existing structures.
- Never silently reset malformed or unknown state.
- Back up or preserve legacy files before rewriting.
- Characterize current datetime formatting.

## Loss of partial-failure semantics

**Risk:** Existing bulk methods frequently suppress exceptions and return booleans.

**Mitigation:**

- Introduce a typed `BulkResult`.
- Compatibility wrappers convert it back to current dictionaries/lists.
- Record the original exception in the new result.
- Do not continue broad `except Exception` in canonical operations.

## Over-generalized operation framework

**Risk:** A command bus, registry, or generated metaprogramming system could obscure simple calls.

**Mitigation:**

- Use explicit service classes and ordinary methods.
- Do not derive CLI or MCP schemas automatically from operation signatures.
- Share behavior, not protocol metadata.
- Prefer duplicated five-line adapter declarations over a clever universal decorator.

## Dependency leakage

**Risk:** Core imports may accidentally require CLI or MCP extras.

**Mitigation:**

- Keep adapters at the outermost layer.
- Test importing `readwise_sdk` with only core dependencies installed.
- Keep FastMCP imports entirely under `readwise_sdk.mcp`.
- Keep Rich and Typer imports entirely under `readwise_sdk.cli`.

## Type-checking expansion

**Risk:** Enabling `ty` for CLI and MCP may expose many existing issues.

**Mitigation:**

- Add adapter typing after splitting the large modules.
- Remove exclusions directory by directory.
- Use typed context objects and result presenters.
- Avoid `Any` in operation boundaries even if protocol adapters require it.

---

# Final Recommendation

Proceed with an **aggressive `0.3.0` architecture migration** built around an async `ReadwiseService`.

The key rule should be:

> Resource clients know Readwise endpoints. Operations know user intent. Adapters know presentation and protocol.

Under that rule:

- `.v2` and `.v3` become low-level compatibility access.
- Managers, workflows, and contrib stop owning behavior.
- CLI commands and MCP tools call the same operation methods.
- Async behavior is canonical.
- Sync is a deliberate facade, not a second implementation.
- Existing imports and observable behavior survive through tested shims until `1.0`.