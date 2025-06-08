from ..base_query import BaseQuerySet
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast
from ..exceptions import MultipleObjectsReturned, DoesNotExist
from ..fields import ReferenceField
import json
import asyncio


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

    async def join(self, field_name: str, target_fields: Optional[List[str]] = None, dereference: bool = True, dereference_depth: int = 1) -> List[Any]:
        """Perform a JOIN-like operation on a reference field.

        This method performs a JOIN-like operation on a reference field by retrieving
        all documents and then resolving the references using the Document.get method.

        Args:
            field_name: The name of the reference field to join on
            target_fields: Optional list of fields to select from the target document
            dereference: Whether to dereference references in the joined documents (default: True)
            dereference_depth: Maximum depth of reference resolution (default: 1)

        Returns:
            List of documents with joined data

        Raises:
            ValueError: If the field is not a ReferenceField
        """
        # Ensure field_name is a ReferenceField
        field = self.document_class._fields.get(field_name)
        if not field or not isinstance(field, ReferenceField):
            raise ValueError(f"{field_name} is not a ReferenceField")

        # Get all documents
        documents = await self.filter().all()
        if not documents:
            return []

        # Get the target document class
        target_document_class = field.document_type

        # Manually resolve references for each document
        for doc in documents:
            # Resolve the reference
            if getattr(doc, field_name, None):
                ref_value = getattr(doc, field_name)
                ref_id = None

                # Extract the ID from the reference
                if isinstance(ref_value, str) and ':' in ref_value:
                    ref_id = ref_value
                elif hasattr(ref_value, 'id'):
                    ref_id = ref_value.id

                # If we have an ID, resolve the reference
                if ref_id:
                    referenced_doc = await target_document_class.get(id=ref_id, dereference=dereference, dereference_depth=dereference_depth)
                    setattr(doc, field_name, referenced_doc)

        return documents

    def join_sync(self, field_name: str, target_fields: Optional[List[str]] = None, dereference: bool = True, dereference_depth: int = 1) -> List[Any]:
        """Perform a JOIN-like operation on a reference field synchronously.

        This method performs a JOIN-like operation on a reference field by using
        SurrealDB's graph traversal capabilities. It retrieves the referenced documents
        and replaces the reference IDs with the actual documents.

        Args:
            field_name: The name of the reference field to join on
            target_fields: Optional list of fields to select from the target document
            dereference: Whether to dereference references in the joined documents (default: True)
            dereference_depth: Maximum depth of reference resolution (default: 1)

        Returns:
            List of documents with joined data

        Raises:
            ValueError: If the field is not a ReferenceField
        """
        # Ensure field_name is a ReferenceField
        field = self.document_class._fields.get(field_name)
        if not field or not isinstance(field, ReferenceField):
            raise ValueError(f"{field_name} is not a ReferenceField")

        # Get all documents
        documents = self.filter().all_sync()
        if not documents:
            return []

        # Get the target document class
        target_document_class = field.document_type

        # Manually resolve references for each document
        for doc in documents:
            # Resolve the reference
            if getattr(doc, field_name, None):
                ref_value = getattr(doc, field_name)
                ref_id = None

                # Extract the ID from the reference
                if isinstance(ref_value, str) and ':' in ref_value:
                    ref_id = ref_value
                elif hasattr(ref_value, 'id'):
                    ref_id = ref_value.id

                # If we have an ID, resolve the reference
                if ref_id:
                    referenced_doc = target_document_class.get_sync(id=ref_id, dereference=dereference, dereference_depth=dereference_depth)
                    setattr(doc, field_name, referenced_doc)

        return documents

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

        # Add other clauses from _build_clauses
        clauses = self._build_clauses()
        for clause_name, clause_sql in clauses.items():
            if clause_name != 'WHERE':  # WHERE clause is already handled
                query += f" {clause_sql}"

        return query

    async def all(self, dereference: bool = False) -> List[Any]:
        """Execute the query and return all results asynchronously.

        This method builds and executes the query, then converts the results
        to instances of the document class.

        Args:
            dereference: Whether to dereference references (default: False)

        Returns:
            List of document instances
        """
        query = self._build_query()
        results = await self.connection.client.query(query)

        if not results or not results[0]:
            return []

        # Create one instance per result document
        processed_results = [self.document_class.from_db(doc, dereference=dereference) for doc in results]
        return processed_results

    def all_sync(self, dereference: bool = False) -> List[Any]:
        """Execute the query and return all results synchronously.

        This method builds and executes the query, then converts the results
        to instances of the document class.

        Args:
            dereference: Whether to dereference references (default: False)

        Returns:
            List of document instances
        """
        query = self._build_query()
        results = self.connection.client.query(query)

        if not results or not results[0]:
            return []

        # Create one instance per result document
        processed_results = [self.document_class.from_db(doc, dereference=dereference) for doc in results]
        return processed_results

    async def count(self) -> int:
        """Count documents matching the query asynchronously.

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

        return len(result)

    def count_sync(self) -> int:
        """Count documents matching the query synchronously.

        This method builds and executes a count query to count the number
        of documents matching the query.

        Returns:
            Number of matching documents
        """
        count_query = f"SELECT count() FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            count_query += f" WHERE {' AND '.join(conditions)}"

        result = self.connection.client.query(count_query)

        if not result or not result[0]:
            return 0

        return len(result)

    async def get(self, dereference: bool = False, **kwargs: Any) -> Any:
        """Get a single document matching the query asynchronously.

        This method applies filters and ensures that exactly one document is returned.

        Args:
            dereference: Whether to dereference references (default: False)
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        self.filter(**kwargs)
        self.limit_value = 2  # Get 2 to check for multiple
        results = await self.all(dereference=dereference)

        if not results:
            raise DoesNotExist(f"{self.document_class.__name__} matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned(f"Multiple {self.document_class.__name__} objects returned instead of one")

        return results[0]

    def get_sync(self, dereference: bool = False, **kwargs: Any) -> Any:
        """Get a single document matching the query synchronously.

        This method applies filters and ensures that exactly one document is returned.

        Args:
            dereference: Whether to dereference references (default: False)
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        self.filter(**kwargs)
        self.limit_value = 2  # Get 2 to check for multiple
        results = self.all_sync(dereference=dereference)

        if not results:
            raise DoesNotExist(f"{self.document_class.__name__} matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned(f"Multiple {self.document_class.__name__} objects returned instead of one")

        return results[0]

    async def create(self, **kwargs: Any) -> Any:
        """Create a new document asynchronously.

        This method creates a new document with the given field values.

        Args:
            **kwargs: Field names and values for the new document

        Returns:
            The created document
        """
        document = self.document_class(**kwargs)
        return await document.save(self.connection)

    def create_sync(self, **kwargs: Any) -> Any:
        """Create a new document synchronously.

        This method creates a new document with the given field values.

        Args:
            **kwargs: Field names and values for the new document

        Returns:
            The created document
        """
        document = self.document_class(**kwargs)
        return document.save_sync(self.connection)

    async def update(self, **kwargs: Any) -> List[Any]:
        """Update documents matching the query asynchronously.

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

    def update_sync(self, **kwargs: Any) -> List[Any]:
        """Update documents matching the query synchronously.

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

        result = self.connection.client.query(update_query)

        if not result or not result[0]:
            return []

        return [self.document_class.from_db(doc) for doc in result[0]]

    async def delete(self) -> int:
        """Delete documents matching the query asynchronously.

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

    def delete_sync(self) -> int:
        """Delete documents matching the query synchronously.

        This method deletes documents matching the query.

        Returns:
            Number of deleted documents
        """
        delete_query = f"DELETE FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            delete_query += f" WHERE {' AND '.join(conditions)}"

        result = self.connection.client.query(delete_query)

        if not result or not result[0]:
            return 0

        return len(result[0])

    async def bulk_create(self, documents: List[Any], batch_size: int = 1000,
                      validate: bool = True, return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation asynchronously.

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

    def bulk_create_sync(self, documents: List[Any], batch_size: int = 1000,
                      validate: bool = True, return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation synchronously.

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
                # Sequential validation for sync version
                for doc in batch:
                    doc.validate()

            # Convert batch to DB representation
            data = [doc.to_db() for doc in batch]

            # Construct optimized bulk insert query
            query = f"INSERT INTO {collection} {json.dumps(data)};"

            # Execute batch insert
            try:
                result = self.connection.client.query(query)

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
