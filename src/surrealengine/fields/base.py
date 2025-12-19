"""
Base field classes for SurrealEngine document field definitions.

This module provides the fundamental field types used to define document schemas
in SurrealEngine. All field types inherit from the base Field class and provide
validation, serialization, and database conversion functionality.

Classes:
    Field: Base class for all field types
    RecordIDField: Field for SurrealDB record IDs
    
Key Features:
    - Type validation and conversion
    - Database serialization/deserialization  
    - Signal support for field operations
    - Extensible validation system
"""
import datetime
import re
import uuid
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Pattern, Type, TypeVar, Union, cast

from surrealdb import RecordID
from ..exceptions import ValidationError
from ..signals import (
    pre_validate, post_validate, pre_to_db, post_to_db,
    pre_from_db, post_from_db, SIGNAL_SUPPORT
)
import json

# Type variable for field types
T = TypeVar('T')

class Field:
    """Base class for all field types.

    This class provides the foundation for all field types in the document model.
    It includes methods for validation and conversion between Python and database
    representations.

    Attributes:
        required: Whether the field is required
        default: Default value for the field
        name: Name of the field (set during document class creation)
        db_field: Name of the field in the database
        owner_document: The document class that owns this field
        define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
    """

    def __init__(self, required: bool = False, default: Any = None, db_field: Optional[str] = None,
                 define_schema: bool = False, indexed: bool = False, unique: bool = False, 
                 search: bool = False, analyzer: Optional[str] = None, index_with: Optional[List[str]] = None,
                 comment: Optional[str] = None) -> None:
        """Initialize a new Field.

        Args:
            required: Whether the field is required
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed
            unique: Whether the index should enforce uniqueness
            search: Whether the index is a search index
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        self.required = required
        self.default = default
        self.name: Optional[str] = None  # Will be set during document class creation
        self.db_field = db_field
        self.owner_document: Optional[Type] = None
        self.define_schema = define_schema
        self.indexed = indexed
        self.unique = unique
        self.search = search
        self.analyzer = analyzer
        self.index_with = index_with
        self.py_type = Any
        self.comment = comment

    def validate(self, value: Any) -> Any:
        """Validate the field value.

        This method checks if the value is valid for this field type.
        Subclasses should override this method to provide type-specific validation.

        Args:
            value: The value to validate

        Returns:
            The validated value

        Raises:
            ValidationError: If the value is invalid for this field type
            ValueError: If the value is None and the field is required

        Examples:
            Basic validation:

            >>> field = StringField(required=True)
            >>> field.validate("hello")
            'hello'

            Required field validation:

            >>> field = StringField(required=True)
            >>> field.validate(None)  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ValueError: Field 'field_name' is required
        """
        # Trigger pre_validate signal
        if SIGNAL_SUPPORT:
            pre_validate.send(self.__class__, field=self, value=value)

        if value is None and self.required:
            raise ValueError(f"Field '{self.name}' is required")

        result = value

        # Trigger post_validate signal
        if SIGNAL_SUPPORT:
            post_validate.send(self.__class__, field=self, value=result)

        return result

    def to_db(self, value: Any) -> Any:
        """Convert Python value to database representation.

        This method converts a Python value to a representation that can be
        stored in the database. Subclasses should override this method to
        provide type-specific conversion.

        Args:
            value: The Python value to convert

        Returns:
            The database representation of the value

        Examples:
            Basic to_db conversion:

            >>> field = Field()
            >>> field.to_db("hello")
            'hello'

            None value handling:

            >>> field.to_db(None)
            
        """
        # Trigger pre_to_db signal
        if SIGNAL_SUPPORT:
            pre_to_db.send(self.__class__, field=self, value=value)

        result = value

        # Trigger post_to_db signal
        if SIGNAL_SUPPORT:
            post_to_db.send(self.__class__, field=self, value=result)

        return result

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python representation.

        This method converts a value from the database to a Python value.
        Subclasses should override this method to provide type-specific conversion.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the value

        Examples:
            Basic from_db conversion:

            >>> field = Field()
            >>> field.from_db("hello")
            'hello'

            None value handling:

            >>> field.from_db(None)
            
        """
        # Trigger pre_from_db signal
        if SIGNAL_SUPPORT:
            pre_from_db.send(self.__class__, field=self, value=value)

        result = value

        # Trigger post_from_db signal
        if SIGNAL_SUPPORT:
            post_from_db.send(self.__class__, field=self, value=result)

        return result

    def get_surreal_type(self) -> str:
        """Return the SurrealQL type name for this field.

        This method returns the appropriate SurrealQL type name that corresponds
        to this field type. Subclasses should override this method to provide
        their specific SurrealQL type.

        Returns:
            The SurrealQL type name as a string

        Examples:
            >>> field = Field()
            >>> field.get_surreal_type()
            'any'
        """
        return 'any'

    def cast_to_surreal_type(self) -> str:
        """Return SurrealQL type casting syntax.
        
        This method returns the SurrealQL type casting syntax for this field,
        which can be used in queries to explicitly cast values to the correct type.

        Returns:
            The SurrealQL type casting syntax

        Examples:
            >>> field = Field()
            >>> field.cast_to_surreal_type()
            '<any>'
        """
        return f"<{self.get_surreal_type()}>"