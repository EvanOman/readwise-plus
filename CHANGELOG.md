# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/EvanOman/readwise-plus/compare/v0.1.5...v0.2.0) (2026-02-14)


### Features

* comprehensive test suite with 97% coverage ([4a244dc](https://github.com/EvanOman/readwise-plus/commit/4a244dcded5d19d1287d5530551c6c02a4d325da))


### Bug Fixes

* **ci:** also exclude tests/conftest.py from ty type-checking ([6839d81](https://github.com/EvanOman/readwise-plus/commit/6839d8147f9341873c8a36b7244586e71d13891f))
* **ci:** exclude test_cli.py from ty type-checking ([c1bf95c](https://github.com/EvanOman/readwise-plus/commit/c1bf95c2401ce6c024a2026edb921e50bd356218))
* **ci:** skip CLI tests when typer is not installed ([c818d7b](https://github.com/EvanOman/readwise-plus/commit/c818d7b912754d3567be3a46c56e9de6cfee7a00))

## [0.1.5](https://github.com/EvanOman/readwise-plus/compare/v0.1.4...v0.1.5) (2026-02-14)


### Features

* **client:** add create_optional() factory and is_configured property for deferred validation ([61096af](https://github.com/EvanOman/readwise-plus/commit/61096af4fe3430dbe15753ab1bd6049d26648573)), closes [#29](https://github.com/EvanOman/readwise-plus/issues/29)
* **contrib:** add AsyncDocumentImporter for async document operations ([196fa7a](https://github.com/EvanOman/readwise-plus/commit/196fa7a99c30117ce7e76147aa4050226e022f4d)), closes [#32](https://github.com/EvanOman/readwise-plus/issues/32)
* **contrib:** add detailed TruncationInfo to PushResult for field-level truncation tracking ([166fda1](https://github.com/EvanOman/readwise-plus/commit/166fda1750ac4d3ffc08df4c6d8c845876985c4e)), closes [#26](https://github.com/EvanOman/readwise-plus/issues/26)
* **contrib:** add sync_documents() method to BatchSync ([bddf77e](https://github.com/EvanOman/readwise-plus/commit/bddf77e2df99984033271e4002c9e5a0ea73703b)), closes [#31](https://github.com/EvanOman/readwise-plus/issues/31)
* **contrib:** default category to None in SimpleHighlight and push() to let API decide ([24cf6fa](https://github.com/EvanOman/readwise-plus/commit/24cf6fae2b5cbeb4faa172f159e32d519f690d34)), closes [#25](https://github.com/EvanOman/readwise-plus/issues/25)


### Bug Fixes

* **client:** use dynamic version from package metadata instead of hardcoded value ([6e5a344](https://github.com/EvanOman/readwise-plus/commit/6e5a34463fb1df6f35f8e613186bda850cc447ce)), closes [#27](https://github.com/EvanOman/readwise-plus/issues/27)


### Documentation

* add merge strategy guidance for release-please compatibility ([06181a3](https://github.com/EvanOman/readwise-plus/commit/06181a3ff0e4ec457e3be182f4eb9254d6260860))

## [0.1.4](https://github.com/EvanOman/readwise-plus/compare/v0.1.3...v0.1.4) (2026-02-12)


### Features

* add notes field to DocumentUpdate model ([c4ba4cd](https://github.com/EvanOman/readwise-plus/commit/c4ba4cddd1d8f78df8ade586a42593abaab2c687))


### Bug Fixes

* format batch_sync.py for CI ([de2667d](https://github.com/EvanOman/readwise-plus/commit/de2667deb47b61f129b2c28626ecf1104f2e1537))
* support Python 3.10+ instead of requiring 3.12+ ([d8f7b5f](https://github.com/EvanOman/readwise-plus/commit/d8f7b5fd7d3688e722a421b8578184b98597e737))


### Reverts

* restore Python 3.12+ requirement ([2e52079](https://github.com/EvanOman/readwise-plus/commit/2e52079b7c3e57425aed06c2de5016ca5a7a6899))
* undo manual version bump, let release-please manage versioning ([a506543](https://github.com/EvanOman/readwise-plus/commit/a506543fe933ad6f09b7ea74bfa1b7cd13114316))


### Documentation

* add AsyncBatchSync documentation ([a580084](https://github.com/EvanOman/readwise-plus/commit/a5800846826952934aba980ebf428284fc0e6aee))

## [0.1.3](https://github.com/EvanOman/readwise-plus/compare/v0.1.2...v0.1.3) (2026-01-21)


### Features

* **contrib:** add AsyncBatchSync for async batch synchronization ([2a14a0c](https://github.com/EvanOman/readwise-plus/commit/2a14a0cfda5b853af7654f68708ba0b4035e6997))
* **contrib:** add update/delete methods to HighlightPusher ([7ea8723](https://github.com/EvanOman/readwise-plus/commit/7ea8723290970e2870de2687971c56021dd26310))


### Documentation

* add async support documentation ([99c24a4](https://github.com/EvanOman/readwise-plus/commit/99c24a46906ef03099d907e0d2d0aae148ad8c6d))
* add documentation for HighlightCreate, HighlightUpdate, and CRUD methods ([d62010a](https://github.com/EvanOman/readwise-plus/commit/d62010a32f6450c8ddf0161efd4c06308f53f004))

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
