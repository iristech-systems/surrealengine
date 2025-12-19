"""
Document classes for object-document mapping with SurrealDB.

This module provides the foundation for defining and working with documents
in SurrealDB using an Object-Document Mapper (ODM) pattern. It includes
the base Document class, RelationDocument for graph relationships, and
supporting metaclasses for field processing and schema generation.

Classes:
    DocumentMetaclass: Metaclass for processing field definitions
    Document: Base class for all database documents
    RelationDocument: Base class for graph relation documents
    HybridDocument: Document with backend-specific field handling
"""
import json
import datetime
import logging
from dataclasses import dataclass, field as dataclass_field, make_dataclass
from typing import Any, Dict, List, Optional, Type, Union, ClassVar
from .query import QuerySet, RelationQuerySet, QuerySetDescriptor
from .fields import Field, RecordIDField, ReferenceField, DictField
from .connection import ConnectionRegistry, SurrealEngineAsyncConnection, SurrealEngineSyncConnection
from surrealdb import RecordID
from .signals import (
    pre_init, post_init, pre_save, pre_save_post_validation, post_save,
    pre_delete, post_delete, pre_bulk_insert, post_bulk_insert, SIGNAL_SUPPORT
)
from .materialized_view import MaterializedView


# Set up logging
logger = logging.getLogger(__name__)


# Robust import for SDK datetime wrapper
try:
    from surrealdb.data.types.datetime import IsoDateTimeWrapper  # new path
except Exception:  # pragma: no cover
    try:
        from surrealdb.types import IsoDateTimeWrapper  # older path
    except Exception:
        IsoDateTimeWrapper = None

def _iso_from_wrapper(w) -> str:
    if w is None:
        return ""
    s = getattr(w, "dt", None)
    if isinstance(s, datetime.datetime):
        return s.isoformat()
    if isinstance(s, str):
        return s
    s2 = getattr(w, "iso", None)
    if isinstance(s2, str):
        return s2
    return str(w)

# Universal HTTP-safe serializer for outgoing payloads
def _serialize_http_safe(value: Any):
    """Recursively process values for SurrealDB SDK.

    Convert IsoDateTimeWrapper back to raw datetime - the SDK handles that better.
    """
    import datetime as _dt

    try:
        from surrealdb.data.types.datetime import IsoDateTimeWrapper as _Iso
    except Exception:
        try:
            from surrealdb.types import IsoDateTimeWrapper as _Iso
        except Exception:
            _Iso = None
    
    # Pass through primitives and datetime unchanged
    if value is None or isinstance(value, (str, int, float, bool, _dt.datetime)):
        return value

    # Convert IsoDateTimeWrapper/Datetime back to datetime
    try:
        from surrealdb import Datetime
        if isinstance(value, Datetime):
            if hasattr(value, 'inner') and isinstance(value.inner, _dt.datetime):
                return value.inner
            if hasattr(value, 'dt') and isinstance(value.dt, _dt.datetime):
                return value.dt
            return value 
    except ImportError:
        pass

    if _Iso and isinstance(value, _Iso):
        dt_val = getattr(value, 'dt', None)
        if isinstance(dt_val, _dt.datetime):
            return dt_val
        iso_val = getattr(value, 'iso', None)
        if isinstance(iso_val, str):
            try:
                return _dt.datetime.fromisoformat(iso_val.replace('Z', '+00:00'))
            except:
                pass
        return value

    # Recursively handle collections
    if isinstance(value, list):
        return [_serialize_http_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_http_safe(v) for k, v in value.items()}

    # Pass through everything else unchanged
    return value


def _serialize_for_surreal(value: Any) -> str:
    """Serialize Python values to SurrealDB-friendly literal strings."""
    # Datetime wrappers and datetime objects
    try:
        from surrealdb import Datetime
        if isinstance(value, Datetime):
            dt = None
            if hasattr(value, 'inner') and isinstance(value.inner, datetime.datetime):
                dt = value.inner
            elif hasattr(value, 'dt') and isinstance(value.dt, datetime.datetime):
                dt = value.dt
            
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                iso = dt.isoformat().replace("+00:00", "Z")
                return f"d'{iso}'"
            return str(value)
    except ImportError:
        pass

    if IsoDateTimeWrapper is not None and isinstance(value, IsoDateTimeWrapper):
        iso = _iso_from_wrapper(value).replace("+00:00", "Z")
        return f"d'{iso}'"
    if isinstance(value, datetime.datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=datetime.timezone.utc)
        iso = dt.isoformat().replace("+00:00", "Z")
        return f"d'{iso}'"

    # Already a Surreal datetime literal
    if isinstance(value, str):
        if value.startswith("d'") and value.endswith("'"):
            return value
        return json.dumps(value)

    if value is None:
        return "none"

    if isinstance(value, list):
        return '[' + ', '.join(_serialize_for_surreal(v) for v in value) + ']'
    if isinstance(value, tuple):
        return '[' + ', '.join(_serialize_for_surreal(v) for v in value) + ']'
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            items.append(json.dumps(str(k)) + ": " + _serialize_for_surreal(v))
        return '{' + ', '.join(items) + '}'

    try:
        return json.dumps(value)
    except TypeError:
        return json.dumps(str(value))


class DocumentMetaclass(type):
    """Metaclass for Document classes.

    This metaclass processes field attributes in Document classes to create
    a structured schema. It handles field inheritance, field naming, and
    metadata configuration.

    Attributes:
        _meta: Dictionary of metadata for the document class
        _fields: Dictionary of fields for the document class
        _fields_ordered: List of field names in order of definition
    """

    def __new__(mcs, name: str, bases: tuple, attrs: Dict[str, Any]) -> Type:
        """Create a new Document class.

        This method processes the class attributes to create a structured schema.
        It handles field inheritance, field naming, and metadata configuration.

        Args:
            name: Name of the class being created
            bases: Tuple of base classes
            attrs: Dictionary of class attributes

        Returns:
            The new Document class
        """
        # Skip processing for the base Document class
        if name == 'Document' and attrs.get('__module__') == __name__:
            return super().__new__(mcs, name, bases, attrs)

        # Get or create _meta
        meta = attrs.get('Meta', type('Meta', (), {}))
        attrs['_meta'] = {
            'collection': getattr(meta, 'collection', name.lower()),
            'indexes': getattr(meta, 'indexes', []),
            'id_field': getattr(meta, 'id_field', 'id'),
            'strict': getattr(meta, 'strict', True),
            'time_series': getattr(meta, 'time_series', False),
            'time_field': getattr(meta, 'time_field', None),
            'abstract': getattr(meta, 'abstract', False),
        }

        # Process fields
        fields: Dict[str, Field] = {}
        fields_ordered: List[str] = []

        # Inherit fields from parent classes
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)
                fields_ordered.extend(base._fields_ordered)

        # Add fields from current class
        for attr_name, attr_value in list(attrs.items()):
            if isinstance(attr_value, Field):
                fields[attr_name] = attr_value
                fields_ordered.append(attr_name)

                # Set field name
                attr_value.name = attr_name

                # Set db_field if not set
                if not attr_value.db_field:
                    attr_value.db_field = attr_name

                # Remove the field from attrs so it doesn't become a class attribute
                del attrs[attr_name]

        attrs['_fields'] = fields
        attrs['_fields_ordered'] = fields_ordered

        # Create the new class
        new_class = super().__new__(mcs, name, bases, attrs)

        # Assign owner document to fields
        for field_name, field in new_class._fields.items():
            field.owner_document = new_class

        return new_class


class Document(metaclass=DocumentMetaclass):
    """Base class for all documents.

    This class provides the foundation for all document models in the ORM.
    It includes methods for CRUD operations, validation, and serialization.

    Attributes:
        objects: QuerySetDescriptor for querying documents of this class
        _data: Dictionary of field values
        _changed_fields: List of field names that have been changed
        _fields: Dictionary of fields for this document class (class attribute)
        _fields_ordered: List of field names in order of definition (class attribute)
        _meta: Dictionary of metadata for this document class (class attribute)

    Meta Options:
        The Meta inner class can be used to configure various document options:

        collection (str): Name of the database collection/table. Defaults to lowercase class name.
        indexes (List[Dict]): List of index definitions. Each index dict can contain:
            - keys (List[str]): Field names to include in the index
            - unique (bool): Whether the index enforces uniqueness (default: False)
            - name (str): Custom name for the index
            - type (str): Index type (e.g., "search" for full-text search)
        id_field (str): Name of the ID field. Defaults to "id".
        strict (bool): Whether to enforce strict field validation. Defaults to True.
            When False, allows dynamic fields not defined in the schema.
        time_series (bool): Whether this is a time series table. Defaults to False.
        time_field (str): Field to use for time series timestamp. Required when time_series is True.
        abstract (bool): Whether this document is abstract. Abstract documents are not registered
            with the database and are meant to be inherited.

    Example:
        >>> class User(Document):
        ...     name = StringField(required=True)
        ...     email = StringField(indexed=True, unique=True)
        ...     
        ...     class Meta:
        ...         collection = "users"
        ...         indexes = [
        ...             {"keys": ["email"], "unique": True},
        ...             {"keys": ["name", "created_at"]}
        ...         ]
    """
    objects = QuerySetDescriptor()
    id = RecordIDField()

    def __init__(self, **values: Any) -> None:
        """Initialize a new Document.

        Args:
            **values: Field values to set on the document

        Raises:
            AttributeError: If strict mode is enabled and an unknown field is provided
        """
        if 'id' not in self._fields:
            self._fields['id'] = RecordIDField()

        # Trigger pre_init signal
        if SIGNAL_SUPPORT:
            pre_init.send(self.__class__, document=self, values=values)

        self._data: Dict[str, Any] = {}
        self._changed_fields: List[str] = []
        self._original_data: Dict[str, Any] = {}  # Track original values for change detection

        # Set default values
        for field_name, field in self._fields.items():
            value = field.default
            if callable(value):
                value = value()
            self._data[field_name] = value

        # Set values from kwargs
        for key, value in values.items():
            if key in self._fields:
                setattr(self, key, value)
            elif self._meta.get('strict', True):
                raise AttributeError(f"Unknown field: {key}")

        # For new documents, mark as clean after initialization
        # since initial value setting shouldn't count as "changes"
        if not self.id:  # New document
            self.mark_clean()

        # Trigger post_init signal
        if SIGNAL_SUPPORT:
            post_init.send(self.__class__, document=self)

    def __getattr__(self, name: str) -> Any:
        """Get a field value.

        This method is called when an attribute is not found through normal lookup.
        It checks if the attribute is a field and returns its value if it is.

        Args:
            name: Name of the attribute to get

        Returns:
            The field value

        Raises:
            AttributeError: If the attribute is not a field
        """
        if name in self._fields:
            # Return the value directly from _data instead of the field instance
            return self._data.get(name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Set a field value.

        This method is called when an attribute is set. It checks if the attribute
        is a field and validates the value if it is.

        Args:
            name: Name of the attribute to set
            value: Value to set
        """
        if name.startswith('_'):
            super().__setattr__(name, value)
        elif name in self._fields:
            field = self._fields[name]
            # Store original value before changing (if not already tracked)
            if name not in self._changed_fields and hasattr(self, '_original_data'):
                self._original_data[name] = self._data.get(name)
            self._data[name] = field.validate(value)
            if name not in self._changed_fields:
                self._changed_fields.append(name)
        else:
            super().__setattr__(name, value)

    @property
    def id(self) -> Any:
        """Get the document ID.

        Returns:
            The document ID
        """
        return self._data.get('id')

    @id.setter
    def id(self, value: Any) -> None:
        """Set the document ID.

        Args:
            value: The document ID to set
        """
        if 'id' in self._fields:
            field = self._fields['id']
            # Store original value before changing (if not already tracked)
            if 'id' not in self._changed_fields and hasattr(self, '_original_data'):
                self._original_data['id'] = self._data.get('id')
            self._data['id'] = field.validate(value)
            if 'id' not in self._changed_fields:
                self._changed_fields.append('id')
        else:
            self._data['id'] = value

    @classmethod
    def _get_collection_name(cls) -> str:
        """Return the collection name for this document.

        Returns:
            The collection name
        """
        return cls._meta.get('collection')

    # ================================
    # ENHANCED CHANGE TRACKING METHODS
    # ================================
    
    def has_changed(self, field: str = None) -> bool:
        """Check if the document or a specific field has changed.
        
        Args:
            field: Optional field name to check. If None, checks if any field changed.
            
        Returns:
            True if the document/field has changed, False otherwise
            
        Examples:
            >>> user = User(name="John", age=30)
            >>> await user.save()
            >>> user.age = 31
            >>> user.has_changed()  # True
            >>> user.has_changed('age')  # True 
            >>> user.has_changed('name')  # False
        """
        if field:
            return field in self._changed_fields
        return len(self._changed_fields) > 0
    
    def get_changes(self) -> Dict[str, Any]:
        """Get a dictionary of all changed fields and their new values.
        
        Returns:
            Dictionary mapping field names to their new values
            
        Examples:
            >>> user.age = 31
            >>> user.name = "Jane"
            >>> user.get_changes()  # {'age': 31, 'name': 'Jane'}
        """
        return {field: self._data.get(field) for field in self._changed_fields}
    
    def get_original_value(self, field: str) -> Any:
        """Get the original value of a field before any changes.
        
        Args:
            field: Name of the field
            
        Returns:
            The original value of the field
            
        Examples:
            >>> user.age = 31  # was 30
            >>> user.get_original_value('age')  # 30
        """
        return self._original_data.get(field)
    
    def revert_changes(self, fields: List[str] = None) -> None:
        """Revert changes to original values.
        
        Args:
            fields: Optional list of field names to revert. If None, reverts all changes.
            
        Examples:
            >>> user.age = 31
            >>> user.name = "Jane" 
            >>> user.revert_changes(['age'])  # Only revert age
            >>> user.revert_changes()  # Revert all changes
        """
        if fields:
            # Revert specific fields
            for field in fields:
                if field in self._changed_fields and field in self._original_data:
                    self._data[field] = self._original_data[field]
                    self._changed_fields.remove(field)
        else:
            # Revert all changes
            for field in list(self._changed_fields):
                if field in self._original_data:
                    self._data[field] = self._original_data[field]
            self._changed_fields.clear()
    
    @property
    def is_dirty(self) -> bool:
        """Check if the document has unsaved changes.
        
        Returns:
            True if there are unsaved changes, False otherwise
            
        Examples:
            >>> user.is_dirty  # False
            >>> user.age = 31
            >>> user.is_dirty  # True
            >>> await user.save()
            >>> user.is_dirty  # False
        """
        return len(self._changed_fields) > 0
    
    @property
    def is_clean(self) -> bool:
        """Check if the document has no unsaved changes.
        
        Returns:
            True if there are no unsaved changes, False otherwise
        """
        return len(self._changed_fields) == 0
    
    @property
    def dirty_fields(self) -> List[str]:
        """Get list of field names that have been changed.
        
        Returns:
            List of field names with unsaved changes
            
        Examples:
            >>> user.age = 31
            >>> user.name = "Jane"
            >>> user.dirty_fields  # ['age', 'name']
        """
        return self._changed_fields.copy()
    
    def mark_clean(self) -> None:
        """Mark the document as clean (no pending changes).
        
        This updates the original data to match current data and clears changed fields.
        Usually called automatically after successful save operations.
        """
        from copy import deepcopy
        self._original_data = deepcopy(self._data)
        self._changed_fields.clear()
    
    def get_changed_data_for_update(self) -> Dict[str, Any]:
        """Get only the changed fields formatted for database update.
        
        Returns:
            Dictionary of changed fields in database format
            
        This is used internally for optimized updates that only send changed fields.
        """
        if not self._changed_fields:
            return {}
        
        # Get changed data and convert to DB format
        changed_data = {}
        for field_name in self._changed_fields:
            # Note: We don't skip the 'id' field here anymore because:
            # 1. SurrealDB handles it properly in upsert operations
            # 2. The ID might be stored as a string and needed for queries
            # 3. Skipping it can break RecordID-based queries
            if field_name in self._fields:
                field = self._fields[field_name]
                value = self._data.get(field_name)
                changed_data[field.db_field or field_name] = field.to_db(value)
            else:
                changed_data[field_name] = self._data.get(field_name)
        
        return changed_data

    def validate(self) -> None:
        """Validate all fields.

        This method validates all fields in the document against their
        validation rules.

        Raises:
            ValidationError: If a field fails validation
        """
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            field.validate(value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the document to a dictionary.

        This method converts the document to a dictionary containing all
        field values including the document ID. It ensures that RecordID
        objects are properly converted to strings for JSON serialization.
        It also recursively converts embedded documents to dictionaries.

        Returns:
            Dictionary of field values including ID
        """
        result = {}
        for k, v in self._data.items():
            # Convert RecordID objects to strings
            if isinstance(v, RecordID):
                result[k] = str(v)
            # Handle embedded documents by recursively calling to_dict()
            elif hasattr(v, 'to_dict') and callable(v.to_dict):
                result[k] = v.to_dict()
            # Handle lists that might contain RecordIDs or embedded documents
            elif isinstance(v, list):
                result[k] = [
                    item.to_dict() if hasattr(item, 'to_dict') and callable(item.to_dict)
                    else str(item) if isinstance(item, RecordID)
                    else item
                    for item in v
                ]
            # Handle dicts that might contain RecordIDs or embedded documents
            elif isinstance(v, dict):
                result[k] = {
                    key: val.to_dict() if hasattr(val, 'to_dict') and callable(val.to_dict)
                    else str(val) if isinstance(val, RecordID)
                    else val
                    for key, val in v.items()
                }
            else:
                result[k] = v
        return result

    def to_db(self) -> Dict[str, Any]:
        """Convert the document to a database-friendly dictionary.

        This method converts the document to a dictionary suitable for
        storage in the database. It applies field-specific conversions
        and includes only non-None values unless the field is required.

        Returns:
            Dictionary of field values for the database
        """
        result = {}
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            if value is not None or field.required:
                db_field = field.db_field or field_name
                result[db_field] = field.to_db(value)
        return result

    @classmethod
    def from_db(cls, data: Any, dereference: bool = False, partial: bool = False) -> 'Document':
        """Create a document instance from database data.

        Args:
            data: Data from the database (dictionary, string, RecordID, etc.)
            dereference: Whether to dereference references (default: False)
            partial: Whether the data is a partial document (default: False)

        Returns:
            A new document instance
        """
        # Create an empty instance without triggering signals
        instance = cls.__new__(cls)

        # Initialize _data, _changed_fields, and _original_data
        instance._data = {}
        instance._changed_fields = []
        instance._original_data = {}

        # Add id field if not present
        if 'id' not in instance._fields:
            instance._fields['id'] = RecordIDField()

        # If not partial, set default values
        if not partial:
            for field_name, field in instance._fields.items():
                value = field.default
                if callable(value):
                    value = value()
                instance._data[field_name] = value

        # If data is a dictionary, update with database values
        if isinstance(data, dict):
            # First, handle fields with db_field mapping
            for field_name, field in instance._fields.items():
                db_field = field.db_field or field_name
                if db_field in data:
                    # Pass the dereference parameter to from_db if the field supports it
                    if hasattr(field, 'from_db') and 'dereference' in field.from_db.__code__.co_varnames:
                        instance._data[field_name] = field.from_db(data[db_field], dereference=dereference)
                    else:
                        instance._data[field_name] = field.from_db(data[db_field])

            # Then, handle fields without db_field mapping (for backward compatibility)
            for key, value in data.items():
                if key in instance._fields:
                    field = instance._fields[key]
                    # Pass the dereference parameter to from_db if the field supports it
                    if hasattr(field, 'from_db') and 'dereference' in field.from_db.__code__.co_varnames:
                        instance._data[key] = field.from_db(value, dereference=dereference)
                    else:
                        instance._data[key] = field.from_db(value)
        # If data is a RecordID or string, set it as the ID
        elif isinstance(data, (RecordID, str)):
            instance._data['id'] = data
        # For other types, try to convert to string and set as ID
        else:
            try:
                instance._data['id'] = str(data)
            except (TypeError, ValueError):
                # If conversion fails, just use the data as is
                pass

        # Initialize original data for change tracking
        from copy import deepcopy
        instance._original_data = deepcopy(instance._data)
        
        return instance

    async def resolve_references(self, depth: int = 1) -> 'Document':
        """Resolve all references in this document using FETCH.

        This method uses SurrealDB's FETCH clause to efficiently resolve references
        instead of making individual queries for each reference.

        Args:
            depth: Maximum depth of reference resolution (default: 1)

        Returns:
            The document instance with resolved references
        """
        if depth <= 0 or not self.id:
            return self

        # Build FETCH clause for all reference fields
        fetch_fields = []
        for field_name, field in self._fields.items():
            if isinstance(field, ReferenceField) and getattr(self, field_name):
                fetch_fields.append(field_name)
        
        if not fetch_fields:
            return self

        # Use FETCH to resolve references in a single query
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        query = f"SELECT * FROM `{self.id}` FETCH {', '.join(fetch_fields)}"
        
        try:
            # Use FETCH with a WHERE clause instead of selecting from specific record
            fetch_query = f"SELECT * FROM {self.__class__._get_collection_name()} WHERE id = {self.id} FETCH {', '.join(fetch_fields)}"
            result = await connection.client.query(fetch_query)
            if result and result[0]:
                # Update this document with fetched data
                fetched_data = result[0][0]
                updated_doc = self.from_db(fetched_data)
                
                # Copy the resolved references to this instance
                for field_name in fetch_fields:
                    if hasattr(updated_doc, field_name):
                        setattr(self, field_name, getattr(updated_doc, field_name))
                
                # If depth > 1, recursively resolve references in fetched documents
                if depth > 1:
                    for field_name in fetch_fields:
                        referenced_doc = getattr(self, field_name, None)
                        if referenced_doc and hasattr(referenced_doc, 'resolve_references'):
                            await referenced_doc.resolve_references(depth=depth-1)
        except Exception:
            # Fall back to manual resolution if FETCH fails
            for field_name, field in self._fields.items():
                if isinstance(field, ReferenceField) and getattr(self, field_name):
                    ref_id = getattr(self, field_name)
                    if isinstance(ref_id, str) and ':' in ref_id:
                        referenced_doc = await field.document_type.get(id=ref_id, dereference=True)
                        if referenced_doc and depth > 1:
                            await referenced_doc.resolve_references(depth=depth-1)
                        setattr(self, field_name, referenced_doc)
                    elif isinstance(ref_id, RecordID):
                        ref_id_str = str(ref_id)
                        referenced_doc = await field.document_type.get(id=ref_id_str, dereference=True)
                        if referenced_doc and depth > 1:
                            await referenced_doc.resolve_references(depth=depth-1)
                        setattr(self, field_name, referenced_doc)

        return self

    def resolve_references_sync(self, depth: int = 1) -> 'Document':
        """Resolve all references in this document synchronously using FETCH.

        This method uses SurrealDB's FETCH clause to efficiently resolve references
        instead of making individual queries for each reference.

        Args:
            depth: Maximum depth of reference resolution (default: 1)

        Returns:
            The document instance with resolved references
        """
        if depth <= 0 or not self.id:
            return self

        # Build FETCH clause for all reference fields
        fetch_fields = []
        for field_name, field in self._fields.items():
            if isinstance(field, ReferenceField) and getattr(self, field_name):
                fetch_fields.append(field_name)
        
        if not fetch_fields:
            return self

        # Use FETCH to resolve references in a single query
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        query = f"SELECT * FROM `{self.id}` FETCH {', '.join(fetch_fields)}"
        
        try:
            # Use FETCH with a WHERE clause instead of selecting from specific record
            fetch_query = f"SELECT * FROM {self.__class__._get_collection_name()} WHERE id = {self.id} FETCH {', '.join(fetch_fields)}"
            result = connection.client.query(fetch_query)
            if result and result[0]:
                # Update this document with fetched data
                fetched_data = result[0][0]
                updated_doc = self.from_db(fetched_data)
                
                # Copy the resolved references to this instance
                for field_name in fetch_fields:
                    if hasattr(updated_doc, field_name):
                        setattr(self, field_name, getattr(updated_doc, field_name))
                
                # If depth > 1, recursively resolve references in fetched documents
                if depth > 1:
                    for field_name in fetch_fields:
                        referenced_doc = getattr(self, field_name, None)
                        if referenced_doc and hasattr(referenced_doc, 'resolve_references_sync'):
                            referenced_doc.resolve_references_sync(depth=depth-1)
        except Exception:
            # Fall back to manual resolution if FETCH fails
            for field_name, field in self._fields.items():
                if isinstance(field, ReferenceField) and getattr(self, field_name):
                    ref_id = getattr(self, field_name)
                    if isinstance(ref_id, str) and ':' in ref_id:
                        referenced_doc = field.document_type.get_sync(id=ref_id, dereference=True)
                        if referenced_doc and depth > 1:
                            referenced_doc.resolve_references_sync(depth=depth-1)
                        setattr(self, field_name, referenced_doc)
                    elif isinstance(ref_id, RecordID):
                        ref_id_str = str(ref_id)
                        referenced_doc = field.document_type.get_sync(id=ref_id_str, dereference=True)
                        if referenced_doc and depth > 1:
                            referenced_doc.resolve_references_sync(depth=depth-1)
                        setattr(self, field_name, referenced_doc)

        return self

    @classmethod
    async def get(cls, id: Any, dereference: bool = False, dereference_depth: int = 1, **kwargs: Any) -> 'Document':
        """Get a document by ID with optional dereferencing using FETCH.

        This method retrieves a document by ID and optionally resolves references
        using SurrealDB's FETCH clause for efficient reference resolution.

        Args:
            id: The ID of the document to retrieve
            dereference: Whether to resolve references (default: False)
            dereference_depth: Maximum depth of reference resolution (default: 1)
            **kwargs: Additional arguments to pass to the get method

        Returns:
            The document instance with optionally resolved references

        Examples:
            Get a document by ID:

            >>> user = await User.get("user:123")
            >>> print(f"Retrieved user: {user.name}")

            Get with full record ID:

            >>> task = await Task.get("tasks:abc123")
            >>> print(f"Task: {task.title}")

            Get with reference dereferencing:

            >>> post = await Post.get("post:456", dereference=True)
            >>> print(f"Post by: {post.author.name}")  # author is resolved

            Get with deep dereferencing:

            >>> post = await Post.get("post:456", dereference=True, dereference_depth=2)
            # Resolves references 2 levels deep
        """
        if not dereference:
            # No dereferencing needed, use regular get
            return await cls.objects.get(id=id, **kwargs)
        
        # Build FETCH clause for reference fields
        fetch_fields = []
        for field_name, field in cls._fields.items():
            if isinstance(field, ReferenceField):
                fetch_fields.append(field_name)
        
        if fetch_fields:
            # Use FETCH to resolve references in the initial query
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
            
            # Handle ID format - both strings and RecordID objects
            if (isinstance(id, str) and ':' in id) or isinstance(id, RecordID):
                record_id = str(id)  # Convert RecordID to string
            else:
                record_id = f"{cls._get_collection_name()}:{id}"
            
            try:
                # Use FETCH on the entire collection, then filter
                fetch_query = f"SELECT * FROM {cls._get_collection_name()} FETCH {', '.join(fetch_fields)}"
                result = await connection.client.query(fetch_query)
                if not result or not result[0]:
                    from .exceptions import DoesNotExist
                    raise DoesNotExist(f"Object with ID '{id}' does not exist.")
                
                # Handle both single document and list of documents
                documents = result[0]
                target_doc = None
                
                # If documents is a single dict, wrap it in a list
                if isinstance(documents, dict):
                    documents = [documents]
                
                # Find the document with the matching ID
                for doc_data in documents:
                    if isinstance(doc_data, dict) and str(doc_data.get('id')) == record_id:
                        target_doc = doc_data
                        break
                
                if not target_doc:
                    from .exceptions import DoesNotExist
                    raise DoesNotExist(f"Object with ID '{id}' does not exist.")
                
                document = cls.from_db(target_doc)
                
                # If dereference_depth > 1, recursively resolve deeper references
                if dereference_depth > 1:
                    await document.resolve_references(depth=dereference_depth)
                
                return document
            except Exception as e:
                # Fall back to regular get with manual dereferencing
                logger.error(f"Error getting document {id}: {e}")
                raise
        
        # Fallback to original method
        document = await cls.objects.get(id=id, **kwargs)
        if dereference and dereference_depth > 1 and document:
            await document.resolve_references(depth=dereference_depth)
        return document

    @classmethod
    def get_sync(cls, id: Any, dereference: bool = False, dereference_depth: int = 1, **kwargs: Any) -> 'Document':
        """Get a document by ID with optional dereferencing synchronously using FETCH.

        This method retrieves a document by ID and optionally resolves references
        using SurrealDB's FETCH clause for efficient reference resolution.

        Args:
            id: The ID of the document to retrieve
            dereference: Whether to resolve references (default: False)
            dereference_depth: Maximum depth of reference resolution (default: 1)
            **kwargs: Additional arguments to pass to the get method

        Returns:
            The document instance with optionally resolved references
        """
        if not dereference:
            # No dereferencing needed, use regular get
            return cls.objects.get_sync(id=id, **kwargs)
        
        # Build FETCH clause for reference fields
        fetch_fields = []
        for field_name, field in cls._fields.items():
            if isinstance(field, ReferenceField):
                fetch_fields.append(field_name)
        
        if fetch_fields:
            # Use FETCH to resolve references in the initial query
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
            
            # Handle ID format - both strings and RecordID objects
            if (isinstance(id, str) and ':' in id) or isinstance(id, RecordID):
                record_id = str(id)  # Convert RecordID to string
            else:
                record_id = f"{cls._get_collection_name()}:{id}"
            
            try:
                # Use FETCH on the entire collection, then filter
                fetch_query = f"SELECT * FROM {cls._get_collection_name()} FETCH {', '.join(fetch_fields)}"
                result = connection.client.query(fetch_query)
                if not result or not result[0]:
                    from .exceptions import DoesNotExist
                    raise DoesNotExist(f"Object with ID '{id}' does not exist.")
                
                # Handle both single document and list of documents
                documents = result[0]
                target_doc = None
                
                # If documents is a single dict, wrap it in a list
                if isinstance(documents, dict):
                    documents = [documents]
                
                # Find the document with the matching ID
                for doc_data in documents:
                    if isinstance(doc_data, dict) and str(doc_data.get('id')) == record_id:
                        target_doc = doc_data
                        break
                
                if not target_doc:
                    from .exceptions import DoesNotExist
                    raise DoesNotExist(f"Object with ID '{id}' does not exist.")
                
                document = cls.from_db(target_doc)
                
                # If dereference_depth > 1, recursively resolve deeper references
                if dereference_depth > 1:
                    document.resolve_references_sync(depth=dereference_depth)
                
                return document
            except Exception:
                # Fall back to regular get with manual dereferencing
                pass
        
        # Fallback to original method
        document = cls.objects.get_sync(id=id, **kwargs)
        if dereference and dereference_depth > 1 and document:
            document.resolve_references_sync(depth=dereference_depth)
        return document

    async def update(self, connection: Optional[Any] = None, **kwargs) -> 'Document':
        """Update the document with new data.

        Args:
            connection: The database connection to use (optional)
            **kwargs: Fields to update

        Returns:
            The updated document instance
        """
        # Trigger pre_save signal
        if SIGNAL_SUPPORT:
            pre_save.send(self.__class__, document=self)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        # Update fields from kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.validate()
        
        if not self.id:
            raise ValidationError("Cannot update a document without an ID.")

        # Get changed data
        data = self.get_changed_data_for_update()
        if not data:
            return self
            
        data = _serialize_http_safe(data)
        
        # Use merge for partial update
        result = await connection.client.merge(self.id, data)
        
        # Update the current instance with the returned data
        if result:
            doc_data = result[0] if isinstance(result, list) and result else result
            if isinstance(doc_data, dict):
                self._data.update(doc_data)
                # Parse fields
                for field_name, field in self._fields.items():
                    if field_name in doc_data:
                        self._data[field_name] = field.from_db(doc_data[field_name])
        else:
            from .exceptions import DoesNotExist
            raise DoesNotExist(f"Document with ID {self.id} does not exist.")
        
        # Trigger post_save signal
        if SIGNAL_SUPPORT:
            post_save.send(self.__class__, document=self, created=False)

        self.mark_clean()
        return self

    def update_sync(self, connection: Optional[Any] = None, **kwargs) -> 'Document':
        """Update the document with new data synchronously.

        Args:
            connection: The database connection to use (optional)
            **kwargs: Fields to update

        Returns:
            The updated document instance
        """
        # Trigger pre_save signal
        if SIGNAL_SUPPORT:
            pre_save.send(self.__class__, document=self)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        # Update fields from kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.validate()
        
        if not self.id:
            raise ValidationError("Cannot update a document without an ID.")

        # Get changed data
        data = self.get_changed_data_for_update()
        if not data:
            return self
            
        data = _serialize_http_safe(data)
        
        # Use merge for partial update
        result = connection.client.merge(self.id, data)
        
        # Update the current instance with the returned data
        if result:
            doc_data = result[0] if isinstance(result, list) and result else result
            if isinstance(doc_data, dict):
                self._data.update(doc_data)
                # Parse fields
                for field_name, field in self._fields.items():
                    if field_name in doc_data:
                        self._data[field_name] = field.from_db(doc_data[field_name])
        else:
            from .exceptions import DoesNotExist
            raise DoesNotExist(f"Document with ID {self.id} does not exist.")
        
        # Trigger post_save signal
        if SIGNAL_SUPPORT:
            post_save.send(self.__class__, document=self, created=False)

        self.mark_clean()
        return self

    async def save(self, connection: Optional[Any] = None) -> 'Document':
        """Save the document to the database asynchronously.

        This method saves the document to the database, either creating
        a new document or updating an existing one.
        """
        # Trigger pre_save signal
        if SIGNAL_SUPPORT:
            pre_save.send(self.__class__, document=self)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        self.validate()

        # Update existing document if possible
        if self.id and self._changed_fields:
            data = self.get_changed_data_for_update()
            if data:
                from .exceptions import DoesNotExist
                try:
                    return await self.update(connection=connection, **data)
                except DoesNotExist:
                    # Document doesn't exist, proceed to create
                    pass
        
        if self.id and not self._changed_fields:
            return self

        # Create new document
        # Trigger pre_save_post_validation signal
        if SIGNAL_SUPPORT:
            pre_save_post_validation.send(self.__class__, document=self)

        data = self.to_db()
        safe_data = _serialize_http_safe(data)
        
        result = await connection.client.create(
            self._get_collection_name(),
            safe_data
        )
        
        # Update the current instance with the returned data
        if result:
            doc_data = result[0] if isinstance(result, list) and result else result
            if isinstance(doc_data, dict):
                self._data.update(doc_data)
                if 'id' in doc_data:
                    self._data['id'] = doc_data['id']
                for field_name, field in self._fields.items():
                    if field_name in doc_data:
                        self._data[field_name] = field.from_db(doc_data[field_name])
        
        # Trigger post_save signal
        if SIGNAL_SUPPORT:
            post_save.send(self.__class__, document=self, created=True)

        self.mark_clean()
        return self

    def save_sync(self, connection: Optional[Any] = None) -> 'Document':
        """Save the document to the database synchronously.

        This method saves the document to the database, either creating
        a new document or updating an existing one based on whether the
        document has an ID.

        Args:
            connection: The database connection to use (optional)

        Returns:
            The saved document instance

        Raises:
            ValidationError: If the document fails validation
        """
        # Trigger pre_save signal
        if SIGNAL_SUPPORT:
            pre_save.send(self.__class__, document=self)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        self.validate()
        
        # Smart save: use only changed fields for existing documents
        if self.id and self._changed_fields:
            data = self.get_changed_data_for_update()
            if data:
                from .exceptions import DoesNotExist
                try:
                    return self.update_sync(connection=connection, **data)
                except DoesNotExist:
                    pass
        
        # If we have an ID but no changes, we don't need to do anything
        if self.id and not self._changed_fields:
            return self

        # Create new document
        # Trigger pre_save_post_validation signal
        if SIGNAL_SUPPORT:
            pre_save_post_validation.send(self.__class__, document=self)

        data = self.to_db()
        data = _serialize_http_safe(data)
        
        result = connection.client.create(
            self._get_collection_name(),
            data
        )

        # Update the current instance with the returned data
        if result:
            if isinstance(result, list) and result:
                doc_data = result[0]
            else:
                doc_data = result

            # Update the instance's _data with the returned document
            if isinstance(doc_data, dict):
                # First update the raw data
                self._data.update(doc_data)

                # Make sure to capture the ID if it's a new document
                if 'id' in doc_data:
                    self._data['id'] = doc_data['id']

                # Then properly convert each field using its from_db method
                for field_name, field in self._fields.items():
                    if field_name in doc_data:
                        self._data[field_name] = field.from_db(doc_data[field_name])

        # Trigger post_save signal
        if SIGNAL_SUPPORT:
            post_save.send(self.__class__, document=self, created=True)

        # Mark document as clean after successful save
        self.mark_clean()

        return self

    async def delete(self, connection: Optional[Any] = None) -> bool:
        """Delete the document from the database asynchronously.

        This method deletes the document from the database.

        Args:
            connection: The database connection to use (optional)

        Returns:
            True if the document was deleted

        Raises:
            ValueError: If the document doesn't have an ID

        Examples:
            Delete a document:

            >>> user = await User.get("user:123")
            >>> await user.delete()
            >>> print("User deleted successfully")

            Delete with custom connection:

            >>> await user.delete(connection=custom_connection)

            Bulk delete pattern:

            >>> for task in await Task.objects.filter(completed=True).all():
            ...     await task.delete()
        """
        # Trigger pre_delete signal
        if SIGNAL_SUPPORT:
            pre_delete.send(self.__class__, document=self)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        if not self.id:
            raise ValueError("Cannot delete a document without an ID")

        await connection.client.delete(f"{self.id}")

        # Trigger post_delete signal
        if SIGNAL_SUPPORT:
            post_delete.send(self.__class__, document=self)

        return True

    def delete_sync(self, connection: Optional[Any] = None) -> bool:
        """Delete the document from the database synchronously.

        This method deletes the document from the database.

        Args:
            connection: The database connection to use (optional)

        Returns:
            True if the document was deleted

        Raises:
            ValueError: If the document doesn't have an ID
        """
        # Trigger pre_delete signal
        if SIGNAL_SUPPORT:
            pre_delete.send(self.__class__, document=self)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        if not self.id:
            raise ValueError("Cannot delete a document without an ID")

        connection.client.delete(f"{self.id}")

        # Trigger post_delete signal
        if SIGNAL_SUPPORT:
            post_delete.send(self.__class__, document=self)

        return True

    async def refresh(self, connection: Optional[Any] = None) -> 'Document':
        """Refresh the document from the database asynchronously.

        This method refreshes the document's data from the database.

        Args:
            connection: The database connection to use (optional)

        Returns:
            The refreshed document instance

        Raises:
            ValueError: If the document doesn't have an ID
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        if not self.id:
            raise ValueError("Cannot refresh a document without an ID")

        result = await connection.client.select(f"{self.id}")
        if result:
            if isinstance(result, list) and result:
                doc = result[0]
            else:
                doc = result

            for field_name, field in self._fields.items():
                db_field = field.db_field or field_name
                if db_field in doc:
                    self._data[field_name] = field.from_db(doc[db_field])

            # Reset change tracking after refresh
            from copy import deepcopy
            self._original_data = deepcopy(self._data)
            self._changed_fields = []
        return self

    def refresh_sync(self, connection: Optional[Any] = None) -> 'Document':
        """Refresh the document from the database synchronously.

        This method refreshes the document's data from the database.

        Args:
            connection: The database connection to use (optional)

        Returns:
            The refreshed document instance

        Raises:
            ValueError: If the document doesn't have an ID
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        if not self.id:
            raise ValueError("Cannot refresh a document without an ID")

        result = connection.client.select(f"{self.id}")
        if result:
            if isinstance(result, list) and result:
                doc = result[0]
            else:
                doc = result

            for field_name, field in self._fields.items():
                db_field = field.db_field or field_name
                if db_field in doc:
                    self._data[field_name] = field.from_db(doc[db_field])

            # Reset change tracking after refresh
            from copy import deepcopy
            self._original_data = deepcopy(self._data)
            self._changed_fields = []
        return self

    @classmethod
    def relates(cls, relation_name: str) -> callable:
        """Get a RelationQuerySet for a specific relation.

        This method returns a function that creates a RelationQuerySet for
        the specified relation name. The function can be called with an
        optional connection parameter.

        Args:
            relation_name: Name of the relation

        Returns:
            Function that creates a RelationQuerySet
        """

        def relation_query_builder(connection: Optional[Any] = None) -> RelationQuerySet:
            """Create a RelationQuerySet for the specified relation.

            Args:
                connection: The database connection to use (optional)

            Returns:
                A RelationQuerySet for the relation
            """
            if connection is None:
                connection = ConnectionRegistry.get_default_connection()
            return RelationQuerySet(cls, connection, relation=relation_name)

        return relation_query_builder

    async def fetch_relation(self, relation_name: str, target_document: Optional[Type] = None,
                             relation_document: Optional[Type] = None, connection: Optional[Any] = None,
                             **filters: Any) -> List[Any]:
        """Fetch related documents asynchronously.

        This method fetches documents related to this document through
        the specified relation.

        Args:
            relation_name: Name of the relation
            target_document: The document class of the target documents (optional)
            relation_document: The document class representing the relation (optional)
            connection: The database connection to use (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents, relation documents, or relation records
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        result = await relation_query.get_related(self, target_document, **filters)

        # If relation_document is specified, convert the relation records to RelationDocument instances
        if relation_document and not target_document:
            return [relation_document.from_db(record) for record in result]

        return result

    def fetch_relation_sync(self, relation_name: str, target_document: Optional[Type] = None,
                            relation_document: Optional[Type] = None, connection: Optional[Any] = None,
                            **filters: Any) -> List[Any]:
        """Fetch related documents synchronously.

        This method fetches documents related to this document through
        the specified relation.

        Args:
            relation_name: Name of the relation
            target_document: The document class of the target documents (optional)
            relation_document: The document class representing the relation (optional)
            connection: The database connection to use (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents, relation documents, or relation records
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        result = relation_query.get_related_sync(self, target_document, **filters)

        # If relation_document is specified, convert the relation records to RelationDocument instances
        if relation_document and not target_document:
            return [relation_document.from_db(record) for record in result]

        return result

    async def resolve_relation(self, relation_name: str, target_document_class: Optional[Type] = None,
                               relation_document: Optional[Type] = None, connection: Optional[Any] = None) -> List[Any]:
        """Resolve related documents from a relation fetch result asynchronously.

        This method resolves related documents from a relation fetch result.
        It fetches the relation data and then resolves each related document.

        Args:
            relation_name: Name of the relation to resolve
            target_document_class: Class of the target document (optional)
            relation_document: The document class representing the relation (optional)
            connection: Database connection to use (optional)

        Returns:
            List of resolved document instances
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        # If relation_document is specified, convert the relation records to RelationDocument instances
        if relation_document and not target_document_class:
            return await self.fetch_relation(relation_name, relation_document=relation_document, connection=connection)

        # First fetch the relation data
        relation_data = await self.fetch_relation(relation_name, connection=connection)
        if not relation_data:
            return []

        resolved_documents = []
        if isinstance(relation_data, dict) and 'related' in relation_data and isinstance(relation_data['related'],
                                                                                         list):
            for related_id in relation_data['related']:
                if isinstance(related_id, RecordID):
                    collection = related_id.table_name
                    record_id = related_id.id

                    # Fetch the actual document
                    try:
                        result = await connection.client.select(related_id)
                        if result and isinstance(result, list):
                            doc = result[0]
                        else:
                            doc = result

                        if doc:
                            resolved_documents.append(doc)
                    except Exception as e:
                        logger.error(f"Error resolving document {collection}:{record_id}: {str(e)}")

        return resolved_documents

    def resolve_relation_sync(self, relation_name: str, target_document_class: Optional[Type] = None,
                              relation_document: Optional[Type] = None, connection: Optional[Any] = None) -> List[Any]:
        """Resolve related documents from a relation fetch result synchronously.

        This method resolves related documents from a relation fetch result.
        It fetches the relation data and then resolves each related document.

        Args:
            relation_name: Name of the relation to resolve
            target_document_class: Class of the target document (optional)
            relation_document: The document class representing the relation (optional)
            connection: Database connection to use (optional)

        Returns:
            List of resolved document instances
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        # If relation_document is specified, convert the relation records to RelationDocument instances
        if relation_document and not target_document_class:
            return self.fetch_relation_sync(relation_name, relation_document=relation_document, connection=connection)

        # First fetch the relation data
        relation_data = self.fetch_relation_sync(relation_name, connection=connection)
        if not relation_data:
            return []

        resolved_documents = []
        if isinstance(relation_data, dict) and 'related' in relation_data and isinstance(relation_data['related'],
                                                                                         list):
            for related_id in relation_data['related']:
                if isinstance(related_id, RecordID):
                    collection = related_id.table_name
                    record_id = related_id.id

                    # Fetch the actual document
                    try:
                        result = connection.client.select(related_id)
                        if result and isinstance(result, list):
                            doc = result[0]
                        else:
                            doc = result

                        if doc:
                            resolved_documents.append(doc)
                    except Exception as e:
                        logger.error(f"Error resolving document {collection}:{record_id}: {str(e)}")

        return resolved_documents

    async def relate_to(self, relation_name: str, target_instance: Any,
                        connection: Optional[Any] = None, **attrs: Any) -> Optional[Any]:
        """Create a relation to another document asynchronously.

        This method creates a relation from this document to another document.

        Args:
            relation_name: Name of the relation
            target_instance: The document instance to relate to
            connection: The database connection to use (optional)
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed

        Examples:
            Create a simple relation:

            >>> person = await Person.get("person:john")
            >>> book = await Book.get("book:novel")
            >>> relation = await person.relate_to("authored", book)

            Create relation with attributes:

            >>> await person.relate_to("authored", book,
            ...     date_written="2022-01-15T00:00:00Z",
            ...     is_primary_author=True)

            Create multiple relations:

            >>> for book in user_books:
            ...     await author.relate_to("wrote", book, year=2023)
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.relate(self, target_instance, **attrs)

    def relate_to_sync(self, relation_name: str, target_instance: Any,
                       connection: Optional[Any] = None, **attrs: Any) -> Optional[Any]:
        """Create a relation to another document synchronously.

        This method creates a relation from this document to another document.

        Args:
            relation_name: Name of the relation
            target_instance: The document instance to relate to
            connection: The database connection to use (optional)
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return relation_query.relate_sync(self, target_instance, **attrs)

    async def update_relation_to(self, relation_name: str, target_instance: Any,
                                 connection: Optional[Any] = None, **attrs: Any) -> Optional[Any]:
        """Update a relation to another document asynchronously.

        This method updates a relation from this document to another document.

        Args:
            relation_name: Name of the relation
            target_instance: The document instance the relation is to
            connection: The database connection to use (optional)
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.update_relation(self, target_instance, **attrs)

    def update_relation_to_sync(self, relation_name: str, target_instance: Any,
                                connection: Optional[Any] = None, **attrs: Any) -> Optional[Any]:
        """Update a relation to another document synchronously.

        This method updates a relation from this document to another document.

        Args:
            relation_name: Name of the relation
            target_instance: The document instance the relation is to
            connection: The database connection to use (optional)
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return relation_query.update_relation_sync(self, target_instance, **attrs)

    async def delete_relation_to(self, relation_name: str, target_instance: Optional[Any] = None,
                                 connection: Optional[Any] = None) -> int:
        """Delete a relation to another document asynchronously.

        This method deletes a relation from this document to another document.
        If target_instance is not provided, it deletes all relations with the
        specified name from this document.

        Args:
            relation_name: Name of the relation
            target_instance: The document instance the relation is to (optional)
            connection: The database connection to use (optional)

        Returns:
            Number of deleted relations
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.delete_relation(self, target_instance)

    def delete_relation_to_sync(self, relation_name: str, target_instance: Optional[Any] = None,
                                connection: Optional[Any] = None) -> int:
        """Delete a relation to another document synchronously.

        This method deletes a relation from this document to another document.
        If target_instance is not provided, it deletes all relations with the
        specified name from this document.

        Args:
            relation_name: Name of the relation
            target_instance: The document instance the relation is to (optional)
            connection: The database connection to use (optional)

        Returns:
            Number of deleted relations
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return relation_query.delete_relation_sync(self, target_instance)

    async def traverse_path(self, path_spec: str, target_document: Optional[Type] = None,
                            connection: Optional[Any] = None, **filters: Any) -> List[Any]:
        """Traverse a path in the graph asynchronously.

        This method traverses a path in the graph starting from this document.
        The path_spec is a string like "->[watched]->->[acted_in]->" which describes
        a path through the graph.

        Args:
            path_spec: String describing the path to traverse
            target_document: The document class to return instances of (optional)
            connection: The database connection to use (optional)
            **filters: Filters to apply to the results

        Returns:
            List of documents or path results

        Raises:
            ValueError: If the document is not saved
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        if not self.id:
            raise ValueError(f"Cannot traverse from unsaved {self.__class__.__name__}")

        start_id = f"{self.__class__._get_collection_name()}:{self.id}"

        if target_document:
            end_collection = target_document._get_collection_name()
            query = f"SELECT * FROM {end_collection} WHERE {path_spec}{start_id}"
        else:
            query = f"SELECT {path_spec} as path FROM {start_id}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                from .surrealql import escape_literal
                conditions.append(f"{field} = {escape_literal(value)}")

            if target_document:
                query += f" AND {' AND '.join(conditions)}"
            else:
                query += f" WHERE {' AND '.join(conditions)}"

        result = await connection.client.query(query)

        if not result or not result[0]:
            return []

        # Process results based on query type
        if target_document:
            # Return list of related document instances
            return [target_document.from_db(doc) for doc in result[0]]
        else:
            # Return raw path results
            return result[0]

    def traverse_path_sync(self, path_spec: str, target_document: Optional[Type] = None,
                           connection: Optional[Any] = None, **filters: Any) -> List[Any]:
        """Traverse a path in the graph synchronously.

        This method traverses a path in the graph starting from this document.
        The path_spec is a string like "->[watched]->->[acted_in]->" which describes
        a path through the graph.

        Args:
            path_spec: String describing the path to traverse
            target_document: The document class to return instances of (optional)
            connection: The database connection to use (optional)
            **filters: Filters to apply to the results

        Returns:
            List of documents or path results

        Raises:
            ValueError: If the document is not saved
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        if not self.id:
            raise ValueError(f"Cannot traverse from unsaved {self.__class__.__name__}")

        start_id = f"{self.__class__._get_collection_name()}:{self.id}"

        if target_document:
            end_collection = target_document._get_collection_name()
            query = f"SELECT * FROM {end_collection} WHERE {path_spec}{start_id}"
        else:
            query = f"SELECT {path_spec} as path FROM {start_id}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                from .surrealql import escape_literal
                conditions.append(f"{field} = {escape_literal(value)}")

            if target_document:
                query += f" AND {' AND '.join(conditions)}"
            else:
                query += f" WHERE {' AND '.join(conditions)}"

        result = connection.client.query(query)

        if not result or not result[0]:
            return []

        # Process results based on query type
        if target_document:
            # Return list of related document instances
            return [target_document.from_db(doc) for doc in result[0]]
        else:
            # Return raw path results
            return result[0]

    @classmethod
    async def bulk_create(self, documents: List[Any], batch_size: int = 1000,
                          validate: bool = True, return_documents: bool = True, connection: Optional[Any] = None) -> \
            Union[List[Any], int]:
        """Create multiple documents in batches.

        Args:
            documents: List of documents to create
            batch_size: Number of documents per batch
            validate: Whether to validate documents before creation
            return_documents: Whether to return created documents

        Returns:
            List of created documents if return_documents=True, else count of created documents
        """
        results = []
        total_count = 0

        # Process documents in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            if validate:
                # Perform validation without using asyncio.gather since validate is not async
                for doc in batch:
                    doc.validate()

            # Convert batch to DB representation
            data = [doc.to_db() for doc in batch]

            # Create the documents in the database
            collection = batch[0]._get_collection_name()
            if connection is None:
                connection = ConnectionRegistry.get_default_connection()
            created = await connection.client.insert(collection, data)

            if created:
                if return_documents:
                    # Convert created records back to documents
                    for record in created:
                        doc = self.from_db(record)
                        results.append(doc)
                total_count += len(created)

        return results if return_documents else total_count

    @classmethod
    def bulk_create_sync(cls, documents: List[Any], batch_size: int = 1000,
                         validate: bool = True, return_documents: bool = True,
                         connection: Optional[Any] = None) -> Union[List[Any], int]:
        """Create multiple documents in a single operation synchronously.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance. It can optionally validate the
        documents and return the created documents.

        Args:
            documents: List of Document instances to create
            batch_size: Number of documents per batch (default: 1000)
            validate: Whether to validate documents (default: True)
            return_documents: Whether to return created documents (default: True)
            connection: The database connection to use (optional)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        # Trigger pre_bulk_insert signal
        if SIGNAL_SUPPORT:
            pre_bulk_insert.send(cls, documents=documents)

        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        result = cls.objects(connection).bulk_create_sync(
            documents,
            batch_size=batch_size,
            validate=validate,
            return_documents=return_documents
        )

        # Trigger post_bulk_insert signal
        if SIGNAL_SUPPORT:
            post_bulk_insert.send(cls, documents=documents, loaded=return_documents)

        return result

    @classmethod
    async def create_index(cls, index_name: str, fields: List[str], unique: bool = False,
                           search: bool = False, analyzer: Optional[str] = None,
                           comment: Optional[str] = None, connection: Optional[Any] = None) -> None:
        """Create an index on the document's collection asynchronously.

        Args:
            index_name: Name of the index
            fields: List of field names to include in the index
            unique: Whether the index should enforce uniqueness
            search: Whether the index is a search index
            analyzer: Analyzer to use for search indexes
            comment: Optional comment for the index
            connection: Optional connection to use
        """
        if connection is None:
            from .connection import ConnectionRegistry
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        collection_name = cls._get_collection_name()
        fields_str = ", ".join(fields)

        # Build the index definition
        query = f"DEFINE INDEX {index_name} ON {collection_name} FIELDS {fields_str}"

        # Add index type
        if unique:
            query += " UNIQUE"
        elif search and analyzer:
            query += f" SEARCH ANALYZER {analyzer}"

        # Add comment if provided
        if comment:
            query += f" COMMENT '{comment}'"

        # Execute the query
        await connection.client.query(query)

    @classmethod
    def create_index_sync(cls, index_name: str, fields: List[str], unique: bool = False,
                          search: bool = False, analyzer: Optional[str] = None,
                          comment: Optional[str] = None, connection: Optional[Any] = None) -> None:
        """Create an index on the document's collection synchronously.

        Args:
            index_name: Name of the index
            fields: List of field names to include in the index
            unique: Whether the index should enforce uniqueness
            search: Whether the index is a search index
            analyzer: Analyzer to use for search indexes
            comment: Optional comment for the index
            connection: Optional connection to use
        """
        if connection is None:
            from .connection import ConnectionRegistry
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        collection_name = cls._get_collection_name()
        fields_str = ", ".join(fields)

        # Build the index definition
        query = f"DEFINE INDEX {index_name} ON {collection_name} FIELDS {fields_str}"

        # Add index type
        if unique:
            query += " UNIQUE"
        elif search and analyzer:
            query += f" SEARCH ANALYZER {analyzer}"

        # Add comment if provided
        if comment:
            query += f" COMMENT '{comment}'"

        # Execute the query
        connection.client.query(query)

    @classmethod
    async def create_indexes(cls, connection: Optional[Any] = None) -> None:
        """Create all indexes defined for this document class asynchronously.

        This method creates indexes defined in the Meta class and also creates
        indexes for fields marked as indexed.

        Args:
            connection: Optional connection to use
        """
        connection = connection or ConnectionRegistry.get_default_connection(async_mode=True)

        # Track processed multi-field indexes to avoid duplicates
        processed_multi_field_indexes = set()

        # Create indexes defined in Meta.indexes
        if hasattr(cls, '_meta') and 'indexes' in cls._meta and cls._meta['indexes']:
            for index_def in cls._meta['indexes']:
                # Handle different index definition formats
                if isinstance(index_def, dict):
                    # Dictionary format with options
                    index_name = index_def.get('name')
                    fields = index_def.get('fields', [])
                    unique = index_def.get('unique', False)
                    search = index_def.get('search', False)
                    analyzer = index_def.get('analyzer')
                    comment = index_def.get('comment')
                elif isinstance(index_def, tuple) and len(index_def) >= 2:
                    # Tuple format (name, fields, [unique])
                    index_name = index_def[0]
                    fields = index_def[1] if isinstance(index_def[1], list) else [index_def[1]]
                    unique = index_def[2] if len(index_def) > 2 else False
                    search = False
                    analyzer = None
                    comment = None
                else:
                    # Skip invalid index definitions
                    continue

                await cls.create_index(
                    index_name=index_name,
                    fields=fields,
                    unique=unique,
                    search=search,
                    analyzer=analyzer,
                    comment=comment,
                    connection=connection
                )

                # Mark this index as processed to avoid duplicates
                if fields:
                    processed_multi_field_indexes.add(tuple(sorted(fields)))

        # Create indexes for fields marked as indexed
        for field_name, field_obj in cls._fields.items():
            if getattr(field_obj, 'indexed', False):
                db_field_name = field_obj.db_field or field_name

                # Check if this is a multi-field index
                index_with = getattr(field_obj, 'index_with', None)
                if index_with and isinstance(index_with, list) and len(index_with) > 0:
                    # Get the actual field names for the index_with fields
                    index_with_fields = []
                    for with_field_name in index_with:
                        if with_field_name in cls._fields:
                            with_field_obj = cls._fields[with_field_name]
                            with_db_field_name = with_field_obj.db_field or with_field_name
                            index_with_fields.append(with_db_field_name)
                        else:
                            # If the field doesn't exist, use the name as is
                            index_with_fields.append(with_field_name)

                    # Generate a unique identifier for this multi-field index
                    # Sort fields to ensure consistent ordering
                    all_fields = sorted([db_field_name] + index_with_fields)
                    index_key = tuple(all_fields)

                    # Skip if we've already processed this combination
                    if index_key in processed_multi_field_indexes:
                        continue

                    # Mark this combination as processed
                    processed_multi_field_indexes.add(index_key)

                    # Generate a default index name
                    index_name = f"{cls._get_collection_name()}_{'_'.join(all_fields)}_idx"

                    # Get index options
                    unique = getattr(field_obj, 'unique', False)
                    search = getattr(field_obj, 'search', False)
                    analyzer = getattr(field_obj, 'analyzer', None)

                    # Create the multi-field index
                    await cls.create_index(
                        index_name=index_name,
                        fields=all_fields,
                        unique=unique,
                        search=search,
                        analyzer=analyzer,
                        connection=connection
                    )
                else:
                    # Create a single-field index
                    # Skip if we've already processed this field
                    if (db_field_name,) in processed_multi_field_indexes:
                        continue

                    # Mark this field as processed
                    processed_multi_field_indexes.add((db_field_name,))

                    # Generate a default index name
                    index_name = f"{cls._get_collection_name()}_{field_name}_idx"

                    # Get index options
                    unique = getattr(field_obj, 'unique', False)
                    search = getattr(field_obj, 'search', False)
                    analyzer = getattr(field_obj, 'analyzer', None)

                    # Create the single-field index
                    await cls.create_index(
                        index_name=index_name,
                        fields=[db_field_name],
                        unique=unique,
                        search=search,
                        analyzer=analyzer,
                        connection=connection
                    )

    @classmethod
    def create_indexes_sync(cls, connection: Optional[Any] = None) -> None:
        """Create all indexes defined for this document class synchronously.

        This method creates indexes defined in the Meta class and also creates
        indexes for fields marked as indexed.

        Args:
            connection: Optional connection to use
        """
        connection = connection or ConnectionRegistry.get_default_connection(async_mode=False)

        # Track processed multi-field indexes to avoid duplicates
        processed_multi_field_indexes = set()

        # Create indexes defined in Meta.indexes
        if hasattr(cls, '_meta') and 'indexes' in cls._meta and cls._meta['indexes']:
            for index_def in cls._meta['indexes']:
                # Handle different index definition formats
                if isinstance(index_def, dict):
                    # Dictionary format with options
                    index_name = index_def.get('name')
                    fields = index_def.get('fields', [])
                    unique = index_def.get('unique', False)
                    search = index_def.get('search', False)
                    analyzer = index_def.get('analyzer')
                    comment = index_def.get('comment')
                elif isinstance(index_def, tuple) and len(index_def) >= 2:
                    # Tuple format (name, fields, [unique])
                    index_name = index_def[0]
                    fields = index_def[1] if isinstance(index_def[1], list) else [index_def[1]]
                    unique = index_def[2] if len(index_def) > 2 else False
                    search = False
                    analyzer = None
                    comment = None
                else:
                    # Skip invalid index definitions
                    continue

                cls.create_index_sync(
                    index_name=index_name,
                    fields=fields,
                    unique=unique,
                    search=search,
                    analyzer=analyzer,
                    comment=comment,
                    connection=connection
                )

                # Mark this index as processed to avoid duplicates
                if fields:
                    processed_multi_field_indexes.add(tuple(sorted(fields)))

        # Create indexes for fields marked as indexed
        for field_name, field_obj in cls._fields.items():
            if getattr(field_obj, 'indexed', False):
                db_field_name = field_obj.db_field or field_name

                # Check if this is a multi-field index
                index_with = getattr(field_obj, 'index_with', None)
                if index_with and isinstance(index_with, list) and len(index_with) > 0:
                    # Get the actual field names for the index_with fields
                    index_with_fields = []
                    for with_field_name in index_with:
                        if with_field_name in cls._fields:
                            with_field_obj = cls._fields[with_field_name]
                            with_db_field_name = with_field_obj.db_field or with_field_name
                            index_with_fields.append(with_db_field_name)
                        else:
                            # If the field doesn't exist, use the name as is
                            index_with_fields.append(with_field_name)

                    # Generate a unique identifier for this multi-field index
                    # Sort fields to ensure consistent ordering
                    all_fields = sorted([db_field_name] + index_with_fields)
                    index_key = tuple(all_fields)

                    # Skip if we've already processed this combination
                    if index_key in processed_multi_field_indexes:
                        continue

                    # Mark this combination as processed
                    processed_multi_field_indexes.add(index_key)

                    # Generate a default index name
                    index_name = f"{cls._get_collection_name()}_{'_'.join(all_fields)}_idx"

                    # Get index options
                    unique = getattr(field_obj, 'unique', False)
                    search = getattr(field_obj, 'search', False)
                    analyzer = getattr(field_obj, 'analyzer', None)

                    # Create the multi-field index
                    cls.create_index_sync(
                        index_name=index_name,
                        fields=all_fields,
                        unique=unique,
                        search=search,
                        analyzer=analyzer,
                        connection=connection
                    )
                else:
                    # Create a single-field index
                    # Skip if we've already processed this field
                    if (db_field_name,) in processed_multi_field_indexes:
                        continue

                    # Mark this field as processed
                    processed_multi_field_indexes.add((db_field_name,))

                    # Generate a default index name
                    index_name = f"{cls._get_collection_name()}_{field_name}_idx"

                    # Get index options
                    unique = getattr(field_obj, 'unique', False)
                    search = getattr(field_obj, 'search', False)
                    analyzer = getattr(field_obj, 'analyzer', None)

                    # Create the single-field index
                    cls.create_index_sync(
                        index_name=index_name,
                        fields=[db_field_name],
                        unique=unique,
                        search=search,
                        analyzer=analyzer,
                        connection=connection
                    )

    @classmethod
    def _get_field_type_for_surreal(cls, field: Field) -> str:
        """Get the SurrealDB type for a field.

        Args:
            field: The field to get the type for

        Returns:
            The SurrealDB type as a string
        """
        from .fields import (
            StringField, IntField, FloatField, BooleanField,
            DateTimeField, ListField, DictField, ReferenceField,
            GeometryField, RelationField, DecimalField, DurationField,
            BytesField, RegexField, OptionField, FutureField,
            UUIDField, TableField, RecordIDField
        )

        if isinstance(field, StringField):
            return "string"
        elif isinstance(field, IntField):
            return "int"
        elif isinstance(field, FloatField) or isinstance(field, DecimalField):
            return "float"
        elif isinstance(field, BooleanField):
            return "bool"
        elif isinstance(field, DateTimeField):
            return "datetime"
        elif isinstance(field, DurationField):
            return "duration"
        elif isinstance(field, ListField):
            if field.field_type:
                inner_type = cls._get_field_type_for_surreal(field.field_type)
                return f"array<{inner_type}>"
            return "array"
        elif isinstance(field, DictField):
            return "object"
        elif isinstance(field, ReferenceField):
            # Get the target collection name
            target_cls = field.document_type
            target_collection = target_cls._get_collection_name()
            return f"record<{target_collection}>"
        elif isinstance(field, RelationField):
            # Get the target collection name
            target_cls = field.to_document
            target_collection = target_cls._get_collection_name()
            return f"record<{target_collection}>"
        elif isinstance(field, GeometryField):
            return "geometry"
        elif isinstance(field, BytesField):
            return "bytes"
        elif isinstance(field, RegexField):
            return "regex"
        elif isinstance(field, OptionField):
            if field.field_type:
                inner_type = cls._get_field_type_for_surreal(field.field_type)
                return f"option<{inner_type}>"
            return "option"
        elif isinstance(field, UUIDField):
            return "uuid"
        elif isinstance(field, TableField):
            return "table"
        elif isinstance(field, RecordIDField):
            return "record"
        elif isinstance(field, FutureField):
            return "any"  # Future fields are computed at query time

        # Default to any type if we can't determine a specific type
        return "any"

    @classmethod
    async def create_table(cls, connection: Optional[Any] = None, schemafull: bool = True) -> None:
        """Create the table for this document class asynchronously.

        Args:
            connection: Optional connection to use
            schemafull: Whether to create a SCHEMAFULL table (default: True)

        Examples:
            Create a SCHEMAFULL table:

            >>> await User.create_table()
            >>> print("Created users table with strict schema")

            Create a SCHEMALESS table:

            >>> await FlexibleDoc.create_table(schemafull=False)
            >>> print("Created flexible table without schema constraints")

            Create with custom connection:

            >>> await Person.create_table(connection=custom_connection)

            Create multiple tables:

            >>> await Person.create_table()
            >>> await Address.create_table()
            >>> await Organization.create_table()
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        collection_name = cls._get_collection_name()

        # Create the table
        schema_type = "SCHEMAFULL" if schemafull else "SCHEMALESS"
        query = f"DEFINE TABLE {collection_name} {schema_type}"

        # Check if this is a time series table
        is_time_series = False
        time_field = None

        # Check if the Meta class has time_series and time_field attributes
        if hasattr(cls, '_meta'):
            is_time_series = cls._meta.get('time_series', False)
            time_field = cls._meta.get('time_field')

        # If time_series is True but time_field is not specified, try to find a TimeSeriesField
        if is_time_series and not time_field:
            for field_name, field in cls._fields.items():
                if field.__class__.__name__ == 'TimeSeriesField':
                    time_field = field.db_field
                    break

        # Add time series configuration if applicable
        if is_time_series and time_field:
            query += f" TYPE TIMESTAMP TIMEFIELD {time_field}"

        # Add comment if available
        if hasattr(cls, '__doc__') and cls.__doc__:
            # Clean up docstring and escape single quotes
            doc = cls.__doc__.strip().replace("'", "''")
            if doc:
                query += f" COMMENT '{doc}'"

        await connection.client.query(query)

        # Create fields if schemafull or if field is marked with define_schema=True
        for field_name, field in cls._fields.items():
            # Skip id field as it's handled by SurrealDB
            if field_name == cls._meta.get('id_field', 'id'):
                continue

            # Only define fields if schemafull or if field is explicitly marked for schema definition
            if schemafull or field.define_schema:
                field_type = cls._get_field_type_for_surreal(field)
                field_query = f"DEFINE FIELD {field.db_field} ON {collection_name} TYPE {field_type}"

                # Build constraints
                exprs = []
                if field.required:
                    exprs.append("$value != NONE")
                try:
                    from .fields.scalar import StringField, NumberField
                    from .fields.specialized import ChoiceField
                except Exception:
                    StringField = NumberField = ChoiceField = None  # type: ignore

                # StringField constraints
                if StringField and isinstance(field, StringField):
                    if getattr(field, 'min_length', None) is not None:
                        exprs.append(f"string::len($value) >= {int(field.min_length)}")
                    if getattr(field, 'max_length', None) is not None:
                        exprs.append(f"string::len($value) <= {int(field.max_length)}")
                    if getattr(field, 'regex_pattern', None):
                        # Use string::matches for regex in v2; pattern as string literal
                        from .surrealql import escape_literal
                        pattern = field.regex_pattern
                        exprs.append(f"string::matches($value, {escape_literal(pattern)})")
                    if getattr(field, 'choices', None):
                        vals = []
                        for v in field.choices:
                            if isinstance(v, str):
                                s = v.replace('\\', r'\\').replace('"', r'\"')
                                vals.append(f'"{s}"')
                            else:
                                vals.append(str(v).lower() if isinstance(v, bool) else str(v))
                        exprs.append(f"$value INSIDE [{', '.join(vals)}]")

                # Number constraints (NumberField and subclasses)
                if NumberField and isinstance(field, NumberField):
                    if getattr(field, 'min_value', None) is not None:
                        exprs.append(f"$value >= {field.min_value}")
                    if getattr(field, 'max_value', None) is not None:
                        exprs.append(f"$value <= {field.max_value}")

                # ChoiceField constraints
                if ChoiceField and isinstance(field, ChoiceField):
                    vals = []
                    for v in field.values:
                        if isinstance(v, str):
                            s = v.replace('\\', r'\\').replace('"', r'\"')
                            vals.append(f'"{s}"')
                        else:
                            vals.append(str(v).lower() if isinstance(v, bool) else str(v))
                    exprs.append(f"$value INSIDE [{', '.join(vals)}]")

                if exprs:
                    field_query += " ASSERT " + " AND ".join(exprs)

                # Default value
                if field.default is not None and not callable(field.default):
                    def _literal(val):
                        if isinstance(val, str):
                            s = val.replace('\\', r'\\').replace('"', r'\"')
                            return f'"{s}"'
                        if isinstance(val, bool):
                            return 'true' if val else 'false'
                        return str(val)
                    field_query += f" DEFAULT {_literal(field.default)}"

                # Field comment
                if getattr(field, 'comment', None):
                    c = field.comment.replace('\\', r'\\').replace('"', r'\"')
                    # SurrealQL docs: field COMMENT supports string literal; we use double quotes safely
                    field_query += f" COMMENT \"{c}\""

                await connection.client.query(field_query)

                # Handle nested fields for DictField
                if isinstance(field, DictField) and schemafull:
                    if field.db_field == 'settings':
                        nested_field_query = f"DEFINE FIELD {field.db_field}.theme ON {collection_name} TYPE string"
                        await connection.client.query(nested_field_query)

    @classmethod
    def create_table_sync(cls, connection: Optional[Any] = None, schemafull: bool = True) -> None:
        """Create the table for this document class synchronously."""
        if connection is None:
            from .connection import ConnectionRegistry
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        collection_name = cls._get_collection_name()

        # Create the table
        schema_type = "SCHEMAFULL" if schemafull else "SCHEMALESS"
        query = f"DEFINE TABLE {collection_name} {schema_type}"

        # Check if this is a time series table
        is_time_series = False
        time_field = None

        # Check if the Meta class has time_series and time_field attributes
        if hasattr(cls, '_meta'):
            is_time_series = cls._meta.get('time_series', False)
            time_field = cls._meta.get('time_field')

        # If time_series is True but time_field is not specified, try to find a TimeSeriesField
        if is_time_series and not time_field:
            for field_name, field in cls._fields.items():
                if field.__class__.__name__ == 'TimeSeriesField':
                    time_field = field.db_field
                    break

        # Add time series configuration if applicable
        if is_time_series and time_field:
            query += f" TYPE TIMESTAMP TIMEFIELD {time_field}"

        # Add comment if available
        if hasattr(cls, '__doc__') and cls.__doc__:
            # Clean up docstring: remove newlines, extra spaces, and escape quotes
            doc = ' '.join(cls.__doc__.strip().split())
            doc = doc.replace("'", "''")
            if doc:
                query += f" COMMENT '{doc}'"
        connection.client.query(query)

        # Create fields if schemafull or if field is marked with define_schema=True
        for field_name, field in cls._fields.items():
            # Skip id field as it's handled by SurrealDB
            if field_name == cls._meta.get('id_field', 'id'):
                continue

            # Only define fields if schemafull or if field is explicitly marked for schema definition
            if schemafull or field.define_schema:
                field_type = cls._get_field_type_for_surreal(field)
                field_query = f"DEFINE FIELD {field.db_field} ON {collection_name} TYPE {field_type}"

                # Build constraints
                exprs = []
                if field.required:
                    exprs.append("$value != NONE")
                try:
                    from .fields.scalar import StringField, NumberField
                    from .fields.specialized import ChoiceField
                except Exception:
                    StringField = NumberField = ChoiceField = None  # type: ignore

                # StringField constraints
                if StringField and isinstance(field, StringField):
                    if getattr(field, 'min_length', None) is not None:
                        exprs.append(f"string::len($value) >= {int(field.min_length)}")
                    if getattr(field, 'max_length', None) is not None:
                        exprs.append(f"string::len($value) <= {int(field.max_length)}")
                    if getattr(field, 'regex_pattern', None):
                        from .surrealql import escape_literal
                        pattern = field.regex_pattern
                        exprs.append(f"string::matches($value, {escape_literal(pattern)})")
                    if getattr(field, 'choices', None):
                        vals = []
                        for v in field.choices:
                            if isinstance(v, str):
                                s = v.replace('\\', r'\\').replace('"', r'\"')
                                vals.append(f'"{s}"')
                            else:
                                vals.append(str(v).lower() if isinstance(v, bool) else str(v))
                        exprs.append(f"$value INSIDE [{', '.join(vals)}]")

                # Number constraints (NumberField and subclasses)
                if NumberField and isinstance(field, NumberField):
                    if getattr(field, 'min_value', None) is not None:
                        exprs.append(f"$value >= {field.min_value}")
                    if getattr(field, 'max_value', None) is not None:
                        exprs.append(f"$value <= {field.max_value}")

                # ChoiceField constraints
                if ChoiceField and isinstance(field, ChoiceField):
                    vals = []
                    for v in field.values:
                        if isinstance(v, str):
                            s = v.replace('\\', r'\\').replace('"', r'\"')
                            vals.append(f'"{s}"')
                        else:
                            vals.append(str(v).lower() if isinstance(v, bool) else str(v))
                    exprs.append(f"$value INSIDE [{', '.join(vals)}]")

                if exprs:
                    field_query += " ASSERT " + " AND ".join(exprs)

                # Default value
                if field.default is not None and not callable(field.default):
                    def _literal(val):
                        if isinstance(val, str):
                            s = val.replace('\\', r'\\').replace('"', r'\"')
                            return f'"{s}"'
                        if isinstance(val, bool):
                            return 'true' if val else 'false'
                        return str(val)
                    field_query += f" DEFAULT {_literal(field.default)}"

                # Field comment
                if getattr(field, 'comment', None):
                    c = field.comment.replace('\\', r'\\').replace('"', r'\"')
                    field_query += f" COMMENT \"{c}\""

                connection.client.query(field_query)

                # Handle nested fields for DictField
                if isinstance(field, DictField) and schemafull:
                    if field.db_field == 'settings':
                        nested_field_query = f"DEFINE FIELD {field.db_field}.theme ON {collection_name} TYPE string"
                        connection.client.query(nested_field_query)

    @classmethod
    def to_dataclass(cls):
        """Convert the document class to a dataclass.

        This method creates a dataclass based on the document's fields.
        It uses the field names, types, and whether they are required.
        Required fields have no default value, making them required during initialization.
        Non-required fields use None as default if they don't define one.
        A __post_init__ method is added to validate all fields after initialization.

        Returns:
            A dataclass type based on the document's fields
        """
        fields = [('id', Optional[str], dataclass_field(default=None))]
        # Process fields
        for field_name, field_obj in cls._fields.items():
            # Skip id field as it's handled separately
            if field_name == cls._meta.get('id_field', 'id'):
                continue
            # For required fields, don't provide a default value
            if field_obj.required:
                fields.insert(0, (field_name, field_obj.py_type))
            # For fields with a non-callable default, use that default
            elif field_obj.default is not None and not callable(field_obj.default):
                fields.append((field_name, field_obj.py_type, dataclass_field(default=field_obj.default)))
            # For other fields, use None as default
            else:
                fields.append((field_name, field_obj.py_type, dataclass_field(default=None)))

        # Define the __post_init__ method to validate fields
        def post_init(self):
            """Validate all fields after initialization."""
            for field_name, field_obj in cls._fields.items():
                value = getattr(self, field_name, None)
                field_obj.validate(value)

        # Create the dataclass using make_dataclass
        return make_dataclass(
            cls_name=f"{cls.__name__}_Dataclass",
            fields=fields,
            namespace={"__post_init__": post_init}
        )

    @classmethod
    def create_materialized_view(cls, name: str, query: QuerySet, refresh_interval: str = None, 
                                 aggregations=None, select_fields=None, **kwargs):
        """Create a materialized view based on a query.

        This method creates a materialized view in SurrealDB based on a query.
        Materialized views are precomputed views of data that can be used to
        improve query performance for frequently accessed aggregated data.

        Args:
            name: The name of the materialized view
            query: The query that defines the materialized view
            refresh_interval: The interval at which the view is refreshed (e.g., "1h", "30m")
            aggregations: Dictionary of field names and aggregation functions
            select_fields: List of fields to select (if None, selects all fields)
            **kwargs: Additional keyword arguments to pass to the MaterializedView constructor

        Returns:
            A MaterializedView instance
        """
        from .materialized_view import MaterializedView, Count, Mean, Sum, Min, Max, ArrayCollect

        # Process aggregations if provided as keyword arguments
        if aggregations is None:
            aggregations = {}

        # Check for aggregation functions in kwargs
        for key, value in kwargs.items():
            if key.startswith('count_'):
                field_name = key[6:]  # Remove 'count_' prefix
                aggregations[field_name] = Count()
            elif key.startswith('mean_'):
                field_name = key[5:]  # Remove 'mean_' prefix
                field = kwargs.get(key)
                aggregations[field_name] = Mean(field)
            elif key.startswith('sum_'):
                field_name = key[4:]  # Remove 'sum_' prefix
                field = kwargs.get(key)
                aggregations[field_name] = Sum(field)
            elif key.startswith('min_'):
                field_name = key[4:]  # Remove 'min_' prefix
                field = kwargs.get(key)
                aggregations[field_name] = Min(field)
            elif key.startswith('max_'):
                field_name = key[4:]  # Remove 'max_' prefix
                field = kwargs.get(key)
                aggregations[field_name] = Max(field)
            elif key.startswith('collect_'):
                field_name = key[8:]  # Remove 'collect_' prefix
                field = kwargs.get(key)
                aggregations[field_name] = ArrayCollect(field)

        return MaterializedView(name, query, refresh_interval, cls, aggregations, select_fields)

    @classmethod
    def _get_document_class_for_collection(cls, collection_name: str) -> Optional[Type['Document']]:
        """Get the document class for a collection name.

        This method looks up the document class for a given collection name
        in the document registry. If no class is found, it returns None.

        Args:
            collection_name: The name of the collection

        Returns:
            The document class for the collection, or None if not found
        """
        # Initialize the document registry if it doesn't exist
        if not hasattr(cls, '_document_registry'):
            cls._document_registry = {}

            # Populate the registry with all existing document classes
            def register_subclasses(doc_class):
                for subclass in doc_class.__subclasses__():
                    if hasattr(subclass, '_meta') and not subclass._meta.get('abstract', False):
                        collection = subclass._meta.get('collection')
                        if collection:
                            cls._document_registry[collection] = subclass
                    register_subclasses(subclass)

            # Start with Document subclasses
            register_subclasses(cls)

        # Handle RecordID objects
        if isinstance(collection_name, RecordID):
            collection_name = collection_name.table_name

        # Handle string IDs in the format "collection:id"
        elif isinstance(collection_name, str) and ':' in collection_name:
            collection_name = collection_name.split(':', 1)[0]

        # Look up the document class in the registry
        return cls._document_registry.get(collection_name)

class RelationDocument(Document):
    """A Document that represents a relationship between two documents.

    RelationDocuments should be used to model relationships with additional attributes.
    They can be used with Document.relates(), Document.fetch_relation(), and Document.resolve_relation().
    """

    class Meta:
        """Meta options for RelationDocument."""
        abstract = True

    in_document = ReferenceField(Document, required=True, db_field="in")
    out_document = ReferenceField(Document, required=True, db_field="out")

    @classmethod
    def get_relation_name(cls) -> str:
        """Get the name of the relation.

        By default, this is the lowercase name of the class.
        Override this method to customize the relation name.

        Returns:
            The name of the relation
        """
        return cls._meta.get('collection')

    @classmethod
    def relates(cls, from_document: Optional[Type] = None, to_document: Optional[Type] = None) -> callable:
        """Get a RelationQuerySet for this relation.

        This method returns a function that creates a RelationQuerySet for
        this relation. The function can be called with an optional connection parameter.

        Args:
            from_document: The document class the relation is from (optional)
            to_document: The document class the relation is to (optional)

        Returns:
            Function that creates a RelationQuerySet
        """
        relation_name = cls.get_relation_name()

        def relation_query_builder(connection: Optional[Any] = None) -> 'RelationQuerySet':
            """Create a RelationQuerySet for this relation.

            Args:
                connection: The database connection to use (optional)

            Returns:
                A RelationQuerySet for the relation
            """
            if connection is None:
                connection = ConnectionRegistry.get_default_connection()
            return RelationQuerySet(from_document or Document, connection, relation=relation_name)

        return relation_query_builder

    @classmethod
    async def create_relation(cls, from_instance: Any, to_instance: Any, **attrs: Any) -> 'RelationDocument':
        """Create a relation between two instances asynchronously.

        This method creates a relation between two document instances and
        returns a RelationDocument instance representing the relationship.

        Args:
            from_instance: The instance to create the relation from
            to_instance: The instance to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            A RelationDocument instance representing the relationship

        Raises:
            ValueError: If either instance is not saved
        """
        if not from_instance.id:
            raise ValueError(f"Cannot create relation from unsaved {from_instance.__class__.__name__}")

        if not to_instance.id:
            raise ValueError(f"Cannot create relation to unsaved {to_instance.__class__.__name__}")

        # Create the relation using Document.relate_to
        relation = await from_instance.relate_to(cls.get_relation_name(), to_instance, **attrs)

        # Create a RelationDocument instance from the relation data
        relation_doc = cls(
            in_document=from_instance,
            out_document=to_instance,
            **attrs
        )

        # Set the ID from the relation
        if relation and 'id' in relation:
            relation_doc.id = relation['id']

        return relation_doc

    @classmethod
    def create_relation_sync(cls, from_instance: Any, to_instance: Any, **attrs: Any) -> 'RelationDocument':
        """Create a relation between two instances synchronously.

        This method creates a relation between two document instances and
        returns a RelationDocument instance representing the relationship.

        Args:
            from_instance: The instance to create the relation from
            to_instance: The instance to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            A RelationDocument instance representing the relationship

        Raises:
            ValueError: If either instance is not saved
        """
        if not from_instance.id:
            raise ValueError(f"Cannot create relation from unsaved {from_instance.__class__.__name__}")

        if not to_instance.id:
            raise ValueError(f"Cannot create relation to unsaved {to_instance.__class__.__name__}")

        # Create the relation using Document.relate_to_sync
        relation = from_instance.relate_to_sync(cls.get_relation_name(), to_instance, **attrs)

        # Create a RelationDocument instance from the relation data
        relation_doc = cls(
            in_document=from_instance,
            out_document=to_instance,
            **attrs
        )

        # Set the ID from the relation
        if relation and 'id' in relation:
            relation_doc.id = relation['id']

        return relation_doc

    @classmethod
    def find_by_in_document(cls, in_doc, **additional_filters):
        """
        Query RelationDocument by in_document field.

        Args:
            in_doc: The document instance or ID to filter by
            **additional_filters: Additional filters to apply

        Returns:
            QuerySet filtered by in_document
        """
        # Get the default connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(cls, connection)

        # Apply the in_document filter and any additional filters
        filters = {'in': in_doc, **additional_filters}
        return queryset.filter(**filters)

    @classmethod
    def find_by_in_document_sync(cls, in_doc, **additional_filters):
        """
        Query RelationDocument by in_document field synchronously.

        Args:
            in_doc: The document instance or ID to filter by
            **additional_filters: Additional filters to apply

        Returns:
            QuerySet filtered by in_document
        """
        # Get the default connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(cls, connection)

        # Apply the in_document filter and any additional filters
        filters = {'in': in_doc, **additional_filters}
        return queryset.filter(**filters)

    @classmethod
    def find_by_in_documents(cls, in_docs, **additional_filters):
        """
        Query RelationDocument where the `in` reference is any of the provided records (async-ready queryset).

        Args:
            in_docs: Iterable of items; each item may be a Document instance, RecordID, 'table:id' string, or dict with 'id'.
            **additional_filters: Any additional filters to apply to the query.

        Returns:
            QuerySet filtered by in__in
        """
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(cls, connection)

        def _norm(v):
            if isinstance(v, Document):
                return v.id
            if isinstance(v, RecordID):
                return str(v)
            if isinstance(v, dict) and v.get('id'):
                return v['id']
            return v

        in_ids = [ _norm(v) for v in in_docs if v ]
        filters = { 'in__in': in_ids, **additional_filters }
        return queryset.filter(**filters)

    @classmethod
    def find_by_in_documents_sync(cls, in_docs, **additional_filters):
        """Synchronous version of find_by_in_documents.

        Args:
            in_docs: Iterable of items; each item may be a Document instance, RecordID, 'table:id' string, or dict with 'id'.
            **additional_filters: Any additional filters to apply to the query.

        Returns:
            QuerySet filtered by in__in
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(cls, connection)

        def _norm(v):
            if isinstance(v, Document):
                return v.id
            if isinstance(v, RecordID):
                return str(v)
            if isinstance(v, dict) and v.get('id'):
                return v['id']
            return v

        in_ids = [ _norm(v) for v in in_docs if v ]
        filters = { 'in__in': in_ids, **additional_filters }
        return queryset.filter(**filters)

    async def resolve_out(self, connection=None):
        """Resolve the out_document field asynchronously.

        This method resolves the out_document field if it's currently just an ID reference.
        If the out_document is already a document instance, it returns it directly.

        Args:
            connection: Database connection to use (optional)

        Returns:
            The resolved out_document instance
        """
        # If out_document is already a document instance, return it
        if isinstance(self.out_document, Document):
            return self.out_document

        # Get the connection if not provided
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        # If out_document is a string ID, fetch the document
        if isinstance(self.out_document, str) and ':' in self.out_document:
            try:
                # Fetch the document using the ID
                result = await connection.client.select(self.out_document)

                # Process the result
                if result:
                    if isinstance(result, list) and result:
                        doc = result[0]
                    else:
                        doc = result

                    return doc
            except Exception as e:
                logger.error(f"Error resolving out_document {self.out_document}: {str(e)}")

        elif isinstance(self.out_document, RecordID):
            try:
                result = await connection.client.select(self.out_document)
                if result:
                    if isinstance(result, list) and result:
                        doc = result[0]
                    else:
                        doc = result

                    return doc
            except Exception as e:
                logger.error(f"Error resolving out_document {self.out_document}: {str(e)}")

        # Return the current value if resolution failed
        return self.out_document

    def resolve_out_sync(self, connection=None):
        """Resolve the out_document field synchronously.

        This method resolves the out_document field if it's currently just an ID reference.
        If the out_document is already a document instance, it returns it directly.

        Args:
            connection: Database connection to use (optional)

        Returns:
            The resolved out_document instance
        """
        # If out_document is already a document instance, return it
        if isinstance(self.out_document, Document):
            return self.out_document

        # Get the connection if not provided
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        # If out_document is a string ID, fetch the document
        if isinstance(self.out_document, str) and ':' in self.out_document:
            try:
                # Fetch the document using the ID
                result = connection.client.select(self.out_document)

                # Process the result
                if result:
                    if isinstance(result, list) and result:
                        doc = result[0]
                    else:
                        doc = result

                    return doc
            except Exception as e:
                logger.error(f"Error resolving out_document {self.out_document}: {str(e)}")

        elif isinstance(self.out_document, RecordID):
            try:
                result = connection.client.select(self.out_document)
                if result:
                    if isinstance(result, list) and result:
                        doc = result[0]
                    else:
                        doc = result

                    return doc
            except Exception as e:
                logger.error(f"Error resolving out_document {self.out_document}: {str(e)}")

        # Return the current value if resolution failed
        return self.out_document
''