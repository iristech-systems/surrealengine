import json
from .query import QuerySet, RelationQuerySet, QuerySetDescriptor
from .fields import Field
from .connection import ConnectionRegistry
from surrealdb import RecordID


class DocumentMetaclass(type):
    """Metaclass for Document classes."""

    def __new__(mcs, name, bases, attrs):
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
        fields = {}
        fields_ordered = []

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
    """Base class for all documents."""
    objects = QuerySetDescriptor()

    def __init__(self, **values):
        self._data = {}
        self._changed_fields = []

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

    def __getattr__(self, name):
        if name in self._fields:
            # Return the value directly from _data instead of the field instance
            return self._data.get(name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
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
    def id(self):
        """Get the document ID."""
        return self._data.get('id')

    @id.setter
    def id(self, value):
        """Set the document ID."""
        self._data['id'] = value

    @classmethod
    def _get_collection_name(cls):
        """Return the collection name for this document."""
        return cls._meta.get('collection')

    def validate(self):
        """Validate all fields."""
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            field.validate(value)

    def to_dict(self):
        """Convert the document to a dictionary."""
        return {k: v for k, v in self._data.items() if k in self._fields}

    def to_db(self):
        """Convert the document to a database-friendly dictionary."""
        result = {}
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            if value is not None or field.required:
                db_field = field.db_field or field_name
                result[db_field] = field.to_db(value)
        return result

    @classmethod
    def from_db(cls, data):
        """Create instance from database data."""
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

    async def save(self, connection=None):
        """Save the document to the database."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()

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

    async def delete(self, connection=None):
        """Delete the document from the database."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
        if not self.id:
            raise ValueError("Cannot delete a document without an ID")

        await connection.client.delete(f"{self._get_collection_name()}:{self.id}")
        return True

    async def refresh(self, connection=None):
        """Refresh the document from the database."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
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

    @classmethod
    def relates(cls, relation_name):
        """Get a RelationQuerySet for a specific relation."""

        def relation_query_builder(connection=None):
            if connection is None:
                connection = ConnectionRegistry.get_default_connection()
            return RelationQuerySet(cls, connection, relation=relation_name)

        return relation_query_builder

    async def fetch_relation(self, relation_name, target_document=None, connection=None, **filters):
        """Fetch related documents."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.get_related(self, target_document, **filters)

    async def resolve_relation(self, relation_name, target_document_class=None, connection=None):
        """
        Resolve related documents from a relation fetch result.

        Args:
            relation_name: Name of the relation to resolve
            target_document_class: Class of the target document (optional)
            connection: Database connection to use (optional)

        Returns:
            List of resolved document instances
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()

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

    async def relate_to(self, relation_name, target_instance, connection=None, **attrs):
        """Create a relation to another document."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.relate(self, target_instance, **attrs)

    async def update_relation_to(self, relation_name, target_instance, connection=None, **attrs):
        """Update a relation to another document."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.update_relation(self, target_instance, **attrs)

    async def delete_relation_to(self, relation_name, target_instance=None, connection=None):
        """Delete a relation to another document."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
        relation_query = RelationQuerySet(self.__class__, connection, relation=relation_name)
        return await relation_query.delete_relation(self, target_instance)

    async def traverse_path(self, path_spec, target_document=None, connection=None, **filters):
        """
        Traverse a path in the graph.

        path_spec is a string like "->[watched]->->[acted_in]->" which describes
        a path through the graph.
        """
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
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

    @classmethod
    async def bulk_create(cls, documents, connection=None, batch_size=1000,
                          validate=True, return_documents=True):
        """Create multiple documents in a single operation."""
        if connection is None:
            connection = ConnectionRegistry.get_default_connection()
        return await cls.objects(connection).bulk_create(
            documents,
            batch_size=batch_size,
            validate=validate,
            return_documents=return_documents
        )

