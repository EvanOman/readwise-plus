# CLAUDE.md - Instructions for Claude Code

This file provides guidance for Claude Code when working on this repository.

## Project Overview

**readwise-plus** is a comprehensive Python SDK for Readwise with high-level workflow abstractions. It supports both the Readwise API (v2) for highlights/books and the Reader API (v3) for documents.

## Build & Test Commands

```bash
# Install dependencies
just install

# Run all checks (format, lint, type-check, test) - RUN BEFORE EVERY COMMIT
just fc

# Individual commands
just fmt          # Format code
just lint         # Run linter
just type         # Type check
just test         # Run tests

# Run live tests (requires READWISE_API_KEY)
READWISE_API_KEY=xxx pytest -m live
```

## Project Structure

```
src/readwise_sdk/
├── client.py          # Main ReadwiseClient
├── exceptions.py      # Custom exceptions
├── v2/                # Readwise API v2 (highlights, books)
│   ├── client.py
│   └── models.py
├── v3/                # Reader API v3 (documents)
│   ├── client.py
│   └── models.py
├── managers/          # High-level managers
│   ├── highlights.py
│   ├── books.py
│   ├── documents.py
│   └── sync.py
├── workflows/         # Task-oriented utilities
│   ├── digest.py
│   ├── inbox.py
│   ├── poller.py
│   └── tags.py
├── contrib/           # Convenience interfaces
│   ├── highlight_push.py
│   ├── document_import.py
│   └── batch_sync.py
└── cli/               # Command-line interface
    └── main.py
```

## Conventional Commits (REQUIRED)

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automated releases via Release Please.

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description | Version Bump |
|------|-------------|--------------|
| `feat` | New feature | Minor |
| `fix` | Bug fix | Patch |
| `docs` | Documentation only | None |
| `style` | Code style (formatting, etc.) | None |
| `refactor` | Code refactoring | None |
| `perf` | Performance improvement | Patch |
| `test` | Adding/updating tests | None |
| `chore` | Maintenance tasks | None |
| `ci` | CI/CD changes | None |
| `build` | Build system changes | None |

### Breaking Changes

For breaking changes, add `!` after the type or add `BREAKING CHANGE:` in the footer:

```
feat!: remove deprecated highlight_url field

BREAKING CHANGE: The highlight_url field has been removed from HighlightCreate.
Use source_url instead.
```

### Examples

```bash
# New feature
feat(v3): add support for document notes

# Bug fix
fix(managers): handle empty highlight list in bulk_tag

# Documentation
docs: update README with new contrib interfaces

# Breaking change
feat(client)!: require Python 3.12+

# With scope and body
feat(workflows): add smart archive rules

Add configurable rules for automatically archiving documents:
- Age-based rules
- Category-based rules
- Domain-based rules
```

### Scopes (Optional)

- `client` - Main client
- `v2` - V2 API
- `v3` - V3 API
- `managers` - High-level managers
- `workflows` - Workflow utilities
- `contrib` - Contrib interfaces
- `cli` - CLI
- `deps` - Dependencies

## Release Process

Releases are automated via Release Please:

1. Merge PRs with conventional commits to `main`
2. Release Please creates/updates a release PR
3. When release PR is merged, a GitHub Release is created
4. The `publish` workflow automatically publishes to PyPI

## Code Style

- Python 3.12+
- Pydantic for models
- httpx for HTTP client
- Type hints required
- Docstrings for public APIs
- Line length: 100 chars

## Testing

- Unit tests in `tests/`
- Live tests marked with `@pytest.mark.live`
- Mock API responses using `respx`
- Aim for >90% coverage

## Adding New Features

1. Add models in `v2/models.py` or `v3/models.py`
2. Add client methods in `v2/client.py` or `v3/client.py`
3. Consider adding a high-level manager method
4. Add tests
5. Update llms.txt if adding public API
6. Use conventional commit message
