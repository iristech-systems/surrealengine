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
from .document import Document
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
    OptionField
)
from .query import QuerySet, RelationQuerySet
from .schema import (
    get_document_classes,
    create_tables_from_module,
    create_tables_from_module_sync,
    generate_schema_statements,
    generate_schema_statements_from_module
)

__version__ = "0.1.0"
__all__ = [
    "SurrealEngine",
    "SurrealEngineAsyncConnection",
    "SurrealEngineSyncConnection",
    "SurrealEngineConnection",  # For backward compatibility
    "BaseSurrealEngineConnection",
    "create_connection",
    "ConnectionRegistry",
    "Document",
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
    # Schema generation functions
    "get_document_classes",
    "create_tables_from_module",
    "create_tables_from_module_sync",
    "generate_schema_statements",
    "generate_schema_statements_from_module"
]
