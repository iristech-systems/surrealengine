"""SurrealEngine: Object-Document Mapper for SurrealDB with both sync and async support.

SurrealEngine is a comprehensive Object-Document Mapper (ODM) for SurrealDB that provides
an intuitive Python interface for database operations. It supports both synchronous and
asynchronous operations, connection pooling, field validation, query building, and 
graph-based relationships.

Key Features:
    - Dual sync/async support for all operations
    - Connection pooling and management
    - Rich field types with validation
    - Query builder with Django-style filtering
    - Graph relationships and traversal
    - Materialized views and aggregations
    - Schema management and migrations
    - Signals for model lifecycle events

Example:
    Basic document definition and usage:

    >>> from surrealengine import Document, StringField, IntField
    >>> from surrealengine import create_connection
    >>> 
    >>> class User(Document):
    ...     name = StringField(required=True)
    ...     age = IntField()
    ...     
    ...     class Meta:
    ...         collection = "users"
    >>> 
    >>> # Create connection and save user
    >>> connection = create_connection("ws://localhost:8000/rpc")
    >>> # await connection.connect()  # in async context
    >>> 
    >>> user = User(name="Alice", age=30)
    >>> # await user.save()  # in async context
    >>> # print(f"Created user: {user.id}")

Modules:
    connection: Database connection management and pooling
    document: Core document classes and metaclasses
    fields: Field types for document schemas
    query: Query building and execution
    exceptions: Custom exception classes
    schema: Schema management utilities
    signals: Model lifecycle signals
    materialized_view: Materialized view support
    aggregation: Data aggregation utilities
"""

from .connection import (
    SurrealEngineAsyncConnection, 
    SurrealEngineSyncConnection, 
    ConnectionRegistry,
    create_connection,
    BaseSurrealEngineConnection
)

# For backward compatibility
SurrealEngineConnection = SurrealEngineAsyncConnection
from .schemaless import SurrealEngine
from .document import Document, RelationDocument
from .exceptions import (
    DoesNotExist,
    MultipleObjectsReturned,
    ValidationError,
)
from .fields import (
    BooleanField,
    DateTimeField,
    DictField,
    Field,
    FloatField,
    GeometryField,
    IntField,
    ListField,
    NumberField,
    ReferenceField,
    RelationField,
    StringField,
    FutureField,
    DecimalField,
    DurationField,
    OptionField,
    LiteralField,
    RangeField,
    SetField,
    TimeSeriesField,
    EmailField,
    URLField,
    IPAddressField,
    SlugField,
    ChoiceField
)
from .materialized_view import (
    MaterializedView, 
    Aggregation, 
    Count, 
    Mean, 
    Sum, 
    Min, 
    Max, 
    ArrayCollect,
    Median,
    StdDev,
    Variance,
    Percentile,
    Distinct,
    GroupConcat,
    CountIf,
    SumIf,
    MeanIf,
    MinIf,
    MaxIf,
    DistinctCountIf
)
from .meta import DocumentMetaOptions
from .query import QuerySet, RelationQuerySet
from .query_expressions import Q, QueryExpression
from .aggregation import AggregationPipeline
from .expr import Expr
from .surrealql import escape_identifier, escape_literal
from .record_id_utils import RecordIdUtils
from .schema import (
    get_document_classes,
    create_tables_from_module,
    create_tables_from_module_sync,
    generate_schema_statements,
    generate_schema_statements_from_module
)
from .datagrid_api import (
    DataGridQueryBuilder,
    get_grid_data,
    get_grid_data_sync,
    parse_datatables_params,
    format_datatables_response
)
from .relation_update import patch_relation_document

__version__ = "0.4.0"
__all__ = [
    "SurrealEngine",
    "SurrealEngineAsyncConnection",
    "SurrealEngineSyncConnection",
    "SurrealEngineConnection",  # For backward compatibility
    "BaseSurrealEngineConnection",
    "create_connection",
    "ConnectionRegistry",
    "Document",
    "DocumentMetaOptions",
    "RelationDocument",
    "DoesNotExist",
    "MultipleObjectsReturned",
    "ValidationError",
    "Field",
    "StringField",
    "NumberField",
    "IntField",
    "FloatField",
    "BooleanField",
    "DateTimeField",
    "ListField",
    "DictField",
    "ReferenceField",
    "RelationField",
    "GeometryField",
    "QuerySet",
    "RelationQuerySet",
    "Q",
    "QueryExpression",
    "Expr",
    "RecordIdUtils",
    "DurationField",
    "OptionField",
    "LiteralField",
    "RangeField",
    "SetField",
    "TimeSeriesField",
    "EmailField",
    "URLField",
    "IPAddressField",
    "SlugField",
    "ChoiceField",
    "MaterializedView",
    # Aggregation classes
    "AggregationPipeline",
    "Aggregation",
    "Count",
    "Mean",
    "Sum",
    "Min",
    "Max",
    "ArrayCollect",
    "Median",
    "StdDev",
    "Variance",
    "Percentile",
    "Distinct",
    "GroupConcat",
    "CountIf",
    "SumIf",
    "MeanIf",
    "MinIf",
    "MaxIf",
    "DistinctCountIf",
    # Schema generation functions
    "get_document_classes",
    "create_tables_from_module",
    "create_tables_from_module_sync",
    "generate_schema_statements",
    "generate_schema_statements_from_module",
    # DataGrid helpers
    "DataGridQueryBuilder",
    "get_grid_data",
    "get_grid_data_sync",
    "parse_datatables_params",
    "format_datatables_response",
    # SurrealQL helpers
    "escape_identifier",
    "escape_literal",
]

# Apply the patch to add update methods to RelationDocument
patch_relation_document()
