# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2](https://github.com/EvanOman/readwise-plus/compare/v0.1.1...v0.1.2) (2026-01-20)


### Features

* add async support for contrib and managers ([dc2e1d6](https://github.com/EvanOman/readwise-plus/commit/dc2e1d670a2be3d2cee19125be7bc351c380a5af))

## [0.1.1](https://github.com/EvanOman/readwise-plus/compare/v0.1.0...v0.1.1) (2026-01-18)


### Features

* add full async support with AsyncReadwiseClient ([c600b14](https://github.com/EvanOman/readwise-plus/commit/c600b143123ae3333a5baab5cd206e53ef8af00e))
* **cli:** add tag management commands ([45359a0](https://github.com/EvanOman/readwise-plus/commit/45359a020bdf5902be0467c27175a39afa6f9e8e)), closes [#10](https://github.com/EvanOman/readwise-plus/issues/10)


### Bug Fixes

* **ci:** update release-please to use config files ([356e39a](https://github.com/EvanOman/readwise-plus/commit/356e39a40cd9f1f38fe20673ff429246f5a9b54e))


### Documentation

* add MkDocs documentation site with GitHub Pages deployment ([fcb75f5](https://github.com/EvanOman/readwise-plus/commit/fcb75f522997f6049aac3c537a5cd28dd628cac5)), closes [#8](https://github.com/EvanOman/readwise-plus/issues/8)
* improve README with comprehensive examples and badges ([5efcf4e](https://github.com/EvanOman/readwise-plus/commit/5efcf4e6bc27b4a161bcad047e5058c4f3c407f5)), closes [#13](https://github.com/EvanOman/readwise-plus/issues/13)

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
