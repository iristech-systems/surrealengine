"""
SurrealEngine: Async Object-Document Mapper for SurrealDB
"""

from .connection import SurrealEngineConnection, ConnectionRegistry
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
    FutureField
)
from .query import QuerySet, RelationQuerySet

__version__ = "0.1.0"
__all__ = [
    "SurrealEngine",
    "SurrealEngineConnection",
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
    "FutureField"
]