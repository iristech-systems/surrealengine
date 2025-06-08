# SurrealEngine Changelog

All notable changes to the SurrealEngine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Pagination support across all query methods with `page(number, size)` method
- Made dependencies optional: signals (blinker) and jupyter (notebook) can now be installed separately
- Added `PaginationResult` class for enhanced pagination with metadata
- Added new field types: EmailField, URLField, IPAddressField, SlugField, ChoiceField
- Added proper logging system with SurrealEngineLogger class
- Added native SurrealDB type support with LiteralField and RangeField
- Enhanced SetField to ensure uniqueness during validation
- Added TimeSeriesField for time series data with metadata support
- Added materialized views support with MaterializedView class and Document.create_materialized_view method
- Enhanced materialized views with support for aggregation functions (count, mean, sum, min, max, array_collect) and custom field selection
- Added `get_raw_query()` method to BaseQuerySet to get the raw query string without executing it, allowing for manual execution or modification of queries
- Added `execute_raw_query()` and `execute_raw_query_sync()` methods to MaterializedView to execute raw queries against materialized views
- Added field-level indexing with `indexed`, `unique`, `search`, and `analyzer` parameters
- Added support for multi-field indexes with the `index_with` parameter
- Added aggregation pipelines with the `AggregationPipeline` class for complex data transformations
- Added additional aggregation functions: Median, StdDev, Variance, Percentile, Distinct, GroupConcat

### Changed
- Updated README.md with instructions for installing optional dependencies
- Improved pagination ergonomics with the `page(number, size)` method
- Marked "Implement schema registration with SurrealDB" as completed in tasks.md
- Removed JSONField and replaced it with DictField for better functionality and consistency

### Fixed
- Fixed pagination support to work with all query methods, not just filter()
- Enhanced ReferenceField to properly handle RecordID objects
- Fixed DictField nested field access in queries using double underscore syntax (e.g., `settings__theme="dark"`)
- Added support for nested fields in DictFields when using schemafull tables

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
