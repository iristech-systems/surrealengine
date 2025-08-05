# SurrealEngine Changelog

All notable changes to the SurrealEngine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-08-05

### Added
- **Advanced Change Tracking**: Comprehensive change detection and state management for documents
  - Track field-level changes with `has_changed()` method for specific fields or entire document
  - Access changed values with `get_changes()` returning dictionary of modified fields
  - Retrieve original values with `get_original_value(field)` for any field
  - Revert changes selectively with `revert_changes(['field1', 'field2'])` or all changes
  - Clean/dirty state management with `is_dirty`, `is_clean` properties
  - `dirty_fields` property returns list of modified field names
  - Automatic state cleanup after successful save operations

- **Smart Save Optimization**: Intelligent database updates that only send changed fields
  - Existing documents only send modified fields to database (up to 66%+ reduction in data transfer)
  - Skip database operations entirely when no changes detected
  - New documents still send all fields as expected
  - Significant performance improvements for large documents with few changes
  - Zero breaking changes - fully backward compatible

- **Conditional Aggregations**: Advanced aggregation functions with built-in filtering
  - `CountIf`, `SumIf`, `MeanIf`, `MinIf`, `MaxIf`, `DistinctCountIf` functions
  - Support for complex conditions like `CountIf("status = 'success' AND amount > 100")`
  - Expression builder (`Expr`) for programmatic condition construction
  - Pre and post-aggregation filtering with `match()` and `having()` methods
  - Full integration with existing aggregation pipeline system

- **Enhanced RecordID Handling**: Flexible support for various RecordID formats
  - String format support: `"table:id"` now works seamlessly in queries
  - URL-encoded format support: `"table%3Aid"` automatically decoded
  - Short ID format: Just `"id"` when table context is known
  - `RecordIdUtils` class for comprehensive ID manipulation
  - Enhanced `Expr` class with RecordID-specific query methods
  - Automatic normalization in all query operations

### Changed
- Document initialization now starts clean for new documents (initial values don't count as changes)
- Enhanced `save()` methods to use smart save optimization transparently

### Fixed
- Fixed change tracking to properly handle initial document state
- Improved field validation to work correctly with change tracking

## [0.2.1] - 2025-07-02

### Added
- **Query Expression System**: Advanced query building with Q objects and QueryExpression
  - **Q objects** for complex boolean logic supporting AND (&), OR (|), and NOT (~) operations
  - **QueryExpression class** for comprehensive query building with FETCH, ORDER BY, GROUP BY, LIMIT, and START clauses
  - **objects(query) syntax** - Alternative to filter() allowing direct query object passing: `User.objects(Q(active=True))`
  - **filter(query) enhancement** - Now accepts Q objects and QueryExpressions in addition to kwargs
  - **Raw query support** with `Q.raw()` for custom SurrealQL WHERE clauses
  - **FETCH integration** - QueryExpression with FETCH automatically dereferences related documents
  - **Django-style operators** - Support for field__operator syntax (gt, lt, gte, lte, ne, in, contains, startswith, endswith, regex)
  - **Method chaining** - Full compatibility with existing queryset methods (limit, order_by, fetch, etc.)
  - **Synchronous support** - All query expression features work with both async and sync operations

### Fixed
- **String function compatibility** - Updated to use correct SurrealDB v2.x string function names (`string::starts_with` instead of `string::startsWith`, `string::ends_with` instead of `string::endsWith`)

### Added (Continued)
- **DataGrid API Support**: Comprehensive frontend integration for data table libraries
  - Efficient SurrealDB query optimization replacing Python-based filtering with database-native operations
  - Support for BootstrapTable.js format (maintaining backward compatibility with existing APIs)
  - DataTables.js parameter conversion and response formatting
  - Pagination, sorting, filtering, and search functionality optimized at the database level
  - `get_grid_data()` and `get_grid_data_sync()` helper functions for easy route integration
  - `DataGridQueryBuilder` class for building complex filtered queries
  - Parameter conversion utilities: `parse_datatables_params()` and `format_datatables_response()`
  - Performance benefits: Only fetch required data, leverage SurrealDB indexes, reduce memory usage
  - Drop-in replacement for existing route logic - reduces 50+ lines of filtering code to a single function call

## [0.2.0] - 2024-06-28

### Added
- Implemented advanced connection management features:
  - Connection pooling with configurable pool size, connection reuse, validation, and cleanup
  - Integration of connection pools with Document models for seamless use in async applications
  - Connection timeouts and retries with exponential backoff
  - Automatic reconnection with event-based triggers and operation queuing
  - Connection string parsing with support for connection options
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
- Added automatic reference resolution with `Document.get(dereference=True)` and `Document.resolve_references()` methods
- Added JOIN-like operations with `QuerySet.join()` method for efficient retrieval of referenced documents
- Enhanced RelationField with `get_related_documents()` method for bidirectional relation navigation
- **PERFORMANCE IMPROVEMENT**: Updated all reference/dereference code to use SurrealDB's native FETCH clause instead of manual resolution:
  - `ReferenceField.from_db()` now handles fetched documents automatically
  - `RelationField.from_db()` now handles fetched relations automatically  
  - `Document.resolve_references()` uses FETCH queries for efficient bulk resolution
  - `Document.get()` with `dereference=True` uses FETCH for single-query reference resolution
  - `QuerySet.join()` methods use FETCH clauses internally for better performance
  - Maintains full backward compatibility with fallback to manual resolution if FETCH fails
- **MAJOR PERFORMANCE ENHANCEMENT**: Implemented comprehensive query performance optimizations:
  - **Auto-optimization for `id__in` filters**: Automatically converts `filter(id__in=[...])` to direct record access syntax `SELECT * FROM user:id1, user:id2, user:id3` for up to 3.4x faster queries
  - **New convenience methods**: Added `get_many(ids)` and `get_range(start_id, end_id)` for optimized bulk record retrieval using direct record access and range syntax
  - **Smart filter optimization**: Automatic detection of ID range patterns (`id__gte` + `id__lte`) and conversion to optimized range queries `SELECT * FROM table:start..=end`
  - **Developer experience tools**: 
    - `explain()` and `explain_sync()` methods for query execution plan analysis
    - `suggest_indexes()` method for intelligent index recommendations based on query patterns
  - **Optimized bulk operations**: Enhanced `update()` and `delete()` methods with direct record access for bulk ID operations, improving performance for large datasets
  - **Universal ID support**: All optimizations work seamlessly with both auto-generated IDs and custom IDs, maintaining backward compatibility

### Changed
- Updated README.md with instructions for installing optional dependencies
- Improved pagination ergonomics with the `page(number, size)` method
- Marked "Implement schema registration with SurrealDB" as completed in tasks.md
- Removed JSONField and replaced it with DictField for better functionality and consistency
- Refactored fields.py into a directory structure with separate modules for better organization and maintainability

### Fixed
- Fixed pagination support to work with all query methods, not just filter()
- Enhanced ReferenceField to properly handle RecordID objects
- Fixed DictField nested field access in queries using double underscore syntax (e.g., `settings__theme="dark"`)
- Added support for nested fields in DictFields when using schemafull tables
- Fixed IPAddressField to properly handle the 'version' parameter for backward compatibility
- Fixed issue with docstring comments in create_table method causing parsing errors
- Removed debug print statements and commented-out code for cleaner codebase
- **CRITICAL FIX**: Fixed ID formatting issue in upsert operations where numeric string IDs like "testdoc:123" were being stored incorrectly, causing retrieval failures

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
