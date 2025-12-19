import json
import asyncio
import logging
from typing import Any, Dict, List, Optional, Type, Union, Callable
from .exceptions import DoesNotExist, MultipleObjectsReturned
from surrealdb import RecordID
from .base_query import BaseQuerySet

# Set up logging
logger = logging.getLogger(__name__)

class SchemalessQuerySet(BaseQuerySet):
    """QuerySet for schemaless operations.

    This class provides a query builder for tables without a predefined schema.
    It extends BaseQuerySet to provide methods for querying and manipulating
    documents in a schemaless manner.

    Attributes:
        table_name: The name of the table to query
        connection: The database connection to use for queries
    """

    def __init__(self, table_name: str, connection: Any) -> None:
        """Initialize a new SchemalessQuerySet.

        Args:
            table_name: The name of the table to query
            connection: The database connection to use for queries
        """
        super().__init__(connection)
        self.table_name = table_name

    async def all(self) -> List[Any]:
        """Execute the query and return all results asynchronously.

        This method builds and executes the query, then processes the results
        based on whether a matching document class is found. If a matching
        document class is found, the results are converted to instances of that
        class. Otherwise, they are converted to SimpleNamespace objects.

        Returns:
            List of results, either document instances or SimpleNamespace objects
        """
        query = self._build_query()
        results = await self.connection.client.query(query)

        if not results or not results[0]:
            return []

        # If we have a document class in the connection's database mapping, use it
        from .document import Document  # Import at the top of the file
        doc_class = None

        # Find matching document class
        for cls in Document.__subclasses__():
            if hasattr(cls, '_meta') and cls._meta.get('collection') == self.table_name:
                doc_class = cls
                break

        # Process results based on whether we found a matching document class
        processed_results = []
        if doc_class:
            for doc_data in results:  # results[0] contains the actual data
                instance = doc_class.from_db(doc_data)
                processed_results.append(instance)
        else:
            # If no matching document class, create dynamic objects
            from types import SimpleNamespace
            for doc_data in results:
                # Check if doc_data is a dictionary, if not try to convert or skip
                if isinstance(doc_data, dict):
                    instance = SimpleNamespace(**doc_data)
                else:
                    # If it's a string, try to use it as a name attribute
                    instance = SimpleNamespace(name=str(doc_data))
                processed_results.append(instance)

        return processed_results

    def all_sync(self) -> List[Any]:
        """Execute the query and return all results synchronously.

        This method builds and executes the query, then processes the results
        based on whether a matching document class is found. If a matching
        document class is found, the results are converted to instances of that
        class. Otherwise, they are converted to SimpleNamespace objects.

        Returns:
            List of results, either document instances or SimpleNamespace objects
        """
        query = self._build_query()
        results = self.connection.client.query(query)

        if not results or not results[0]:
            return []

        # If we have a document class in the connection's database mapping, use it
        from .document import Document  # Import at the top of the file
        doc_class = None

        # Find matching document class
        for cls in Document.__subclasses__():
            if hasattr(cls, '_meta') and cls._meta.get('collection') == self.table_name:
                doc_class = cls
                break

        # Process results based on whether we found a matching document class
        processed_results = []
        if doc_class:
            for doc_data in results:  # results[0] contains the actual data
                instance = doc_class.from_db(doc_data)
                processed_results.append(instance)
        else:
            # If no matching document class, create dynamic objects
            from types import SimpleNamespace
            for doc_data in results:
                # Check if doc_data is a dictionary, if not try to convert or skip
                if isinstance(doc_data, dict):
                    instance = SimpleNamespace(**doc_data)
                else:
                    # If it's a string, try to use it as a name attribute
                    instance = SimpleNamespace(name=str(doc_data))
                processed_results.append(instance)

        return processed_results

    async def get(self, **kwargs: Any) -> Any:
        """Get a single document matching the query asynchronously.

        This method provides special handling for ID-based lookups, using the
        direct select method with RecordID. For non-ID lookups, it falls back
        to the base class implementation.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Special handling for ID-based lookup
        if len(kwargs) == 1 and 'id' in kwargs:
            id_value = kwargs['id']
            # Handle both full and short ID formats
            if ':' in str(id_value):
                record_id = id_value.split(':')[1]
            else:
                record_id = id_value

            # Use direct select with RecordID
            result = await self.connection.client.select(RecordID(self.table_name, record_id))
            if not result or result == self.table_name:  # Check for the table name response
                raise DoesNotExist(f"Object in table '{self.table_name}' matching query does not exist.")

            # Handle the result appropriately
            if isinstance(result, list):
                return result[0] if result else None
            return result

        # For non-ID lookups, use the base class implementation
        return await super().get(**kwargs)

    def get_sync(self, **kwargs: Any) -> Any:
        """Get a single document matching the query synchronously.

        This method provides special handling for ID-based lookups, using the
        direct select method with RecordID. For non-ID lookups, it falls back
        to the base class implementation.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Special handling for ID-based lookup
        if len(kwargs) == 1 and 'id' in kwargs:
            id_value = kwargs['id']
            # Handle both full and short ID formats
            if ':' in str(id_value):
                record_id = id_value.split(':')[1]
            else:
                record_id = id_value

            # Use direct select with RecordID
            result = self.connection.client.select(RecordID(self.table_name, record_id))
            if not result or result == self.table_name:  # Check for the table name response
                raise DoesNotExist(f"Object in table '{self.table_name}' matching query does not exist.")

            # Handle the result appropriately
            if isinstance(result, list):
                return result[0] if result else None
            return result

        # For non-ID lookups, use the base class implementation
        return super().get_sync(**kwargs)

    def _build_query(self) -> str:
        """Build the query string.

        This method builds the query string for the schemaless query, handling
        special cases for ID fields. It processes the query_parts to handle
        both full and short ID formats.

        Returns:
            The query string
        """
        query = f"SELECT * FROM {self.table_name}"

        if self.query_parts:
            # Process special ID handling first
            processed_query_parts = []
            for field, op, value in self.query_parts:
                if field == 'id' and isinstance(value, str):
                    # Handle record IDs specially
                    if ':' in value:
                        # Full record ID format (table:id)
                        processed_query_parts.append(('id', '=', value))
                    else:
                        # Short ID format (just id)
                        processed_query_parts.append(('id', '=', f'{self.table_name}:{value}'))
                else:
                    processed_query_parts.append((field, op, value))

            # Save the original query_parts
            original_query_parts = self.query_parts
            # Use the processed query_parts for building conditions
            self.query_parts = processed_query_parts
            conditions = self._build_conditions()
            # Restore the original query_parts
            self.query_parts = original_query_parts

            query += f" WHERE {' AND '.join(conditions)}"

        # Add other clauses from _build_clauses
        clauses = self._build_clauses()
        for clause_name, clause_sql in clauses.items():
            if clause_name != 'WHERE':  # WHERE clause is already handled
                query += f" {clause_sql}"

        return query

    async def bulk_create(self, documents: List[Dict[str, Any]], batch_size: int = 1000, 
                      return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation asynchronously.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance. It can optionally return the created documents.

        Args:
            documents: List of dictionaries representing documents to create
            batch_size: Number of documents per batch (default: 1000)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        if not documents:
            return [] if return_documents else 0

        total_created = 0
        created_docs = [] if return_documents else None

        # Process in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Construct optimized bulk insert query
            from .document import serialize_http_safe
            batch = [serialize_http_safe(doc) for doc in batch]
            query = f"INSERT INTO {self.table_name} {json.dumps(batch)};"

            # Execute batch insert
            try:
                result = await self.connection.client.query(query)

                if return_documents and result and result[0]:
                    # Process results if needed
                    from types import SimpleNamespace
                    batch_docs = []
                    for doc_data in result[0]:
                        if isinstance(doc_data, dict):
                            instance = SimpleNamespace(**doc_data)
                        else:
                            instance = SimpleNamespace(name=str(doc_data))
                        batch_docs.append(instance)
                    created_docs.extend(batch_docs)
                    total_created += len(batch_docs)
                elif result and result[0]:
                    total_created += len(result[0])

            except Exception as e:
                # Log error and continue with next batch
                logger.error(f"Error in bulk create batch: {str(e)}")
                continue

        return created_docs if return_documents else total_created

    def bulk_create_sync(self, documents: List[Dict[str, Any]], batch_size: int = 1000, 
                      return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation synchronously.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance. It can optionally return the created documents.

        Args:
            documents: List of dictionaries representing documents to create
            batch_size: Number of documents per batch (default: 1000)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        if not documents:
            return [] if return_documents else 0

        total_created = 0
        created_docs = [] if return_documents else None

        # Process in batches
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            # Construct optimized bulk insert query
            from .document import serialize_http_safe
            batch = [serialize_http_safe(doc) for doc in batch]
            query = f"INSERT INTO {self.table_name} {json.dumps(batch)};"

            # Execute batch insert
            try:
                result = self.connection.client.query(query)

                if return_documents and result and result[0]:
                    # Process results if needed
                    from types import SimpleNamespace
                    batch_docs = []
                    for doc_data in result[0]:
                        if isinstance(doc_data, dict):
                            instance = SimpleNamespace(**doc_data)
                        else:
                            instance = SimpleNamespace(name=str(doc_data))
                        batch_docs.append(instance)
                    created_docs.extend(batch_docs)
                    total_created += len(batch_docs)
                elif result and result[0]:
                    total_created += len(result[0])

            except Exception as e:
                # Log error and continue with next batch
                logger.error(f"Error in bulk create batch: {str(e)}")
                continue

        return created_docs if return_documents else total_created


class SchemalessTable:
    """Dynamic table accessor.

    This class provides access to a specific table in the database without
    requiring a predefined schema. It allows querying the table using the
    objects property or by calling the instance directly with filters.

    Attributes:
        name: The name of the table
        connection: The database connection to use for queries
    """

    def __init__(self, name: str, connection: Any) -> None:
        """Initialize a new SchemalessTable.

        Args:
            name: The name of the table
            connection: The database connection to use for queries
        """
        self.name = name
        self.connection = connection

    async def relate(self, from_id: Union[str, RecordID], relation: str, 
                    to_id: Union[str, RecordID], **attrs: Any) -> Optional[Any]:
        """Create a relation between two records asynchronously.

        This method creates a relation between two records in the database.
        It constructs a RELATE query with the given relation name and attributes.

        Args:
            from_id: The ID of the record to create the relation from
            relation: The name of the relation
            to_id: The ID of the record to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = from_id
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                table, id_part = from_id.split(':', 1)
                from_record = RecordID(table, id_part)
            else:
                # Assume it's from the current table
                from_record = RecordID(self.name, from_id)

        # Handle both string and RecordID types for to_id
        if isinstance(to_id, RecordID):
            to_record = to_id
        else:
            # If it's a string, check if it includes the table name
            if ':' in to_id:
                table, id_part = to_id.split(':', 1)
                to_record = RecordID(table, id_part)
            else:
                # Assume it's from the current table
                to_record = RecordID(self.name, to_id)

        # Construct the relation query using the RecordID objects
        query = f"RELATE {from_record}->{relation}->{to_record}"

        # Add attributes if provided
        if attrs:
            from .document import _serialize_for_surreal as _ser
            attrs_str = ", ".join([f"{k}: {_ser(v)}" for k, v in attrs.items()])
            query += f" CONTENT {{ {attrs_str} }}"

        result = await self.connection.client.query(query)

        # Return the relation record
        if result and result[0]:
            return result[0]

        return None

    def relate_sync(self, from_id: Union[str, RecordID], relation: str, 
                   to_id: Union[str, RecordID], **attrs: Any) -> Optional[Any]:
        """Create a relation between two records synchronously.

        This method creates a relation between two records in the database.
        It constructs a RELATE query with the given relation name and attributes.

        Args:
            from_id: The ID of the record to create the relation from
            relation: The name of the relation
            to_id: The ID of the record to create the relation to
            **attrs: Attributes to set on the relation

        Returns:
            The created relation record or None if creation failed
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = from_id
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                table, id_part = from_id.split(':', 1)
                from_record = RecordID(table, id_part)
            else:
                # Assume it's from the current table
                from_record = RecordID(self.name, from_id)

        # Handle both string and RecordID types for to_id
        if isinstance(to_id, RecordID):
            to_record = to_id
        else:
            # If it's a string, check if it includes the table name
            if ':' in to_id:
                table, id_part = to_id.split(':', 1)
                to_record = RecordID(table, id_part)
            else:
                # Assume it's from the current table
                to_record = RecordID(self.name, to_id)

        # Construct the relation query using the RecordID objects
        query = f"RELATE {from_record}->{relation}->{to_record}"

        # Add attributes if provided
        if attrs:
            from .document import _serialize_for_surreal as _ser
            attrs_str = ", ".join([f"{k}: {_ser(v)}" for k, v in attrs.items()])
            query += f" CONTENT {{ {attrs_str} }}"

        result = self.connection.client.query(query)

        # Return the relation record
        if result and result[0]:
            return result[0]

        return None

    async def get_related(self, from_id: Union[str, RecordID], relation: str, 
                         target_table: Optional[str] = None, **filters: Any) -> List[Any]:
        """Get related records asynchronously.

        This method retrieves records related to the given record through
        the specified relation. It can return either the target records or
        the relation records themselves.

        Args:
            from_id: The ID of the record to get related records for
            relation: The name of the relation
            target_table: The name of the target table (optional)
            **filters: Filters to apply to the related records

        Returns:
            List of related records or relation records
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = str(from_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                from_record = from_id
            else:
                # Assume it's from the current table
                from_record = f"{self.name}:{from_id}"

        # Construct the graph traversal query using the correct SurrealQL syntax
        if target_table:
            # When we want to get the target records
            query = f"SELECT * FROM {target_table} WHERE ->{relation}->{from_record}"
        else:
            # When we just want the relations
            query = f"SELECT id, ->{relation}->? as related FROM {from_record}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                from .surrealql import escape_literal
                conditions.append(f"{field} = {escape_literal(value)}")

            if target_table:
                query += f" AND {' AND '.join(conditions)}"
            else:
                query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(query)

        if not result or not result[0]:
            return []

        # Process results
        from types import SimpleNamespace
        processed_results = []
        for item in result[0]:
            if isinstance(item, dict):
                processed_results.append(SimpleNamespace(**item))
            else:
                processed_results.append(item)

        return processed_results

    def get_related_sync(self, from_id: Union[str, RecordID], relation: str, 
                        target_table: Optional[str] = None, **filters: Any) -> List[Any]:
        """Get related records synchronously.

        This method retrieves records related to the given record through
        the specified relation. It can return either the target records or
        the relation records themselves.

        Args:
            from_id: The ID of the record to get related records for
            relation: The name of the relation
            target_table: The name of the target table (optional)
            **filters: Filters to apply to the related records

        Returns:
            List of related records or relation records
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = str(from_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                from_record = from_id
            else:
                # Assume it's from the current table
                from_record = f"{self.name}:{from_id}"

        # Construct the graph traversal query using the correct SurrealQL syntax
        if target_table:
            # When we want to get the target records
            query = f"SELECT * FROM {target_table} WHERE ->{relation}->{from_record}"
        else:
            # When we just want the relations
            query = f"SELECT id, ->{relation}->? as related FROM {from_record}"

        # Add additional filters if provided
        if filters:
            conditions = []
            for field, value in filters.items():
                from .surrealql import escape_literal
                conditions.append(f"{field} = {escape_literal(value)}")

            if target_table:
                query += f" AND {' AND '.join(conditions)}"
            else:
                query += f" WHERE {' AND '.join(conditions)}"

        result = self.connection.client.query(query)

        if not result or not result[0]:
            return []

        # Process results
        from types import SimpleNamespace
        processed_results = []
        for item in result[0]:
            if isinstance(item, dict):
                processed_results.append(SimpleNamespace(**item))
            else:
                processed_results.append(item)

        return processed_results

    async def update_relation(self, from_id: Union[str, RecordID], relation: str, 
                             to_id: Union[str, RecordID], **attrs: Any) -> Optional[Any]:
        """Update an existing relation asynchronously.

        This method updates an existing relation between two records in the database.
        If the relation doesn't exist, it creates it.

        Args:
            from_id: The ID of the record the relation is from
            relation: The name of the relation
            to_id: The ID of the record the relation is to
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = str(from_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                from_record = from_id
            else:
                # Assume it's from the current table
                from_record = f"{self.name}:{from_id}"

        # Handle both string and RecordID types for to_id
        if isinstance(to_id, RecordID):
            to_record = str(to_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in to_id:
                to_record = to_id
            else:
                # Assume it's from the current table
                to_record = f"{self.name}:{to_id}"

        # Query the relation first
        from .surrealql import escape_literal
        relation_query = f"SELECT id FROM {relation} WHERE in = {escape_literal(from_record)} AND out = {escape_literal(to_record)}"
        relation_result = await self.connection.client.query(relation_query)

        if not relation_result or not relation_result[0]:
            # If relation doesn't exist, create it
            return await self.relate(from_id, relation, to_id, **attrs)

        # Get relation ID and update
        relation_id = relation_result[0][0]['id']
        update_query = f"UPDATE {relation_id} SET"

        # Add attributes
        updates = []
        from .document import _serialize_for_surreal as _ser
        for key, value in attrs.items():
            updates.append(f" {key} = {_ser(value)}")

        update_query += ",".join(updates)

        result = await self.connection.client.query(update_query)

        if result and result[0]:
            return result[0][0]

        return None

    def update_relation_sync(self, from_id: Union[str, RecordID], relation: str, 
                            to_id: Union[str, RecordID], **attrs: Any) -> Optional[Any]:
        """Update an existing relation synchronously.

        This method updates an existing relation between two records in the database.
        If the relation doesn't exist, it creates it.

        Args:
            from_id: The ID of the record the relation is from
            relation: The name of the relation
            to_id: The ID of the record the relation is to
            **attrs: Attributes to update on the relation

        Returns:
            The updated relation record or None if update failed
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = str(from_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                from_record = from_id
            else:
                # Assume it's from the current table
                from_record = f"{self.name}:{from_id}"

        # Handle both string and RecordID types for to_id
        if isinstance(to_id, RecordID):
            to_record = str(to_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in to_id:
                to_record = to_id
            else:
                # Assume it's from the current table
                to_record = f"{self.name}:{to_id}"

        # Query the relation first
        from .surrealql import escape_literal
        relation_query = f"SELECT id FROM {relation} WHERE in = {escape_literal(from_record)} AND out = {escape_literal(to_record)}"
        relation_result = self.connection.client.query(relation_query)

        if not relation_result or not relation_result[0]:
            # If relation doesn't exist, create it
            return self.relate_sync(from_id, relation, to_id, **attrs)

        # Get relation ID and update
        relation_id = relation_result[0][0]['id']
        update_query = f"UPDATE {relation_id} SET"

        # Add attributes
        updates = []
        from .document import _serialize_for_surreal as _ser
        for key, value in attrs.items():
            updates.append(f" {key} = {_ser(value)}")

        update_query += ",".join(updates)

        result = self.connection.client.query(update_query)

        if result and result[0]:
            return result[0][0]

        return None

    async def delete_relation(self, from_id: Union[str, RecordID], relation: str, 
                             to_id: Optional[Union[str, RecordID]] = None) -> int:
        """Delete a relation asynchronously.

        This method deletes a relation between two records in the database.
        If to_id is not provided, it deletes all relations from from_id.

        Args:
            from_id: The ID of the record the relation is from
            relation: The name of the relation
            to_id: The ID of the record the relation is to (optional)

        Returns:
            Number of deleted relations
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = str(from_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                from_record = from_id
            else:
                # Assume it's from the current table
                from_record = f"{self.name}:{from_id}"

        # Construct the delete query
        if to_id:
            # Handle both string and RecordID types for to_id
            if isinstance(to_id, RecordID):
                to_record = str(to_id)
            else:
                # If it's a string, check if it includes the table name
                if ':' in to_id:
                    to_record = to_id
                else:
                    # Assume it's from the current table
                    to_record = f"{self.name}:{to_id}"

            # Delete specific relation
            from .surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_record)} AND out = {escape_literal(to_record)}"
        else:
            # Delete all relations from this record
            from .surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_record)}"

        result = await self.connection.client.query(query)

        if result and result[0]:
            return len(result[0])

        return 0

    def delete_relation_sync(self, from_id: Union[str, RecordID], relation: str, 
                            to_id: Optional[Union[str, RecordID]] = None) -> int:
        """Delete a relation synchronously.

        This method deletes a relation between two records in the database.
        If to_id is not provided, it deletes all relations from from_id.

        Args:
            from_id: The ID of the record the relation is from
            relation: The name of the relation
            to_id: The ID of the record the relation is to (optional)

        Returns:
            Number of deleted relations
        """
        # Handle both string and RecordID types for from_id
        if isinstance(from_id, RecordID):
            from_record = str(from_id)
        else:
            # If it's a string, check if it includes the table name
            if ':' in from_id:
                from_record = from_id
            else:
                # Assume it's from the current table
                from_record = f"{self.name}:{from_id}"

        # Construct the delete query
        if to_id:
            # Handle both string and RecordID types for to_id
            if isinstance(to_id, RecordID):
                to_record = str(to_id)
            else:
                # If it's a string, check if it includes the table name
                if ':' in to_id:
                    to_record = to_id
                else:
                    # Assume it's from the current table
                    to_record = f"{self.name}:{to_id}"

            # Delete specific relation
            from .surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_record)} AND out = {escape_literal(to_record)}"
        else:
            # Delete all relations from this record
            from .surrealql import escape_literal
            query = f"DELETE FROM {relation} WHERE in = {escape_literal(from_record)}"

        result = self.connection.client.query(query)

        if result and result[0]:
            return len(result[0])

        return 0

    async def create_index(self, index_name: str, fields: List[str], unique: bool = False,
                           search: bool = False, analyzer: Optional[str] = None,
                           comment: Optional[str] = None) -> None:
        """Create an index on this table asynchronously.

        Args:
            index_name: Name of the index
            fields: List of field names to include in the index
            unique: Whether the index should enforce uniqueness
            search: Whether the index is a search index
            analyzer: Analyzer to use for search indexes
            comment: Optional comment for the index
        """
        fields_str = ", ".join(fields)

        # Build the index definition
        query = f"DEFINE INDEX {index_name} ON {self.name} FIELDS {fields_str}"

        # Add index type
        if unique:
            query += " UNIQUE"
        elif search and analyzer:
            query += f" SEARCH ANALYZER {analyzer}"

        # Add comment if provided
        if comment:
            query += f" COMMENT '{comment}'"

        # Execute the query
        from .connection import _maybe_span  # lazy import to avoid cycles
        with _maybe_span("surreal.schema.define_index", {"db.system": "surrealdb", "db.name": self.connection.database, "db.namespace": self.connection.namespace, "db.operation": "define_index", "db.collection": self.name, "db.index": index_name}):
            await self.connection.client.query(query)

    def create_index_sync(self, index_name: str, fields: List[str], unique: bool = False,
                         search: bool = False, analyzer: Optional[str] = None,
                         comment: Optional[str] = None) -> None:
        """Create an index on this table synchronously.

        Args:
            index_name: Name of the index
            fields: List of field names to include in the index
            unique: Whether the index should enforce uniqueness
            search: Whether the index is a search index
            analyzer: Analyzer to use for search indexes
            comment: Optional comment for the index
        """
        fields_str = ", ".join(fields)

        # Build the index definition
        query = f"DEFINE INDEX {index_name} ON {self.name} FIELDS {fields_str}"

        # Add index type
        if unique:
            query += " UNIQUE"
        elif search and analyzer:
            query += f" SEARCH ANALYZER {analyzer}"

        # Add comment if provided
        if comment:
            query += f" COMMENT '{comment}'"

        # Execute the query
        from .connection import _maybe_span  # lazy import to avoid cycles
        with _maybe_span("surreal.schema.define_index", {"db.system": "surrealdb", "db.name": self.connection.database, "db.namespace": self.connection.namespace, "db.operation": "define_index", "db.collection": self.name, "db.index": index_name}):
            self.connection.client.query(query)

    @property
    def objects(self) -> SchemalessQuerySet:
        """Get a query set for this table.

        Returns:
            A SchemalessQuerySet for querying this table
        """
        return SchemalessQuerySet(self.name, self.connection)

    async def __call__(self, limit: Optional[int] = None, start: Optional[int] = None,
                       page: Optional[tuple] = None, **kwargs: Any) -> List[Any]:
        """Query the table with filters asynchronously.

        This method allows calling the table instance directly with filters
        to query the table. It supports pagination through limit and start parameters
        or the page parameter. It returns the results as SimpleNamespace objects
        if they aren't already Document instances.

        Args:
            limit: Maximum number of results to return (for pagination)
            start: Number of results to skip (for pagination)
            page: Tuple of (page_number, page_size) for pagination
            **kwargs: Field names and values to filter by

        Returns:
            List of results, either document instances or SimpleNamespace objects
        """
        queryset = SchemalessQuerySet(self.name, self.connection)
        # Apply filters
        queryset = queryset.filter(**kwargs)

        # Apply pagination
        if page is not None:
            page_number, page_size = page
            queryset = queryset.page(page_number, page_size)
        else:
            if limit is not None:
                queryset = queryset.limit(limit)
            if start is not None:
                queryset = queryset.start(start)

        # Execute query
        results = await queryset.all()

        # Convert results to SimpleNamespace objects if they aren't already Document instances
        if results and not hasattr(results[0], '_data'):  # Check if it's not a Document instance
            from types import SimpleNamespace
            results = [SimpleNamespace(**result) if isinstance(result, dict) else result
                       for result in results]

        return results

    def call_sync(self, limit: Optional[int] = None, start: Optional[int] = None,
                  page: Optional[tuple] = None, **kwargs: Any) -> List[Any]:
        """Query the table with filters synchronously.

        This method allows calling the table synchronously with filters
        to query the table. It supports pagination through limit and start parameters
        or the page parameter. It returns the results as SimpleNamespace objects
        if they aren't already Document instances.

        Args:
            limit: Maximum number of results to return (for pagination)
            start: Number of results to skip (for pagination)
            page: Tuple of (page_number, page_size) for pagination
            **kwargs: Field names and values to filter by

        Returns:
            List of results, either document instances or SimpleNamespace objects
        """
        queryset = SchemalessQuerySet(self.name, self.connection)
        # Apply filters
        queryset = queryset.filter(**kwargs)

        # Apply pagination
        if page is not None:
            page_number, page_size = page
            queryset = queryset.page(page_number, page_size)
        else:
            if limit is not None:
                queryset = queryset.limit(limit)
            if start is not None:
                queryset = queryset.start(start)

        # Execute query
        results = queryset.all_sync()

        # Convert results to SimpleNamespace objects if they aren't already Document instances
        if results and not hasattr(results[0], '_data'):  # Check if it's not a Document instance
            from types import SimpleNamespace
            results = [SimpleNamespace(**result) if isinstance(result, dict) else result
                       for result in results]

        return results

    async def transaction(self, coroutines: List[Callable]) -> List[Any]:
        """Execute multiple operations in a transaction asynchronously.

        This method executes a list of coroutines within a transaction,
        committing the transaction if all operations succeed or canceling
        it if any operation fails.

        Args:
            coroutines: List of coroutines to execute in the transaction

        Returns:
            List of results from the coroutines

        Raises:
            Exception: If any operation in the transaction fails
        """
        await self.connection.client.query("BEGIN TRANSACTION;")
        try:
            results = []
            for coro in coroutines:
                result = await coro
                results.append(result)
            await self.connection.client.query("COMMIT TRANSACTION;")
            return results
        except Exception as e:
            await self.connection.client.query("CANCEL TRANSACTION;")
            raise e

    def transaction_sync(self, callables: List[Callable]) -> List[Any]:
        """Execute multiple operations in a transaction synchronously.

        This method executes a list of callables within a transaction,
        committing the transaction if all operations succeed or canceling
        it if any operation fails.

        Args:
            callables: List of callables to execute in the transaction

        Returns:
            List of results from the callables

        Raises:
            Exception: If any operation in the transaction fails
        """
        self.connection.client.query("BEGIN TRANSACTION;")
        try:
            results = []
            for func in callables:
                result = func()
                results.append(result)
            self.connection.client.query("COMMIT TRANSACTION;")
            return results
        except Exception as e:
            self.connection.client.query("CANCEL TRANSACTION;")
            raise e

    async def bulk_create(self, documents: List[Dict[str, Any]], batch_size: int = 1000, 
                         return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation asynchronously.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance. It can optionally return the created documents.

        Args:
            documents: List of dictionaries representing documents to create
            batch_size: Number of documents per batch (default: 1000)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        return await self.objects.bulk_create(documents, batch_size, return_documents)

    def bulk_create_sync(self, documents: List[Dict[str, Any]], batch_size: int = 1000, 
                        return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation synchronously.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance. It can optionally return the created documents.

        Args:
            documents: List of dictionaries representing documents to create
            batch_size: Number of documents per batch (default: 1000)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        return self.objects.bulk_create_sync(documents, batch_size, return_documents)


class SurrealEngine:
    """Dynamic database accessor.

    This class provides dynamic access to tables in the database without
    requiring predefined schemas. It allows accessing tables as attributes
    of the instance.

    Attributes:
        connection: The database connection to use for queries
        is_async: Whether the connection is asynchronous
    """

    def __init__(self, connection: Any) -> None:
        """Initialize a new SurrealEngine.

        Args:
            connection: The database connection to use for queries
        """
        self.connection = connection
        # Determine if the connection is async or sync
        from .connection import SurrealEngineAsyncConnection
        self.is_async = isinstance(connection, SurrealEngineAsyncConnection)

    def __getattr__(self, name: str) -> SchemalessTable:
        """Get a table accessor for the given table name.

        This method allows accessing tables as attributes of the instance.

        Args:
            name: The name of the table

        Returns:
            A SchemalessTable for accessing the table
        """
        return SchemalessTable(name, self.connection)
