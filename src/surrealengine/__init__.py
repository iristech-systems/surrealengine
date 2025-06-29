"""
SurrealEngine: Object-Document Mapper for SurrealDB with both sync and async support
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
    GroupConcat
)
from .query import QuerySet, RelationQuerySet
from .aggregation import AggregationPipeline
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

__version__ = "0.2.0"
__all__ = [
    "SurrealEngine",
    "SurrealEngineAsyncConnection",
    "SurrealEngineSyncConnection",
    "SurrealEngineConnection",  # For backward compatibility
    "BaseSurrealEngineConnection",
    "create_connection",
    "ConnectionRegistry",
    "Document",
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
    "format_datatables_response"
]
