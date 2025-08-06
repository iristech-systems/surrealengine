# SurrealEngine Changelog

All notable changes to the SurrealEngine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Document Update Methods**: Added update() and update_sync() methods to all Document classes
  - Allows updating specific fields in any document without deleting existing data
  - Solves the issue with save() method's upsert behavior that would delete fields not included in the update
  - Preserves all existing document attributes while only modifying the specified fields
  - Fixes issues with FetchProgress and other Document classes that need partial updates

- **RelationDocument Update Methods**: Added update() and update_sync() methods to RelationDocument
  - Allows updating specific fields in a relation without deleting existing data
  - Solves the issue with save() method's upsert behavior that would delete fields not included in the update
  - Preserves all existing relation attributes while only modifying the specified fields

### Fixed
- **RelationDocument Save Behavior**: Modified Document.save() and save_sync() methods to automatically use update() for RelationDocument instances
  - Prevents data loss when saving RelationDocument instances with partial updates
  - Maintains backward compatibility with existing code that uses save() instead of update()
  - Fixes issues with routes that use ProductURL and other RelationDocument classes
- **URL Query Escaping**: Fixed issue with URL values in query filters
  - Ensures proper JSON serialization of URL strings containing spaces and special characters
  - Prevents SurrealDB parse errors when querying by URL fields
  - Improves reliability of queries with complex string values
  - Added special handling for URL detection and proper quoting in filter conditions
- **Document Update Type Error**: Fixed TypeError in document_update.py's isinstance() check
  - Corrected the improper use of Document.__subclasses__() in isinstance() check
  - Changed to use any(isinstance(self, cls) for cls in Document.__subclasses__())
  - Fixes "isinstance() arg 2 must be a type, a tuple of types, or a union" error
  - Ensures FetchProgress and other Document classes can be properly updated

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
