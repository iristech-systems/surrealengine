# SurrealEngine Changelog

All notable changes to the SurrealEngine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Enhanced
- **Field Improvements**: Major enhancements to specialized field types for better validation, performance, and functionality
  - **URLField**: Complete rewrite with urllib integration for robust URL validation and component access
    - Added URL component properties: `.scheme`, `.host`, `.port`, `.path`, `.query`, `.fragment`, `.netloc`
    - Added query parameter helpers: `get_query_params()` and `get_query_param()`
    - Added utility methods: `is_secure()` and `get_base_url()`
    - Support for host-only URLs with automatic scheme addition (e.g., "example.com" → "https://example.com")
    - Configurable allowed schemes and default scheme settings
  - **EmailField**: Improved email validation with more comprehensive regex pattern
    - Enhanced regex pattern allows more valid email characters and formats following RFC standards
    - Added additional validation checks for @ symbol count, empty local/domain parts, and domain structure
  - **DecimalField**: Fixed precision loss issues in database operations
    - Database values now stored as strings to preserve exact decimal precision
    - Proper handling of Decimal objects in `to_db()` and `from_db()` methods
  - **IPAddressField**: Fixed validation bug with non-numeric IPv4 octets
    - Added proper error handling for non-numeric octets in IPv4 validation
    - Improved error messages for different validation failure scenarios
  - **BytesField**: Enhanced with comprehensive file-like interface and optimized performance
    - **BytesFieldWrapper**: New file-like wrapper class providing standard Python file operations (read, write, seek, tell, flush, close)
    - **Context Manager Support**: Full `with` statement compatibility for safe resource handling
    - **File Operations**: Direct file loading/saving with `load_from_file()` and `save_to_file()` methods
    - **Stream Operations**: Stream copying with `copy_to_stream()` and `copy_from_stream()` for large file handling
    - **Metadata Support**: File metadata including filename, content_type, and custom metadata dictionary
    - **Text Operations**: Convenient `read_text()` and `write_text()` methods with encoding support
    - **Size Limits**: Configurable maximum size validation with proper error handling
    - **Database Integration**: Seamless conversion to/from SurrealDB bytes format with base64 encoding
    - **Performance Optimization**: Moved `base64` import from method level to module level
    - **Memory Efficient**: Chunked reading/writing for large files to manage memory usage
    - **Developer Experience**: Intuitive API matching standard Python file objects for easy adoption

### Fixed
- Fixed IPv4 address validation crash when octets contain non-numeric values
- Fixed decimal precision loss when converting between Python Decimal and database storage
- Improved email validation to accept more RFC-compliant email addresses

## [0.3.0] - 2025-09-01

### Added
- Expression and query building
  - Expr is now a single class with a working CASE builder: `Expr.case().when(...).else_(...).alias(...)`
  - `Expr.var(name)` for `$vars` and `Expr.raw(...)` for trusted fragments
  - String functions aligned with SurrealDB v2: `string::starts_with`, `string::ends_with`, `string::contains`, `string::matches`
- Escaping utilities
  - Public `escape_literal` and `escape_identifier`; builders use these consistently
- Aggregation and materialized views
  - AggregationPipeline: response normalization (returns list of row dicts), safe escaping in `match()`/`having()`, and injects `GROUP BY`/`GROUP ALL` when needed
  - Materialized functions updated for v2: replaced `array::collect` with `array::group`; hardened `Distinct`, `GroupConcat` for scalar inputs; `DistinctCountIf` now uses `array::len(array::group(IF cond THEN [field] ELSE [] END))`
- Connection and observability
  - ContextVar‑backed per‑task default connection: `set_default_connection` / `get_default_connection`
  - Connection pooling with validation, idle pruning, retries/backoff
  - OperationQueue with backpressure policies (block | drop_oldest | error) and metrics
  - Optional OpenTelemetry spans around queries/transactions (enabled if OTEL is installed)
  - Example script: `example_scripts/connection_and_observability_example.py`
- Graph and live updates
  - QuerySet.traverse(path, max_depth=None, unique=True) to project graph traversals
  - QuerySet.live(...): async generator for LIVE subscriptions (requires direct async ws connection)
    - Example script: `example_scripts/graph_and_live_example.py`
- RelationDocument helpers
  - `RelationDocument.find_by_in_documents(...)` and sync variant for batch inbound lookups
- Document/Relation updates
  - Added `update()` and `update_sync()` on Document and RelationDocument for partial updates without data loss

### Changed
- Centralized escaping in BaseQuerySet, AggregationPipeline, and Expr; removed ad‑hoc json.dumps usage for literals
- SurrealQL builder ensures `FETCH` is emitted as the last clause to avoid parse errors
- LIVE subscription path: replaced debug print statements with logger.debug to avoid leaking to stdout and to integrate with standard logging
- Docstring improvements across key APIs (e.g., QuerySet.live()) for richer IDE hints

### Fixed
- BaseQuerySet condition building now uses `escape_literal` consistently, including URL handling and arrays; preserves unquoted RecordIDs in INSIDE/NOT INSIDE arrays
- Materialized array functions migrated to v2 semantics; `DistinctCountIf` produces correct distinct counts without function argument errors
- Schema regex assertions now use `string::matches($value, pattern)` with proper literal escaping
- AggregationPipeline results are normalized (no more `'str'.get` errors in examples)
- Correct formatting for INSIDE/NOT INSIDE arrays containing RecordIDs (record ids unquoted)
- Document.save() automatically uses `update()` for RelationDocument to prevent unintended field removal
- Fixed TypeError in document update isinstance check

### Notes
- LIVE queries currently require a direct async websocket client (pooling client does not support LIVE)
- `returning=` is supported on `QuerySet.update(...)`; other mutations may follow in a future release

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


