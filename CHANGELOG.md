# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0](https://github.com/EvanOman/readwise-plus/releases/tag/v0.1.0) (2025-01-17)

### Features

* Initial release of readwise-plus
* **v2**: Full Readwise API v2 support (highlights, books, tags, export, daily review)
* **v3**: Full Reader API v3 support (documents, inbox, reading list, archive, tags)
* **managers**: High-level managers (HighlightManager, BookManager, DocumentManager, SyncManager)
* **workflows**: Workflow utilities (DigestBuilder, ReadingInbox, BackgroundPoller, TagWorkflow)
* **contrib**: Convenience interfaces (HighlightPusher, DocumentImporter, BatchSync)
* **cli**: Command-line interface with typer/rich
* **docs**: llms.txt and llms-full.txt for LLM-friendly documentation

### Documentation

* Comprehensive README with examples
* llms.txt specification compliance
* Type hints throughout
