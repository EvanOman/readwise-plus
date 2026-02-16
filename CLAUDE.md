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
3. When release PR is merged, a GitHub Release is created and PyPI publish runs (both in `release-please.yml`)

### Version Bump Rules (pre-1.0)

The config in `release-please-config.json` controls version bumps:

| Commit Type | Version Bump | Example |
|-------------|-------------|---------|
| `fix:` | Patch | 0.2.0 → 0.2.1 |
| `feat:` | Minor | 0.2.0 → 0.3.0 |
| `feat!:` / `BREAKING CHANGE:` | Minor (not major) | 0.2.0 → 0.3.0 |

Key settings:
- `bump-minor-pre-major: true` — breaking changes bump minor (not major) while pre-1.0
- `bump-patch-for-minor-pre-major: false` — feat commits bump minor (NOT patch) while pre-1.0. **Do not set this to `true`** or feat commits will only produce patch bumps

### Cutting a Release

1. Ensure conventional commits are on `main` (use cherry-pick or squash merge, see below)
2. Release Please auto-creates/updates a PR (e.g., "chore(main): release X.Y.Z")
3. Merge the release PR — this triggers both the GitHub Release and PyPI publish in one workflow
4. The standalone `publish.yml` workflow does NOT trigger (GitHub Actions `GITHUB_TOKEN` limitation) — publishing is handled by the `publish` job inside `release-please.yml`

### If Release PR Shows Wrong Version

If the release PR has the wrong version bump, check `release-please-config.json` bump settings. To regenerate:
1. Fix the config, commit, and push to `main`
2. Close the existing release PR
3. Trigger the Release Please workflow: `gh workflow run "Release Please"`
4. A new PR with the corrected version will be created

## Merging Feature Branches and Worktrees

**Release Please only scans first-parent commits on `main`.** This means merge commits like "Merge branch 'feature-x'" are invisible to the release automation. You must use one of these strategies:

### Preferred: Cherry-pick (for worktree workflows)

```bash
# After work is done on a worktree/feature branch:
git cherry-pick <commit-sha>   # Preserves the original conventional commit message
```

### Alternative: Squash merge

```bash
git merge --squash feature-branch
git commit -m "feat(scope): description of the change"
```

### Never use

```bash
# DO NOT use regular merge - the merge commit message won't follow conventional commits
# and Release Please will not detect the changes:
git merge feature-branch           # Bad
git merge --no-edit feature-branch  # Bad
```

## CI Notes

- The coverage badge is pushed to the orphan `badges` branch (not `main`) to avoid branch protection conflicts. The README references it via a raw GitHub URL. The `badges` branch must NOT have branch protection enabled.
- The `typer` package is an optional CLI dependency (`--extra cli`). CI doesn't install it, so `tests/test_cli.py` is auto-skipped via `collect_ignore` in `tests/conftest.py`. Both `test_cli.py` and `conftest.py` are excluded from `ty` type-checking in the Justfile.

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
