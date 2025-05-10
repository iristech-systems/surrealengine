
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast
from .exceptions import MultipleObjectsReturned, DoesNotExist
from .connection import ConnectionRegistry
from surrealdb import RecordID
from .base_query import BaseQuerySet

class QuerySet(BaseQuerySet):
    """Query builder for SurrealDB.

    This class provides a query builder for document classes with a predefined schema.
    It extends BaseQuerySet to provide methods for querying and manipulating
    documents of a specific document class.

    Attributes:
        document_class: The document class to query
        connection: The database connection to use for queries
    """

    def __init__(self, document_class: Type, connection: Any) -> None:
        """Initialize a new QuerySet.

        Args:
            document_class: The document class to query
            connection: The database connection to use for queries
        """
        super().__init__(connection)
        self.document_class = document_class

    def _build_query(self) -> str:
        """Build the query string.

        This method builds the query string for the document class query.
        It adds conditions from query_parts if any are present.

        Returns:
            The query string
        """
        query = f"SELECT * FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            query += f" WHERE {' AND '.join(conditions)}"
        return query

    async def all(self) -> List[Any]:
        """Execute the query and return all results.

        This method builds and executes the query, then converts the results
        to instances of the document class.

        Returns:
            List of document instances
        """
        query = self._build_query()
        results = await self.connection.client.query(query)

        if not results or not results[0]:
            return []

        # Create one instance per result document
        processed_results = [self.document_class.from_db(doc) for doc in results]
        return processed_results

    async def count(self) -> int:
        """Count documents matching the query.

        This method builds and executes a count query to count the number
        of documents matching the query.

        Returns:
            Number of matching documents
        """
        count_query = f"SELECT count() FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            count_query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(count_query)

        if not result or not result[0]:
            return 0

        return result[0][0]['count']

    async def get(self, **kwargs: Any) -> Any:
        """Get a single document matching the query.

        This method applies filters and ensures that exactly one document is returned.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        self.filter(**kwargs)
        self.limit_value = 2  # Get 2 to check for multiple
        results = await self.all()

        if not results:
            raise DoesNotExist(f"{self.document_class.__name__} matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned(f"Multiple {self.document_class.__name__} objects returned instead of one")

        return results[0]

    async def create(self, **kwargs: Any) -> Any:
        """Create a new document.

        This method creates a new document with the given field values.

        Args:
            **kwargs: Field names and values for the new document

        Returns:
            The created document
        """
        document = self.document_class(**kwargs)
        return await document.save(self.connection)

    async def update(self, **kwargs: Any) -> List[Any]:
        """Update documents matching the query.

        This method updates documents matching the query with the given field values.

        Args:
            **kwargs: Field names and values to update

        Returns:
            List of updated documents
        """
        update_query = f"UPDATE {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            update_query += f" WHERE {' AND '.join(conditions)}"

        update_query += f" SET {', '.join(f'{k} = {json.dumps(v)}' for k, v in kwargs.items())}"

        result = await self.connection.client.query(update_query)

        if not result or not result[0]:
            return []

        return [self.document_class.from_db(doc) for doc in result[0]]

    async def delete(self) -> int:
        """Delete documents matching the query.

        This method deletes documents matching the query.

        Returns:
            Number of deleted documents
        """
        delete_query = f"DELETE FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            delete_query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(delete_query)

        if not result or not result[0]:
            return 0

        return len(result[0])

    async def bulk_create(self, documents: List[Any], batch_size: int = 1000, 
                      validate: bool = True, return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance. It can optionally validate the
        documents and return the created documents.

        Args:
            documents: List of Document instances to create
            batch_size: Number of documents per batch (default: 1000)
            validate: Whether to validate documents (default: True)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        if not documents:
            return [] if return_documents else 0

        collection = self.document_class._get_collection_name()
        total_created = 0
        created_docs = [] if return_documents else None

        # Process in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Validate batch if required
            if validate:
                # Parallel validation using asyncio.gather
                validation_tasks = [doc.validate() for doc in batch]
                await asyncio.gather(*validation_tasks)

            # Convert batch to DB representation
            data = [doc.to_db() for doc in batch]

            # Construct optimized bulk insert query
            query = f"INSERT INTO {collection} {json.dumps(data)};"

            # Execute batch insert
            try:
                result = await self.connection.client.query(query)

                if return_documents and result and result[0]:
                    # Process results if needed
                    batch_docs = [self.document_class.from_db(doc_data)
                                  for doc_data in result[0]]
                    created_docs.extend(batch_docs)
                    total_created += len(batch_docs)
                elif result and result[0]:
                    total_created += len(result[0])

            except Exception as e:
                # Log error and continue with next batch
                print(f"Error in bulk create batch: {str(e)}")
                continue

        return created_docs if return_documents else total_created



class RelationQuerySet:
    """Query set specifically for graph relations.

    This class provides methods for querying and manipulating graph relations
    between documents in the database. It allows creating, retrieving, updating,
    and deleting relations between documents.

    Attributes:
        from_document: The document class the relation is from
        connection: The database connection to use for queries
        relation: The name of the relation
        query_parts: List of query parts
    """

    def __init__(self, from_document: Type, connection: Any, relation: Optional[str] = None) -> None:
        """Initialize a new RelationQuerySet.

        Args:
            from_document: The document class the relation is from
            connection: The database connection to use for queries
            relation: The name of the relation
        """
        self.from_document = from_document
        self.connection = connection
        self.relation = relation
        self.query_parts: List[Any] = []

    async def relate(self, from_instance: Any, to_instance: Any, **attrs: Any) -> Optional[Any]:
        """Create a relation between two instances.

        This method creates a relation between two document instances in the database.
        It constructs a RELATE query with the given relation name and attributes.

        Args:
            from_instance: The instance to create the relation from
            to_instance: The instance to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed

        Raises:
            ValueError: If either instance is not saved or if no relation name is specified
        """
        if not from_instance.id:
            raise ValueError(f"Cannot create relation from unsaved {self.from_document.__name__}")

        to_class = to_instance.__class__
        if not to_instance.id:
            raise ValueError(f"Cannot create relation to unsaved {to_class.__name__}")

        # Handle both string and RecordID types for IDs
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id).split(':')[1]
            from_collection = from_instance.id.table_name
        else:
            from_id = from_instance.id.split(':')[1] if ':' in from_instance.id else from_instance.id
            from_collection = self.from_document._get_collection_name()

        if isinstance(to_instance.id, RecordID):
            to_id = str(to_instance.id).split(':')[1]
            to_collection = to_instance.id.table_name
        else:
            to_id = to_instance.id.split(':')[1] if ':' in to_instance.id else to_instance.id
            to_collection = to_class._get_collection_name()

        # Create RecordID objects with the correct collection names and IDs
        from_record = RecordID(from_collection, from_id)
        to_record = RecordID(to_collection, to_id)

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Construct the relation query using the RecordID objects
        query = f"RELATE {from_record}->{relation}->{to_record}"

        # Add attributes if provided
        if attrs:
            attrs_str = ", ".join([f"{k}: {json.dumps(v)}" for k, v in attrs.items()])
            query += f" CONTENT {{ {attrs_str} }}"

        result = await self.connection.client.query(query)

        # Return the relation record
        if result and result[0]:
            return result[0]

        return None

    async def get_related(self, instance: Any, target_document: Optional[Type] = None, **filters: Any) -> List[Any]:
        """Get related documents.

        This method retrieves documents related to the given instance through
        the specified relation. It can return either the target documents or
        the relation records themselves.

        Args:
            instance: The instance to get related documents for
            target_document: The document class of the target documents (optional)
            **filters: Filters to apply to the related documents

        Returns:
            List of related documents or relation records

        Raises:
            ValueError: If the instance is not saved or if no relation name is specified
        """
        if not instance.id:
            raise ValueError(f"Cannot get relations for unsaved {self.from_document.__name__}")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for IDs
        if isinstance(instance.id, RecordID):
            from_id = str(instance.id)
        else:
            from_id = instance.id if ':' in instance.id else f"{self.from_document._get_collection_name()}:{instance.id}"

        # Construct the graph traversal query using the correct SurrealQL syntax
        if target_document:
            # When we want to get the target documents
            query = f"SELECT ->{relation}->* FROM {from_id}"
        else:
            # When we just want the relations
            query = f"SELECT id, ->{relation}->? as related FROM {from_id}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                conditions.append(f"{field} = {json.dumps(value)}")
            query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(query)

        if not result or not result[0]:
            return []

        # Process results based on query type
        if target_document:
            # When target_document is specified, we're getting actual documents
            return [target_document.from_db(doc) for doc in result[0]]
        else:
            # When no target_document, we're getting relation data
            return result[0]

    async def update_relation(self, from_instance: Any, to_instance: Any, **attrs: Any) -> Optional[Any]:
        """Update an existing relation.

        This method updates an existing relation between two document instances
        in the database. If the relation doesn't exist, it creates it.

        Args:
            from_instance: The instance the relation is from
            to_instance: The instance the relation is to
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed

        Raises:
            ValueError: If either instance is not saved or if no relation name is specified
        """
        if not from_instance.id or not to_instance.id:
            raise ValueError("Cannot update relation between unsaved documents")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for IDs
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id)
        else:
            from_id = f"{self.from_document._get_collection_name()}:{from_instance.id}"

        to_class = to_instance.__class__
        if isinstance(to_instance.id, RecordID):
            to_id = str(to_instance.id)
        else:
            to_id = f"{to_class._get_collection_name()}:{to_instance.id}"

        # Query the relation first
        relation_query = f"SELECT id FROM {relation} WHERE in = {json.dumps(from_id)} AND out = {json.dumps(to_id)}"
        relation_result = await self.connection.client.query(relation_query)

        if not relation_result or not relation_result[0]:
            return await self.relate(from_instance, to_instance, **attrs)

        # Get relation ID and update
        relation_id = relation_result[0][0]['id']
        update_query = f"UPDATE {relation_id} SET"

        # Add attributes
        updates = []
        for key, value in attrs.items():
            updates.append(f" {key} = {json.dumps(value)}")

        update_query += ",".join(updates)

        result = await self.connection.client.query(update_query)

        if result and result[0]:
            return result[0][0]

        return None

    async def delete_relation(self, from_instance: Any, to_instance: Optional[Any] = None) -> int:
        """Delete a relation.

        This method deletes a relation between two document instances in the database.
        If to_instance is not provided, it deletes all relations from from_instance.

        Args:
            from_instance: The instance the relation is from
            to_instance: The instance the relation is to (optional)

        Returns:
            Number of deleted relations

        Raises:
            ValueError: If from_instance is not saved, if to_instance is provided but not saved,
                       or if no relation name is specified
        """
        if not from_instance.id:
            raise ValueError(f"Cannot delete relation for unsaved {self.from_document.__name__}")

        relation = self.relation
        if not relation:
            raise ValueError("Relation name must be specified")

        # Handle both string and RecordID types for from_instance ID
        if isinstance(from_instance.id, RecordID):
            from_id = str(from_instance.id)
        else:
            from_id = f"{self.from_document._get_collection_name()}:{from_instance.id}"

        # Construct the delete query
        if to_instance:
            if not to_instance.id:
                raise ValueError("Cannot delete relation to unsaved document")

            # Handle both string and RecordID types for to_instance ID
            to_class = to_instance.__class__
            if isinstance(to_instance.id, RecordID):
                to_id = str(to_instance.id)
            else:
                to_id = f"{to_class._get_collection_name()}:{to_instance.id}"

            # Delete specific relation
            query = f"DELETE FROM {relation} WHERE in = {json.dumps(from_id)} AND out = {json.dumps(to_id)}"
        else:
            # Delete all relations from this instance
            query = f"DELETE FROM {relation} WHERE in = {json.dumps(from_id)}"

        result = await self.connection.client.query(query)

        if result and result[0]:
            return len(result[0])

        return 0


class QuerySetDescriptor:
    """Descriptor that provides QuerySet access through Document.objects.

    This class is a descriptor that provides access to a QuerySet through
    the Document.objects attribute. It allows querying documents of a specific
    document class using the Document.objects attribute.

    Attributes:
        owner: The document class that owns this descriptor
        connection: The database connection to use for queries
    """

    def __init__(self) -> None:
        """Initialize a new QuerySetDescriptor."""
        self.owner: Optional[Type] = None
        self.connection: Optional[Any] = None

    def __get__(self, obj: Any, owner: Type) -> 'QuerySetDescriptor':
        """Get the descriptor for the given owner.

        This method is called when the descriptor is accessed through
        an attribute of a class or instance.

        Args:
            obj: The instance the descriptor is accessed through, or None
            owner: The class the descriptor is accessed through

        Returns:
            The descriptor instance
        """
        self.owner = owner
        self.connection = ConnectionRegistry.get_default_connection()
        return self

    async def __call__(self, **kwargs: Any) -> List[Any]:
        """Allow direct filtering through call syntax.

        This method allows calling the descriptor directly with filters
        to query the document class.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            List of matching documents
        """
        queryset = QuerySet(self.owner, self.connection)
        # Apply filters and return results
        return await queryset.filter(**kwargs).all()

    async def get(self, **kwargs: Any) -> Any:
        """Allow direct get operation.

        This method allows getting a single document matching the given filters.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        queryset = QuerySet(self.owner, self.connection)
        return await queryset.get(**kwargs)

    def filter(self, **kwargs: Any) -> QuerySet:
        """Create a QuerySet with filters.

        This method creates a new QuerySet with the given filters.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            A QuerySet with the given filters
        """
        queryset = QuerySet(self.owner, self.connection)
        return queryset.filter(**kwargs)
