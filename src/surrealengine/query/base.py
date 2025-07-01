from ..base_query import BaseQuerySet
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast
from ..exceptions import MultipleObjectsReturned, DoesNotExist
from ..fields import ReferenceField
from surrealdb import RecordID
import json
import asyncio
import logging

# Set up logging
logger = logging.getLogger(__name__)


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
        """Perform a JOIN-like operation on a reference field using FETCH.

        This method performs a JOIN-like operation on a reference field by using
        SurrealDB's FETCH clause to efficiently resolve references in a single query.

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

        if not dereference:
            # If no dereferencing needed, just return regular results
            return await self.all()

        # Use FETCH to join in a single query
        queryset = self._clone()
        queryset.fetch_fields.append(field_name)
        
        try:
            documents = await queryset.all()
            
            # If dereference_depth > 1, recursively resolve deeper references
            if dereference_depth > 1:
                for doc in documents:
                    referenced_doc = getattr(doc, field_name, None)
                    if referenced_doc and hasattr(referenced_doc, 'resolve_references'):
                        await referenced_doc.resolve_references(depth=dereference_depth-1)
            
            return documents
        except Exception:
            # Fall back to manual resolution if FETCH fails
            documents = await self.all()
            target_document_class = field.document_type

            for doc in documents:
                if getattr(doc, field_name, None):
                    ref_value = getattr(doc, field_name)
                    ref_id = None

                    if isinstance(ref_value, str) and ':' in ref_value:
                        ref_id = ref_value
                    elif hasattr(ref_value, 'id'):
                        ref_id = ref_value.id

                    if ref_id:
                        referenced_doc = await target_document_class.get(id=ref_id, dereference=dereference, dereference_depth=dereference_depth)
                        setattr(doc, field_name, referenced_doc)

            return documents

    def join_sync(self, field_name: str, target_fields: Optional[List[str]] = None, dereference: bool = True, dereference_depth: int = 1) -> List[Any]:
        """Perform a JOIN-like operation on a reference field synchronously using FETCH.

        This method performs a JOIN-like operation on a reference field by using
        SurrealDB's FETCH clause to efficiently resolve references in a single query.

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

        if not dereference:
            # If no dereferencing needed, just return regular results
            return self.all_sync()

        # Use FETCH to join in a single query
        queryset = self._clone()
        queryset.fetch_fields.append(field_name)
        
        try:
            documents = queryset.all_sync()
            
            # If dereference_depth > 1, recursively resolve deeper references
            if dereference_depth > 1:
                for doc in documents:
                    referenced_doc = getattr(doc, field_name, None)
                    if referenced_doc and hasattr(referenced_doc, 'resolve_references_sync'):
                        referenced_doc.resolve_references_sync(depth=dereference_depth-1)
            
            return documents
        except Exception:
            # Fall back to manual resolution if FETCH fails
            documents = self.all_sync()
            target_document_class = field.document_type

            for doc in documents:
                if getattr(doc, field_name, None):
                    ref_value = getattr(doc, field_name)
                    ref_id = None

                    if isinstance(ref_value, str) and ':' in ref_value:
                        ref_id = ref_value
                    elif hasattr(ref_value, 'id'):
                        ref_id = ref_value.id

                    if ref_id:
                        referenced_doc = target_document_class.get_sync(id=ref_id, dereference=dereference, dereference_depth=dereference_depth)
                        setattr(doc, field_name, referenced_doc)

            return documents

    def _build_query(self) -> str:
        """Build the query string with performance optimizations.

        This method builds the query string for the document class query.
        It automatically uses optimized direct record access when possible.

        Returns:
            The optimized query string
        """
        # Try to build optimized direct record access query first
        optimized_query = self._build_direct_record_query()
        if optimized_query:
            return optimized_query
        
        # Fall back to regular query building
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
        """Update documents matching the query asynchronously with performance optimizations.

        This method updates documents matching the query with the given field values.
        Uses direct record access for bulk ID operations for better performance.

        Args:
            **kwargs: Field names and values to update

        Returns:
            List of updated documents
        """
        # PERFORMANCE OPTIMIZATION: Use direct record access for bulk operations
        if self._bulk_id_selection or self._id_range_selection:
            # For bulk operations, use subquery with direct record access for better performance
            optimized_query = self._build_direct_record_query()
            if optimized_query:
                # Convert SELECT to subquery for UPDATE
                subquery = optimized_query.replace("SELECT *", "SELECT id")
                update_query = f"UPDATE ({subquery}) SET {', '.join(f'{k} = {json.dumps(v)}' for k, v in kwargs.items())}"
                
                result = await self.connection.client.query(update_query)
                
                if not result:
                    return []
                
                # Handle different result structures
                if isinstance(result[0], dict):
                    # Subquery UPDATE case: result is a flat list of documents
                    return [self.document_class.from_db(doc) for doc in result]
                elif isinstance(result[0], list):
                    # Normal case: result[0] is a list of document dictionaries
                    return [self.document_class.from_db(doc) for doc in result[0]]
                else:
                    return []
        
        # Fall back to regular update query
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
        """Update documents matching the query synchronously with performance optimizations.

        This method updates documents matching the query with the given field values.
        Uses direct record access for bulk ID operations for better performance.

        Args:
            **kwargs: Field names and values to update

        Returns:
            List of updated documents
        """
        # PERFORMANCE OPTIMIZATION: Use direct record access for bulk operations
        if self._bulk_id_selection or self._id_range_selection:
            # For bulk operations, use subquery with direct record access for better performance
            optimized_query = self._build_direct_record_query()
            if optimized_query:
                # Convert SELECT to subquery for UPDATE
                subquery = optimized_query.replace("SELECT *", "SELECT id")
                update_query = f"UPDATE ({subquery}) SET {', '.join(f'{k} = {json.dumps(v)}' for k, v in kwargs.items())}"
                
                result = self.connection.client.query(update_query)
                
                if not result:
                    return []
                
                # Handle different result structures
                if isinstance(result[0], dict):
                    # Subquery UPDATE case: result is a flat list of documents
                    return [self.document_class.from_db(doc) for doc in result]
                elif isinstance(result[0], list):
                    # Normal case: result[0] is a list of document dictionaries
                    return [self.document_class.from_db(doc) for doc in result[0]]
                else:
                    return []
        
        # Fall back to regular update query
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
        """Delete documents matching the query asynchronously with performance optimizations.

        This method deletes documents matching the query.
        Uses direct record access for bulk ID operations for better performance.

        Returns:
            Number of deleted documents
        """
        # PERFORMANCE OPTIMIZATION: Use direct record access for bulk operations
        if self._bulk_id_selection:
            # Use direct record deletion syntax for bulk ID operations
            record_ids = [self._format_record_id(id_val) for id_val in self._bulk_id_selection]
            delete_query = f"DELETE {', '.join(record_ids)}"
            
            result = await self.connection.client.query(delete_query)
            # Direct record deletion returns empty list on success
            # Return the count of IDs we attempted to delete
            return len(record_ids)
        elif self._id_range_selection:
            # For range operations, use optimized query with subquery
            optimized_query = self._build_direct_record_query()
            if optimized_query:
                # Convert SELECT to subquery for DELETE
                subquery = optimized_query.replace("SELECT *", "SELECT id")
                delete_query = f"DELETE ({subquery})"
                
                result = await self.connection.client.query(delete_query)
                if not result or not result[0]:
                    return 0
                return len(result[0])
        
        # Fall back to regular delete query
        delete_query = f"DELETE FROM {self.document_class._get_collection_name()}"

        if self.query_parts:
            conditions = self._build_conditions()
            delete_query += f" WHERE {' AND '.join(conditions)}"

        result = await self.connection.client.query(delete_query)

        if not result or not result[0]:
            return 0

        return len(result[0])

    def delete_sync(self) -> int:
        """Delete documents matching the query synchronously with performance optimizations.

        This method deletes documents matching the query.
        Uses direct record access for bulk ID operations for better performance.

        Returns:
            Number of deleted documents
        """
        # PERFORMANCE OPTIMIZATION: Use direct record access for bulk operations
        if self._bulk_id_selection:
            # Use direct record deletion syntax for bulk ID operations
            record_ids = [self._format_record_id(id_val) for id_val in self._bulk_id_selection]
            delete_query = f"DELETE {', '.join(record_ids)}"
            
            result = self.connection.client.query(delete_query)
            # Direct record deletion returns empty list on success
            # Return the count of IDs we attempted to delete
            return len(record_ids)
        elif self._id_range_selection:
            # For range operations, use optimized query with subquery
            optimized_query = self._build_direct_record_query()
            if optimized_query:
                # Convert SELECT to subquery for DELETE
                subquery = optimized_query.replace("SELECT *", "SELECT id")
                delete_query = f"DELETE ({subquery})"
                
                result = self.connection.client.query(delete_query)
                if not result or not result[0]:
                    return 0
                return len(result[0])
        
        # Fall back to regular delete query
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
                # Sequential validation since validate() is synchronous
                for doc in batch:
                    doc.validate()

            # Separate documents with and without explicit IDs
            docs_without_ids = []
            docs_with_ids = []
            
            for doc in batch:
                if doc.id:
                    docs_with_ids.append(doc)
                else:
                    docs_without_ids.append(doc)
            
            # Handle documents without IDs using bulk INSERT
            if docs_without_ids:
                data = [doc.to_db() for doc in docs_without_ids]
                query = f"INSERT INTO {collection} {json.dumps(data)};"
                
                try:
                    result = await self.connection.client.query(query)
                    if return_documents and result and result[0]:
                        batch_docs = [self.document_class.from_db(doc_data)
                                      for doc_data in result[0]]
                        created_docs.extend(batch_docs)
                        total_created += len(batch_docs)
                    elif result and result[0]:
                        total_created += len(result[0])
                except Exception as e:
                    logger.error(f"Error in bulk create batch (no IDs): {str(e)}")
            
            # Handle documents with explicit IDs using individual upserts
            for doc in docs_with_ids:
                try:
                    data = doc.to_db()
                    # Remove ID from data and extract ID part
                    if 'id' in data:
                        del data['id']
                        id_part = str(doc.id).split(':')[1]
                        result = await self.connection.client.upsert(
                            RecordID(collection, int(id_part) if id_part.isdigit() else id_part),
                            data
                        )
                        
                        if return_documents and result:
                            if isinstance(result, list) and result:
                                doc_data = result[0]
                            else:
                                doc_data = result
                            
                            if isinstance(doc_data, dict):
                                if created_docs is not None:
                                    created_docs.append(self.document_class.from_db(doc_data))
                        
                        total_created += 1
                        
                except Exception as e:
                    logger.error(f"Error creating document with ID {doc.id}: {str(e)}")
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
                logger.error(f"Error in bulk create batch: {str(e)}")
                continue

        return created_docs if return_documents else total_created

    
    async def explain(self) -> List[Dict[str, Any]]:
        """Get query execution plan for performance analysis.
        
        This method appends EXPLAIN to the query to show how SurrealDB
        will execute it, helping identify performance bottlenecks.
        
        Returns:
            List of execution plan steps with details
            
        Example:
            plan = await User.objects.filter(age__lt=18).explain()
            print(f"Query will use: {plan[0]['operation']}")
        """
        query = self._build_query() + " EXPLAIN"
        result = await self.connection.client.query(query)
        return result[0] if result and result[0] else []
    
    def explain_sync(self) -> List[Dict[str, Any]]:
        """Get query execution plan for performance analysis synchronously.
        
        Returns:
            List of execution plan steps with details
        """
        query = self._build_query() + " EXPLAIN"
        result = self.connection.client.query(query)
        return result[0] if result and result[0] else []
    
    def suggest_indexes(self) -> List[str]:
        """Suggest indexes based on current query patterns.
        
        Analyzes the current query conditions and suggests optimal
        indexes that could improve performance.
        
        Returns:
            List of suggested DEFINE INDEX statements
            
        Example:
            suggestions = User.objects.filter(age__lt=18, city="NYC").suggest_indexes()
            for suggestion in suggestions:
                print(f"Consider: {suggestion}")
        """
        suggestions = []
        collection_name = self.document_class._get_collection_name()
        
        # Analyze filter conditions
        analyzed_fields = set()
        for field, op, value in self.query_parts:
            if field != 'id' and field not in analyzed_fields:  # ID doesn't need indexing
                analyzed_fields.add(field)
                if op in ('=', '!=', '>', '<', '>=', '<=', 'INSIDE', 'NOT INSIDE'):
                    suggestions.append(
                        f"DEFINE INDEX idx_{collection_name}_{field} ON {collection_name} FIELDS {field}"
                    )
        
        # Suggest compound indexes for multiple conditions
        if len(analyzed_fields) > 1:
            field_list = ', '.join(sorted(analyzed_fields))
            suggestions.append(
                f"DEFINE INDEX idx_{collection_name}_compound ON {collection_name} FIELDS {field_list}"
            )
        
        # Suggest order by indexes
        if self.order_by_value:
            order_field, _ = self.order_by_value
            if order_field not in analyzed_fields:
                suggestions.append(
                    f"DEFINE INDEX idx_{collection_name}_{order_field} ON {collection_name} FIELDS {order_field}"
                )
        
        return list(set(suggestions))  # Remove duplicates