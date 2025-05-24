import json
import datetime
from dataclasses import dataclass, field as dataclass_field, make_dataclass
from typing import Any, Dict, List, Optional, Type, Union, ClassVar
from .query import QuerySet, RelationQuerySet, QuerySetDescriptor
from .fields import Field, RecordIDField, ReferenceField
from .connection import ConnectionRegistry, SurrealEngineAsyncConnection, SurrealEngineSyncConnection
from surrealdb import RecordID
from .signals import (
    pre_init, post_init, pre_save, pre_save_post_validation, post_save,
    pre_delete, post_delete, pre_bulk_insert, post_bulk_insert, SIGNAL_SUPPORT
)


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
        self._data['id'] = value

    @classmethod
    def _get_collection_name(cls) -> str:
        """Return the collection name for this document.

        Returns:
            The collection name
        """
        return cls._meta.get('collection')

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
        # Start with the ID if it exists
        result = {}
        if self.id is not None:
            # Convert RecordID to string if needed
            result['id'] = str(self.id) if isinstance(self.id, RecordID) else self.id

        # Add all other fields with proper conversion
        for k, v in self._data.items():
            if k in self._fields:
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
    def from_db(cls, data: Any) -> 'Document':
        """Create a document instance from database data.

        Args:
            data: Data from the database (dictionary, string, RecordID, etc.)

        Returns:
            A new document instance
        """
        # Create an empty instance without triggering signals
        instance = cls.__new__(cls)

        # Initialize _data and _changed_fields
        instance._data = {}
        instance._changed_fields = []

        # Add id field if not present
        if 'id' not in instance._fields:
            instance._fields['id'] = RecordIDField()

        # Set default values
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
                    instance._data[field_name] = field.from_db(data[db_field])

            # Then, handle fields without db_field mapping (for backward compatibility)
            for key, value in data.items():
                if key in instance._fields:
                    field = instance._fields[key]
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

        return instance

    async def save(self, connection: Optional[Any] = None) -> 'Document':
        """Save the document to the database asynchronously.

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
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        self.validate()
        data = self.to_db()

        # Trigger pre_save_post_validation signal
        if SIGNAL_SUPPORT:
            pre_save_post_validation.send(self.__class__, document=self)

        is_new = not self.id
        if self.id:
            # Update existing document
            result = await connection.client.update(
                f"{self.id}",
                data
            )
        else:
            # Create new document
            result = await connection.client.create(
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
            post_save.send(self.__class__, document=self, created=is_new)

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
        data = self.to_db()

        # Trigger pre_save_post_validation signal
        if SIGNAL_SUPPORT:
            pre_save_post_validation.send(self.__class__, document=self)

        is_new = not self.id
        if self.id:
            # Update existing document
            result = connection.client.update(
                self.id,
                data
            )
        else:
            # Create new document
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
            post_save.send(self.__class__, document=self, created=is_new)

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
                        print(f"Error resolving document {collection}:{record_id}: {str(e)}")

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
                        print(f"Error resolving document {collection}:{record_id}: {str(e)}")

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
                conditions.append(f"{field} = {json.dumps(value)}")

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
                conditions.append(f"{field} = {json.dumps(value)}")

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
            print(connection)

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
        """Create all indexes defined in the Meta class asynchronously.

        Args:
            connection: Optional connection to use
        """
        if not hasattr(cls, '_meta') or 'indexes' not in cls._meta or not cls._meta['indexes']:
            return

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

    @classmethod
    def create_indexes_sync(cls, connection: Optional[Any] = None) -> None:
        """Create all indexes defined in the Meta class synchronously.

        Args:
            connection: Optional connection to use
        """
        if not hasattr(cls, '_meta') or 'indexes' not in cls._meta or not cls._meta['indexes']:
            return

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
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        collection_name = cls._get_collection_name()

        # Create the table
        schema_type = "SCHEMAFULL" if schemafull else "SCHEMALESS"
        query = f"DEFINE TABLE {collection_name} {schema_type}"

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

                # Add constraints
                if field.required:
                    field_query += " ASSERT $value != NONE"

                # Add comment if available
                if hasattr(field, '__doc__') and field.__doc__:
                    # Clean up docstring and escape single quotes
                    doc = field.__doc__.strip().replace("'", "''")
                    if doc:
                        field_query += f" COMMENT '{doc}'"

                await connection.client.query(field_query)

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

        # Add comment if available
        if hasattr(cls, '__doc__') and cls.__doc__:
            # Clean up docstring: remove newlines, extra spaces, and escape quotes
            doc = ' '.join(cls.__doc__.strip().split())
            doc = doc.replace("'", "''")
            if doc:
                query += f" COMMENT '{doc}'"
        try:
            connection.client.query(query)
        except Exception as e:
            print(query)
            raise e

        # Create fields if schemafull or if field is marked with define_schema=True
        for field_name, field in cls._fields.items():
            # Skip id field as it's handled by SurrealDB
            if field_name == cls._meta.get('id_field', 'id'):
                continue

            # Only define fields if schemafull or if field is explicitly marked for schema definition
            if schemafull or field.define_schema:
                field_type = cls._get_field_type_for_surreal(field)
                field_query = f"DEFINE FIELD {field.db_field} ON {collection_name} TYPE {field_type}"

                # Add constraints
                if field.required:
                    field_query += " ASSERT $value != NONE"

                # Add comment if available
                if hasattr(field, '__doc__') and field.__doc__:
                    # Clean up docstring: remove newlines, extra spaces, and escape quotes
                    doc = ' '.join(field.__doc__.strip().split())
                    doc = doc.replace("'", "''")
                    if doc:
                        field_query += f" COMMENT '{doc}'"

                try:
                    connection.client.query(field_query)
                except Exception as e:
                    print(field_query)
                    raise e

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
            print(field_name, field_obj.py_type)
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

                    # Create a document instance from the result
                    # We need to determine the document class from the ID
                    collection = self.out_document.split(':')[0]
                    # This assumes there's a way to get document class from collection name
                    # You might need to adjust this based on your actual implementation
                    doc_class = Document._get_document_class_for_collection(collection)

                    if doc_class:
                        # Create and set the document instance
                        self.out_document = doc_class.from_db(doc)
                        return self.out_document
            except Exception as e:
                print(f"Error resolving out_document {self.out_document}: {str(e)}")

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

                    # Create a document instance from the result
                    # We need to determine the document class from the ID
                    collection = self.out_document.split(':')[0]
                    # This assumes there's a way to get document class from collection name
                    # You might need to adjust this based on your actual implementation
                    doc_class = Document._get_document_class_for_collection(collection)

                    if doc_class:
                        # Create and set the document instance
                        self.out_document = doc_class.from_db(doc)
                        return self.out_document
            except Exception as e:
                print(f"Error resolving out_document {self.out_document}: {str(e)}")

        # Return the current value if resolution failed
        return self.out_document