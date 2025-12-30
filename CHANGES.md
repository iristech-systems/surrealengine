# SurrealEngine Changelog

All notable changes to the SurrealEngine project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2025-12-30

### Added
- **Pythonic Query Expressions**: Implemented operator overloading for `Field` objects, enabling standard Python comparison operators ('>', '<', '==', '&', '|', '~') for building queries.
  - Added support for `startswith`, `endswith` operator methods on `Field` class.
- **Fluent Graph Builder**: Added `.out()`, `.in_()`, and `.both()` methods to `QuerySet` and `Document.objects` for intuitive graph traversal.
- **Magic Relation Accessors**: Added `.rel` property to `Document` for direct, fluent access to relationships starting from a document instance (e.g., `user.rel.friends`).
- **Decorator-based Signals**: Introduced `@receiver` decorator and `SignalProxy` wrappers, allowing signal handlers (like `@pre_save`) to be defined directly as methods within `Document` classes.
- **Manager API Consistency**: expanded `Document.objects` (QuerySetDescriptor) to expose all `QuerySet` methods directly, including `traverse`, `shortest_path`, `with_index`, `no_index`, `live`, `update`, `delete`, and `aggregate`. This enables consistent method chaining on the manager itself (e.g., `User.objects.traverse(...)`).

### Fixed
- **Relation Document Saving**: Fixed `RelationDocument.save()` to correctly handle manual `RecordID` casting for `in` and `out` fields, improving developer experience when creating relations manually.


## [0.5.1] - 2025-12-30

### Fixed
- **Documentation Consistency**: Unified the documentation structure to ensure consistent navigation menus across User Guide and API Reference sections.
- **API Reference Consolidation**: Cleaned up redundant auto-generated API pages and merged orphaned modules (`graph`, `schemaless`, `base_query`, `pagination`, etc.) into curated reference pages.
- **Docstring Formatting**: Corrected numerous docstring errors, fixed indentation issues, and converted Markdown-style code blocks to ReStructuredText (RST) across the core codebase (specifically in `Document` and `QuerySet` classes).
- **Core Import Fix**: Fixed a missing `ValidationError` import in `document.py` that was causing documentation build failures.
- **Field Documentation**: Fixed incorrect module paths in `api/fields.rst` ensuring all field classes are correctly documented via `autodoc`.
- **Sphinx Build Warnings**: Resolved all remaining documentation warnings, including duplicate object descriptions and title underline mismatches.

## [0.5.0] - 2025-12-30

### Added
- **QuerySet Enhancements**:
  - `omit(*fields)`: Exclude specific fields from the results.
  - `timeout(duration)`: Set a timeout for the query execution (e.g., "5s").
  - `tempfiles(value)`: Enable or disable using temporary files for large queries.
  - `with_explain(full=False)`: Builder method to explain the query execution plan. `explain()` and `explain_sync()` now also support `full=True` argument.
  - `no_index()`: Use `WITH NOINDEX` clause to bypass indexes.
  - `group_by(all=True)`: Support for `GROUP ALL` clause.
- **Advanced Filter Operators**: Added support for SurrealDB set operators including:
  - `contains_any`, `contains_all`, `contains_none`
  - `inside`, `not_inside`
  - `all_inside`, `any_inside`, `none_inside`
- **Live Query Ergonomics**:
  - `LiveEvent` class: Typed event objects yielding `action` (CREATE/UPDATE/DELETE), `data`, `ts`, and `id`.
  - `action` filtering: `QuerySet.live(action="CREATE")` or `action=["CREATE", "UPDATE"]` to filter events client-side.
- **Materialized Views**:
  - `create(overwrite=True)` / `create(if_not_exists=True)`: Support for `OVERWRITE` and `IF NOT EXISTS` clauses in `DEFINE TABLE`.
  - Improved `GROUP BY` parsing to robustly handle `QuerySet` grouping configuration.

### Changed
- **Deprecation**: `MaterializedView.refresh()` and `refresh_sync()` are now deprecated as SurrealDB views are live and do not require manual refreshing.
- **Explain Method**: `QuerySet.explain()` now supports `full=True` to retrieve the full execution plan including trace.

## [0.4.1] - 2025-12-19

### Added
- **Embedded Database Support**: Full support for connection schemes `mem://`, `surrealkv://`, and `file://` utilizing the underlying SDK's native embedded capabilities.
- **Sync API Parity**: Added `Document.update_sync()`, `Document.save_sync()`, `Document.refresh_sync()`, and `RelationDocument.update_sync()` to match async capabilities.
- **Data Type Compliance**: Core fields (`DurationField`, `RangeField`, `GeometryField`, `TableField`, `RecordIDField`) now natively support and preserve `surrealdb` SDK objects (`Duration`, `Range`, `Geometry`, `Table`, `RecordID`).

### Changed
- **Strict Return Types**: Fields like `RecordIDField` now return `surrealdb.RecordID` objects instead of strings, improving type safety.
- **Improved Serialization**: Refactored `Document.save` and `Document.update` logic to share a unified serialization creation pipeline, fixing CBOR errors with `Datetime` objects.
- **Refactoring**: Merged `document_update.py` into `document.py` for cleaner architecture.
- **BaseQuerySet**: Updated to remove legacy dependencies and improve query building robustness.

### Fixed
- **CBOR Serialization**: Fixed `ValueError: CBOR text data type must be str` when saving `datetime` objects.
- **ReferenceField Bug**: Fixed issue where `ReferenceField` was incorrectly converting `RecordID` objects to strings during serialization.
- **Geometry Validation**: Enhanced `GeometryField` to strictly validate closed linear rings for Polygons.
- **Default Values**: Fixed issue where default values were not persisted when creating documents with manually specified IDs.

### Enhanced
- **Immutable Filtering**: `BaseQuerySet.filter()` now returns a new queryset instance, preventing accidental mutation of the original queryset.
- **Advanced `Q` Object Handling**: The `filter` method now correctly handles complex, nested `Q` objects for more powerful and intuitive query construction.
- **Combined Queries**: `filter()` now supports passing both a `Q` object and keyword arguments simultaneously, allowing for more flexible query building.
- **Robust `to_where_clause`**: The `Q.to_where_clause()` method has been rewritten to correctly handle nested `Q` objects and generate valid `WHERE` clauses for complex queries.

### Fixed
- Corrected the `VALUE` keyword to `DEFAULT` in the schema generation for document fields.
- Improved the `serialize_http_safe` function to correctly handle `IsoDateTimeWrapper` objects, preventing potential issues with datetime serialization.

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
