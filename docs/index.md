# readwise-plus

Comprehensive Python SDK for [Readwise](https://readwise.io) with high-level workflow abstractions.

[![CI](https://github.com/EvanOman/readwise-plus/actions/workflows/ci.yml/badge.svg)](https://github.com/EvanOman/readwise-plus/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/readwise-plus.svg)](https://pypi.org/project/readwise-plus/)
[![Python versions](https://img.shields.io/pypi/pyversions/readwise-plus)](https://pypi.org/project/readwise-plus/)

## Features

- **V2 API (Readwise)**: Full support for highlights, books, tags, and daily review
- **V3 API (Reader)**: Full support for documents, inbox, reading list, and archive
- **Managers**: High-level abstractions for common operations
- **Workflows**: Pre-built workflows for digests, tagging, and syncing
- **Contrib**: Convenience interfaces for common integration patterns
- **CLI**: Command-line interface for quick operations

## Quick Example

```python
from readwise_sdk import ReadwiseClient

# Initialize with your API token
client = ReadwiseClient()  # Uses READWISE_API_KEY env var

# Get all highlights
for highlight in client.v2.highlights.list():
    print(highlight.text)

# Get Reader inbox
for doc in client.v3.documents.list(location="new"):
    print(doc.title)
```

## Architecture

The SDK is organized into layers of increasing abstraction:

```
readwise-plus/
├── Core Layer
│   ├── V2 Client      → client.v2.*     (Readwise API)
│   └── V3 Client      → client.v3.*     (Reader API)
├── Manager Layer
│   ├── HighlightManager   → Highlight operations
│   ├── BookManager        → Book operations
│   ├── DocumentManager    → Document operations
│   └── SyncManager        → Sync state tracking
├── Workflow Layer
│   ├── DigestBuilder      → Create highlight digests
│   ├── ReadingInbox       → Inbox management
│   ├── TagWorkflow        → Auto-tagging
│   └── BackgroundPoller   → Background sync
└── Contrib Layer
    ├── HighlightPusher    → Push highlights to Readwise
    ├── DocumentImporter   → Import documents to Reader
    └── BatchSync          → Batch synchronization
```

## Next Steps

- [Installation](getting-started/installation.md) - Install readwise-plus
- [Quick Start](getting-started/quickstart.md) - Get up and running quickly
- [CLI Reference](cli.md) - Use the command-line interface
- [API Reference](api/client.md) - Explore the full API
