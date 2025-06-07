# SurrealEngine Changelog

All notable changes to the SurrealEngine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pagination support across all query methods with `page(number, size)` method
- Made dependencies optional: signals (blinker) and jupyter (notebook) can now be installed separately
- Added `PaginationResult` class for enhanced pagination with metadata
- Added new field types: EmailField, URLField, JSONField, IPAddressField, SlugField, ChoiceField
- Added proper logging system with SurrealEngineLogger class

### Changed
- Updated README.md with instructions for installing optional dependencies
- Improved pagination ergonomics with the `page(number, size)` method
- Marked "Implement schema registration with SurrealDB" as completed in tasks.md

### Fixed
- Fixed pagination support to work with all query methods, not just filter()

## [0.1.0] - 2023-05-12

### Added
- Initial release of SurrealEngine
- Basic document model with field validation
- Query functionality with filtering and pagination
- Schemaless API for flexible database access
- Support for both synchronous and asynchronous operations
- Connection management with connection registry
- Transaction support
- Relation management with graph traversal