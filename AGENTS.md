# AGENTS.md - Instructions for AI Agents

This file provides guidance for AI agents and assistants working on this repository.

## Quick Reference

| Command | Description |
|---------|-------------|
| `just fc` | **Run before every commit** - format, lint, type-check, test |
| `just test` | Run tests only |
| `uv sync --dev` | Install dependencies |

## Conventional Commits (MANDATORY)

**All commits MUST follow the Conventional Commits specification.**

### Format

```
<type>(<scope>): <short description>
```

### Types

- `feat`: New feature (bumps minor version)
- `fix`: Bug fix (bumps patch version)
- `docs`: Documentation changes
- `style`: Code formatting
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test changes
- `chore`: Maintenance
- `ci`: CI/CD changes
- `build`: Build system changes

### Breaking Changes

Add `!` after type for breaking changes:
```
feat!: remove deprecated API
```

### Examples

```
feat(v3): add document content extraction
fix(managers): handle pagination edge case
docs: add examples to README
chore(deps): update pydantic to 2.10
```

## Before Committing

1. **Always run `just fc`** - this formats, lints, type-checks, and tests
2. **Use conventional commit format** - required for Release Please
3. **Don't skip pre-commit checks**

## Project Architecture

```
readwise-plus/
├── V2 API (Readwise)     → client.v2.*
├── V3 API (Reader)       → client.v3.*
├── Managers              → HighlightManager, BookManager, etc.
├── Workflows             → DigestBuilder, ReadingInbox, etc.
├── Contrib               → HighlightPusher, DocumentImporter, BatchSync
└── CLI                   → readwise command
```

## Key Files

- `src/readwise_sdk/client.py` - Main entry point
- `src/readwise_sdk/v2/` - Readwise API (highlights, books)
- `src/readwise_sdk/v3/` - Reader API (documents)
- `tests/` - Test files
- `llms.txt` - LLM-friendly documentation

## Release Process

1. Commits with conventional format trigger Release Please
2. Release Please creates a PR with version bump and changelog
3. Merging the release PR creates a GitHub Release
4. GitHub Release triggers PyPI publish

## Common Tasks

### Add a new V2 API method

1. Add model in `src/readwise_sdk/v2/models.py`
2. Add method in `src/readwise_sdk/v2/client.py`
3. Add test in `tests/v2/test_client.py`
4. Commit: `feat(v2): add <method_name> method`

### Add a new V3 API method

1. Add model in `src/readwise_sdk/v3/models.py`
2. Add method in `src/readwise_sdk/v3/client.py`
3. Add test in `tests/v3/test_client.py`
4. Commit: `feat(v3): add <method_name> method`

### Fix a bug

1. Write failing test
2. Fix the bug
3. Run `just fc`
4. Commit: `fix(<scope>): <description of fix>`

### Update documentation

1. Edit relevant files
2. Commit: `docs: <description>`
