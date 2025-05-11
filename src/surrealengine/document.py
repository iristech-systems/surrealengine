import json
from typing import Any, Dict, List, Optional, Type, Union, ClassVar
from .query import QuerySet, RelationQuerySet, QuerySetDescriptor
from .fields import Field
from .connection import ConnectionRegistry, SurrealEngineAsyncConnection, SurrealEngineSyncConnection
from surrealdb import RecordID


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

    def __init__(self, **values: Any) -> None:
        """Initialize a new Document.

        Args:
            **values: Field values to set on the document

        Raises:
            AttributeError: If strict mode is enabled and an unknown field is provided
        """
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
        field values including the document ID.

        Returns:
            Dictionary of field values including ID
        """
        # Start with the ID if it exists
        result = {}
        if self.id is not None:
            result['id'] = self.id

        # Add all other fields
        result.update({k: v for k, v in self._data.items() if k in self._fields})
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
        """Create instance from database data.

        This method creates a new document instance from data retrieved
        from the database. It handles conversion of RecordID objects to
        strings.

        Args:
            data: Data from the database

        Returns:
            A new document instance
        """
        instance = cls()

        # Convert RecordID to string if needed
        if isinstance(data, dict):
            processed_data = {}
            for key, value in data.items():
                if isinstance(value, RecordID):
                    processed_data[key] = str(value)
                else:
                    processed_data[key] = value
            instance._data = processed_data
        else:
            print(f"Warning: Expected dict, got {type(data)}: {data}")
            instance._data = {}

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
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        self.validate()
        data = self.to_db()

        if self.id:
            # Update existing document
            result = await connection.client.update(
                f"{self._get_collection_name()}:{self.id}",
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
                self._data.update(doc_data)
                # Make sure to capture the ID if it's a new document
                if 'id' in doc_data:
                    self._data['id'] = doc_data['id']

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
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        self.validate()
        data = self.to_db()

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
                self._data.update(doc_data)
                # Make sure to capture the ID if it's a new document
                if 'id' in doc_data:
                    self._data['id'] = doc_data['id']

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
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        if not self.id:
            raise ValueError("Cannot delete a document without an ID")

        await connection.client.delete(f"{self._get_collection_name()}:{self.id}")
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
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        if not self.id:
            raise ValueError("Cannot delete a document without an ID")

        connection.client.delete(f"{self._get_collection_name()}:{self.id}")
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

        result = await connection.client.select(f"{self._get_collection_name()}:{self.id}")
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

        result = connection.client.select(f"{self._get_collection_name()}:{self.id}")
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
                            connection: Optional[Any] = None, **filters: Any) -> List[Any]:
        """Fetch related documents asynchronously.

        This method fetches documents related to this document through
        the specified relation.

        Args:
            relation_name: Name of the relation
            target_document: The document class of the target documents (optional)
            connection: The database connection to use (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents or relation records
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.get_related(self, target_document, **filters)

    def fetch_relation_sync(self, relation_name: str, target_document: Optional[Type] = None, 
                          connection: Optional[Any] = None, **filters: Any) -> List[Any]:
        """Fetch related documents synchronously.

        This method fetches documents related to this document through
        the specified relation.

        Args:
            relation_name: Name of the relation
            target_document: The document class of the target documents (optional)
            connection: The database connection to use (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents or relation records
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return relation_query.get_related_sync(self, target_document, **filters)

    async def resolve_relation(self, relation_name: str, target_document_class: Optional[Type] = None, 
                                 connection: Optional[Any] = None) -> List[Any]:
        """Resolve related documents from a relation fetch result asynchronously.

        This method resolves related documents from a relation fetch result.
        It fetches the relation data and then resolves each related document.

        Args:
            relation_name: Name of the relation to resolve
            target_document_class: Class of the target document (optional)
            connection: Database connection to use (optional)

        Returns:
            List of resolved document instances
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)

        # First fetch the relation data
        relation_data = await self.fetch_relation(relation_name)
        if not relation_data:
            return []

        resolved_documents = []
        if isinstance(relation_data, dict) and 'related' in relation_data and isinstance(relation_data['related'], list):
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
                             connection: Optional[Any] = None) -> List[Any]:
        """Resolve related documents from a relation fetch result synchronously.

        This method resolves related documents from a relation fetch result.
        It fetches the relation data and then resolves each related document.

        Args:
            relation_name: Name of the relation to resolve
            target_document_class: Class of the target document (optional)
            connection: Database connection to use (optional)

        Returns:
            List of resolved document instances
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)

        # First fetch the relation data
        relation_data = self.fetch_relation_sync(relation_name)
        if not relation_data:
            return []

        resolved_documents = []
        if isinstance(relation_data, dict) and 'related' in relation_data and isinstance(relation_data['related'], list):
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
    async def bulk_create(cls, documents: List[Any], batch_size: int = 1000,
                          validate: bool = True, return_documents: bool = True,
                          connection: Optional[Any] = None) -> Union[List[Any], int]:
        """Create multiple documents in a single operation asynchronously.

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
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=True)
        return await cls.objects(connection).bulk_create(
            documents,
            batch_size=batch_size,
            validate=validate,
            return_documents=return_documents
        )

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
        if connection is None:
            connection = ConnectionRegistry.get_default_connection(async_mode=False)
        return cls.objects(connection).bulk_create_sync(
            documents,
            batch_size=batch_size,
            validate=validate,
            return_documents=return_documents
        )

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
