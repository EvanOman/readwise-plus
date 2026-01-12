# readwise-sdk

[![CI](https://github.com/EvanOman/readwise-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/EvanOman/readwise-sdk/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/EvanOman/readwise-sdk/branch/main/graph/badge.svg)](https://codecov.io/gh/EvanOman/readwise-sdk)

Comprehensive Python SDK for [Readwise](https://readwise.io) with high-level workflow abstractions.

## Features

- **Core Layer**: Direct Python methods for each Readwise API endpoint
  - Readwise API v2 (highlights, books, tags, daily review)
  - Reader API v3 (documents, reading list)
- **Abstraction Layer**: User-friendly, workflow-oriented operations
  - Highlight and book management
  - Document inbox handling
  - Digest creation and export
  - Background sync and polling

## Installation

```bash
pip install readwise-sdk
```

With CLI support:
```bash
pip install readwise-sdk[cli]
```

## Quick Start

```python
from readwise_sdk import ReadwiseClient

# Initialize with your API token
client = ReadwiseClient(api_key="your_token_here")

# Or use environment variable READWISE_API_KEY
client = ReadwiseClient()

# Validate your token
client.validate_token()

# Get all highlights
for highlight in client.v2.highlights.list():
    print(highlight.text)

# Get Reader inbox
for doc in client.v3.documents.list(location="new"):
    print(doc.title)
```

## High-Level Abstractions

```python
from readwise_sdk import ReadwiseClient
from readwise_sdk.managers import HighlightManager, DocumentManager

client = ReadwiseClient()

# Highlight workflows
highlights = HighlightManager(client)
recent = highlights.get_highlights_since(days=7)
highlights.bulk_tag(highlight_ids, "to-review")

# Document workflows
docs = DocumentManager(client)
inbox = docs.get_inbox()
docs.archive(doc_id)
```

## Development

```bash
# Install dependencies
just install

# Run all checks (format, lint, type-check, test)
just fc

# Run tests only
just test
```

## License

MIT
