set shell := ["bash", "-cu"]

default:
    @just --list

fmt:
    uv run ruff format .

format-check:
    uv run ruff format --check .

lint:
    uv run ruff check .

lint-fix:
    uv run ruff check . --fix

type:
    uv run ty check . --exclude "src/readwise_sdk/cli/"

test:
    uv run pytest

test-live:
    uv run pytest -m live

test-cov:
    uv run pytest --cov=src/readwise_sdk --cov-report=term-missing

# FIX + CHECK: Run before every commit
fc: fmt lint-fix lint type test

ci: lint format-check type test

install:
    uv sync --dev

# Install with CLI extras
install-cli:
    uv sync --dev --extra cli
