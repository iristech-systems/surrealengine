import json
from typing import Any, Dict, List, Optional, Tuple, Union, Type, cast
from .exceptions import MultipleObjectsReturned, DoesNotExist
from surrealdb import RecordID
from .pagination import PaginationResult
from .record_id_utils import RecordIdUtils
from .surrealql import escape_literal

# Import these at runtime to avoid circular imports
def _get_connection_classes():
    from .connection import SurrealEngineAsyncConnection, SurrealEngineSyncConnection
    return SurrealEngineAsyncConnection, SurrealEngineSyncConnection

class BaseQuerySet:
    """Base query builder for SurrealDB.

    This class provides the foundation for building queries in SurrealDB.
    It includes methods for filtering, limiting, ordering, and retrieving results.
    Subclasses must implement specific methods like _build_query, all, and count.

    Attributes:
        connection: The database connection to use for queries
        query_parts: List of query conditions (field, operator, value)
        limit_value: Maximum number of results to return
        start_value: Number of results to skip (for pagination)
        order_by_value: Field and direction to order results by
        group_by_fields: Fields to group results by
        split_fields: Fields to split results by
        fetch_fields: Fields to fetch related records for
        with_index: Index to use for the query
    """

    def __init__(self, connection: Any) -> None:
        """Initialize a new BaseQuerySet.

        Args:
            connection: The database connection to use for queries
        """
        self.connection = connection
        self.query_parts: List[Tuple[str, str, Any]] = []
        self.limit_value: Optional[int] = None
        self.start_value: Optional[int] = None
        self.order_by_value: Optional[Tuple[str, str]] = None
        self.group_by_fields: List[str] = []
        self.split_fields: List[str] = []
        self.fetch_fields: List[str] = []
        self.with_index: Optional[str] = None
        self.select_fields: Optional[List[str]] = None
        # Graph traversal state
        self._traversal_path: Optional[str] = None
        self._traversal_unique: bool = True
        self._traversal_max_depth: Optional[int] = None
        # Performance optimization attributes
        self._bulk_id_selection: Optional[List[Any]] = None
        self._id_range_selection: Optional[Tuple[Any, Any, bool]] = None
        self._prefer_direct_access: bool = False

    def is_async_connection(self) -> bool:
        """Check if the connection is asynchronous.

        Returns:
            True if the connection is asynchronous, False otherwise
        """
        SurrealEngineAsyncConnection, SurrealEngineSyncConnection = _get_connection_classes()
        return isinstance(self.connection, SurrealEngineAsyncConnection)

    def filter(self, query=None, **kwargs) -> 'BaseQuerySet':
        """Add filter conditions to the query with automatic ID optimization.

        This method supports both Q objects and Django-style field lookups with double-underscore operators:
        - field__gt: Greater than
        - field__lt: Less than
        - field__gte: Greater than or equal
        - field__lte: Less than or equal
        - field__ne: Not equal
        - field__in: Inside (for arrays) - optimized for ID fields
        - field__nin: Not inside (for arrays)
        - field__contains: Contains (for strings or arrays)
        - field__startswith: Starts with (for strings)
        - field__endswith: Ends with (for strings)
        - field__regex: Matches regex pattern (for strings)

        PERFORMANCE OPTIMIZATIONS:
        - id__in automatically uses direct record access syntax
        - ID range queries (id__gte + id__lte) use range syntax

        Args:
            query: Q object or QueryExpression for complex queries
            **kwargs: Field names and values to filter by

        Returns:
            A new queryset instance for method chaining

        Raises:
            ValueError: If an unknown operator is provided
        """
        # Clone first to avoid mutating the original queryset
        result = self if (query is None and not kwargs) else self._clone()

        # Handle Q objects and QueryExpressions
        if query is not None:
            # Import here to avoid circular imports
            try:
                from .query_expressions import Q, QueryExpression

                if isinstance(query, Q):
                    # Use to_where_clause() to properly handle both simple and compound Q objects
                    where_clause = query.to_where_clause()
                    if where_clause:
                        result.query_parts.append(('__raw__', '=', where_clause))
                    # Don't return early - continue to process kwargs if provided

                elif isinstance(query, QueryExpression):
                    # Apply QueryExpression to this queryset
                    return query.apply_to_queryset(result)

                else:
                    raise ValueError(f"Unsupported query type: {type(query)}")

            except ImportError:
                raise ValueError("Query expressions not available")

        # Process kwargs (either standalone or combined with a Q object)
        if not kwargs:
            return result

        # Continue with existing kwargs processing
        # PERFORMANCE OPTIMIZATION: Check for bulk ID operations
        if len(kwargs) == 1 and 'id__in' in kwargs:
            result._bulk_id_selection = kwargs['id__in']
            return result

        # PERFORMANCE OPTIMIZATION: Check for ID range operations
        id_range_keys = {k for k in kwargs.keys() if k.startswith('id__') and k.endswith(('gte', 'lte', 'gt', 'lt'))}
        if len(kwargs) == 2 and len(id_range_keys) == 2:
            if 'id__gte' in kwargs and 'id__lte' in kwargs:
                result._id_range_selection = (kwargs['id__gte'], kwargs['id__lte'], True)  # inclusive
                return result
            elif 'id__gt' in kwargs and 'id__lt' in kwargs:
                result._id_range_selection = (kwargs['id__gt'], kwargs['id__lt'], False)  # exclusive
                return result

        # Fall back to regular filtering for non-optimizable queries
        for k, v in kwargs.items():
            if k == 'id':
                # Use RecordIdUtils for comprehensive ID handling
                table_name = None
                if hasattr(self, 'document_class') and self.document_class:
                    table_name = self.document_class._get_collection_name()

                normalized_id = RecordIdUtils.normalize_record_id(v, table_name)
                if normalized_id:
                    result.query_parts.append((k, '=', normalized_id))
                else:
                    # Fall back to original value if normalization fails
                    result.query_parts.append((k, '=', str(v)))
                continue

            # Special handling for URL fields - mark them with a special tag
            if k == 'url' or (isinstance(v, str) and (v.startswith('http://') or v.startswith('https://'))):
                # Add a special tag to indicate this is a URL that needs quoting
                result.query_parts.append((k, '=', {'__url_value__': v}))
                continue

            parts = k.split('__')
            field = parts[0]

            # Handle operators
            if len(parts) > 1:
                op = parts[1]
                if op == 'gt':
                    result.query_parts.append((field, '>', v))
                elif op == 'lt':
                    result.query_parts.append((field, '<', v))
                elif op == 'gte':
                    result.query_parts.append((field, '>=', v))
                elif op == 'lte':
                    result.query_parts.append((field, '<=', v))
                elif op == 'ne':
                    result.query_parts.append((field, '!=', v))
                elif op == 'in':
                    # Note: id__in is handled by optimization above
                    result.query_parts.append((field, 'INSIDE', v))
                elif op == 'nin':
                    result.query_parts.append((field, 'NOT INSIDE', v))
                elif op == 'contains':
                    if isinstance(v, str):
                        result.query_parts.append((f"string::contains({field}, '{v}')", '=', True))
                    else:
                        result.query_parts.append((field, 'CONTAINS', v))
                elif op == 'startswith':
                    result.query_parts.append((f"string::starts_with({field}, '{v}')", '=', True))
                elif op == 'endswith':
                    result.query_parts.append((f"string::ends_with({field}, '{v}')", '=', True))
                elif op == 'regex':
                    result.query_parts.append((f"string::matches({field}, r'{v}')", '=', True))
                else:
                    # Handle nested field access for DictFields
                    document_class = getattr(self, 'document_class', None)
                    if document_class and hasattr(document_class, '_fields'):
                        if field in document_class._fields:
                            from .fields import DictField
                            if isinstance(document_class._fields[field], DictField):
                                nested_field = f"{field}.{op}"
                                result.query_parts.append((nested_field, '=', v))
                                continue

                    # If we get here, it's an unknown operator
                    raise ValueError(f"Unknown operator: {op}")
            else:
                # Simple equality
                result.query_parts.append((field, '=', v))

        return result

    def only(self, *fields: str) -> 'BaseQuerySet':
        """Select only the specified fields.

        This method sets the fields to be selected in the query.
        It automatically includes the 'id' field.

        Args:
            *fields: Field names to select

        Returns:
            The query set instance for method chaining
        """
        clone = self._clone()
        select_fields = list(fields)
        if 'id' not in select_fields:
            select_fields.append('id')
        clone.select_fields = select_fields
        return clone

    def limit(self, value: int) -> 'BaseQuerySet':
        """Set the maximum number of results to return.

        Args:
            value: Maximum number of results

        Returns:
            The query set instance for method chaining
        """
        self.limit_value = value
        return self

    def start(self, value: int) -> 'BaseQuerySet':
        """Set the number of results to skip (for pagination).

        Args:
            value: Number of results to skip

        Returns:
            The query set instance for method chaining
        """
        self.start_value = value
        return self

    def order_by(self, field: str, direction: str = 'ASC') -> 'BaseQuerySet':
        """Set the field and direction to order results by.

        Args:
            field: Field name to order by
            direction: Direction to order by ('ASC' or 'DESC')

        Returns:
            The query set instance for method chaining
        """
        self.order_by_value = (field, direction)
        return self

    def group_by(self, *fields: str) -> 'BaseQuerySet':
        """Group the results by the specified fields.

        This method sets the fields to group the results by using the GROUP BY clause.

        Args:
            *fields: Field names to group by

        Returns:
            The query set instance for method chaining
        """
        self.group_by_fields.extend(fields)
        return self

    def split(self, *fields: str) -> 'BaseQuerySet':
        """Split the results by the specified fields.

        This method sets the fields to split the results by using the SPLIT clause.

        Args:
            *fields: Field names to split by

        Returns:
            The query set instance for method chaining
        """
        self.split_fields.extend(fields)
        return self

    def fetch(self, *fields: str) -> 'BaseQuerySet':
        """Fetch related records for the specified fields.

        This method sets the fields to fetch related records for using the FETCH clause.

        Args:
            *fields: Field names to fetch related records for

        Returns:
            The query set instance for method chaining
        """
        self.fetch_fields.extend(fields)
        return self

    def get_many(self, ids: List[Union[str, Any]]) -> 'BaseQuerySet':
        """Get multiple records by IDs using optimized direct record access.
        
        This method uses SurrealDB's direct record selection syntax for better
        performance compared to WHERE clause filtering.
        
        Args:
            ids: List of record IDs (can be strings or other ID types)
            
        Returns:
            The query set instance configured for direct record access
            
        Example:
            # Efficient: SELECT * FROM users:1, users:2, users:3
            users = await User.objects.get_many([1, 2, 3]).all()
            users = await User.objects.get_many(['users:1', 'users:2']).all()
        """
        clone = self._clone()
        clone._bulk_id_selection = ids
        return clone
    
    def get_range(self, start_id: Union[str, Any], end_id: Union[str, Any], 
                  inclusive: bool = True) -> 'BaseQuerySet':
        """Get a range of records by ID using optimized range syntax.
        
        This method uses SurrealDB's range selection syntax for better
        performance compared to WHERE clause filtering.
        
        Args:
            start_id: Starting ID of the range
            end_id: Ending ID of the range  
            inclusive: Whether the range is inclusive (default: True)
            
        Returns:
            The query set instance configured for range access
            
        Example:
            # Efficient: SELECT * FROM users:100..=200
            users = await User.objects.get_range(100, 200).all()
            users = await User.objects.get_range('users:100', 'users:200', inclusive=False).all()
        """
        clone = self._clone()
        clone._id_range_selection = (start_id, end_id, inclusive)
        return clone


    def with_index(self, index: str) -> 'BaseQuerySet':
        """Use the specified index for the query.

        This method sets the index to use for the query using the WITH clause.

        Args:
            index: Name of the index to use

        Returns:
            The query set instance for method chaining
        """
        self.with_index = index
        return self
    
    def use_direct_access(self) -> 'BaseQuerySet':
        """Mark this queryset to prefer direct record access when possible.
        
        This method sets a preference for using direct record access patterns
        over WHERE clause filtering for better performance.
        
        Returns:
            The query set instance for method chaining
        """
        clone = self._clone()
        clone._prefer_direct_access = True
        return clone

    def _build_query(self) -> str:
        """Build the base query string.

        This method must be implemented by subclasses to generate the appropriate
        query string for the specific database operation.

        Returns:
            The query string

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement _build_query")

    def _build_conditions(self) -> List[str]:
        """Build query conditions from query_parts.

        This method converts the query_parts list into a list of condition strings
        that can be used in a WHERE clause.

        Returns:
            List of condition strings
        """
        conditions = []
        for field, op, value in self.query_parts:
            # Handle raw query conditions
            if field == '__raw__':
                conditions.append(value)
            # Handle special cases
            elif op == '=' and isinstance(field, str) and '::' in field:
                conditions.append(f"{field}")
            else:
                # Determine if field is a RecordID field
                def _field_is_record_id(field_name: str) -> bool:
                    document_class = getattr(self, 'document_class', None)
                    if not document_class or not hasattr(document_class, '_fields'):
                        return False
                    field_obj = document_class._fields.get(field_name)
                    try:
                        from .fields.id import RecordIDField  # type: ignore
                        return isinstance(field_obj, RecordIDField)
                    except Exception:
                        return False

                # Special handling for RecordIDs - only for id or RecordIDField or RecordID object
                if field == 'id' or _field_is_record_id(field) or isinstance(value, RecordID):
                    # Ensure RecordID is properly formatted
                    if isinstance(value, str) and RecordIdUtils.is_valid_record_id(value):
                        conditions.append(f"{field} {op} {value}")
                    elif isinstance(value, RecordID):
                        conditions.append(f"{field} {op} {str(value)}")
                    else:
                        # Try to normalize the RecordID
                        table_name = None
                        if hasattr(self, 'document_class') and self.document_class:
                            table_name = self.document_class._get_collection_name()
                        normalized = RecordIdUtils.normalize_record_id(value, table_name)
                        if normalized and RecordIdUtils.is_valid_record_id(normalized):
                            conditions.append(f"{field} {op} {normalized}")
                        else:
                            conditions.append(f"{field} {op} {escape_literal(value)}")
                # Special handling for INSIDE and NOT INSIDE operators
                elif op in ('INSIDE', 'NOT INSIDE'):
                    # Only treat list items as record IDs if the field is a RecordID field
                    treat_items_as_ids = _field_is_record_id(field)
                    def _is_record_id_str(s):
                        return isinstance(s, str) and RecordIdUtils.is_valid_record_id(s)
                    def _format_literal(item):
                        # Accept dicts with 'id'
                        if isinstance(item, dict) and 'id' in item and _is_record_id_str(item['id']) and treat_items_as_ids:
                            return item['id']
                        # RecordID object
                        if isinstance(item, RecordID) and treat_items_as_ids:
                            return str(item)
                        # String record id
                        if _is_record_id_str(item) and treat_items_as_ids:
                            return item
                        # Fallback to escape_literal for proper quoting/escaping
                        return escape_literal(item)
                    if isinstance(value, (list, tuple, set)):
                        items = ', '.join(_format_literal(v) for v in value)
                        value_str = f"[{items}]"
                    else:
                        # Single non-iterable value - still format appropriately
                        value_str = _format_literal(value)
                    conditions.append(f"{field} {op} {value_str}")
                elif isinstance(value, RecordID):
                    # If value is a RecordID object but field is not RecordID-typed, quote it to be safe
                    conditions.append(f"{field} {op} {escape_literal(str(value))}")
                elif op == 'STARTSWITH':
                    conditions.append(f"string::starts_with({field}, {escape_literal(value)})")
                elif op == 'ENDSWITH':
                    conditions.append(f"string::ends_with({field}, {escape_literal(value)})")
                elif op == 'CONTAINS':
                    if isinstance(value, str):
                        conditions.append(f"string::contains({field}, {escape_literal(value)})")
                    else:
                        conditions.append(f"{field} CONTAINS {escape_literal(value)}")
                # Special handling for URL values
                elif isinstance(value, dict) and '__url_value__' in value:
                    # Extract the URL value and ensure it's properly quoted
                    url_value = value['__url_value__']
                    conditions.append(f"{field} {op} {escape_literal(url_value)}")
                else:
                    # Convert value to database format if we have field information
                    db_value = self._convert_value_for_query(field, value)
                    # Always use escape_literal to ensure proper escaping of all values
                    # This is especially important for URLs, strings with special characters, Expr vars, and RecordIDs
                    conditions.append(f"{field} {op} {escape_literal(db_value)}")
        return conditions

    def _convert_value_for_query(self, field_name: str, value: Any) -> Any:
        """Convert a value to its database representation for query conditions.
        
        This method checks if the document class has a field definition for the given
        field name and uses its to_db() method to convert the value properly.
        
        Args:
            field_name: The name of the field
            value: The value to convert
            
        Returns:
            The converted value ready for JSON serialization
        """
        # Check if we have a document class with field definitions
        document_class = getattr(self, 'document_class', None)
        if document_class and hasattr(document_class, '_fields'):
            # Get the field definition
            field_obj = document_class._fields.get(field_name)
            if field_obj and hasattr(field_obj, 'to_db'):
                # Use the field's to_db method to convert the value
                try:
                    return field_obj.to_db(value)
                except Exception:
                    # If conversion fails, return the original value
                    pass
        
        # If no field definition or conversion failed, return original value
        return value

    def _format_record_id(self, id_value: Any) -> str:
        """Format an ID value into a proper SurrealDB record ID.
        
        This method handles various RecordID formats including URL-encoded versions.
        
        Args:
            id_value: The ID value to format
            
        Returns:
            Properly formatted record ID string
        """
        # Get table name if available
        table_name = None
        if hasattr(self, 'document_class') and self.document_class:
            table_name = self.document_class._get_collection_name()
        
        # Use RecordIdUtils for comprehensive handling
        normalized = RecordIdUtils.normalize_record_id(id_value, table_name)
        
        # If normalization succeeded, return it
        if normalized is not None:
            return normalized
            
        # Fall back to original behavior if normalization fails
        if isinstance(id_value, str) and ':' in id_value:
            return id_value
        elif isinstance(id_value, RecordID):
            return str(id_value)
        elif table_name:
            return f"{table_name}:{id_value}"
        else:
            return str(id_value)
    
    def _build_direct_record_query(self) -> Optional[str]:
        """Build optimized direct record access query if applicable.
        
        Returns:
            Optimized query string or None if not applicable
        """
        # Handle bulk ID selection optimization
        if self._bulk_id_selection:
            if not self._bulk_id_selection:  # Empty list
                return None
            
            record_ids = [self._format_record_id(id_val) for id_val in self._bulk_id_selection]
            query = f"SELECT * FROM {', '.join(record_ids)}"
            
            # Add other clauses (but skip WHERE since we're using direct access)
            clauses = self._build_clauses()
            for clause_name, clause_sql in clauses.items():
                if clause_name != 'WHERE':  # Skip WHERE for direct access
                    query += f" {clause_sql}"
            
            return query
            
        # Handle ID range selection optimization  
        if self._id_range_selection:
            start_id, end_id, inclusive = self._id_range_selection
            
            start_record_id = self._format_record_id(start_id)
            end_record_id = self._format_record_id(end_id)
            
            # Extract just the numeric part for range syntax
            collection_name = getattr(self, 'document_class', None)
            if collection_name:
                collection_name = collection_name._get_collection_name()
                
                # Extract numeric IDs from record IDs
                start_num = str(start_id).split(':')[-1] if ':' in str(start_id) else str(start_id)
                end_num = str(end_id).split(':')[-1] if ':' in str(end_id) else str(end_id)
                
                range_op = "..=" if inclusive else ".."
                query = f"SELECT * FROM {collection_name}:{start_num}{range_op}{end_num}"
            else:
                # Fall back to WHERE clause if we can't determine collection
                return None
            
            # Add other clauses (but skip WHERE since we're using direct access)
            clauses = self._build_clauses()
            for clause_name, clause_sql in clauses.items():
                if clause_name != 'WHERE':  # Skip WHERE for direct access
                    query += f" {clause_sql}"
            
            return query
            
        return None

    def _build_clauses(self) -> Dict[str, str]:
        """Build query clauses from the query parameters.

        This method builds the various clauses for the query string, including
        WHERE, GROUP BY, SPLIT, WITH, ORDER BY, LIMIT, START, and FETCH.

        Returns:
            Dictionary of clause names and their string representations
        """
        clauses = {}

        # Build WHERE clause
        if self.query_parts:
            conditions = self._build_conditions()
            clauses['WHERE'] = f"WHERE {' AND '.join(conditions)}"

        # Build GROUP BY clause
        if self.group_by_fields:
            clauses['GROUP BY'] = f"GROUP BY {', '.join(self.group_by_fields)}"

        # Build SPLIT clause
        if self.split_fields:
            clauses['SPLIT'] = f"SPLIT {', '.join(self.split_fields)}"

        # Build WITH clause
        if self.with_index:
            clauses['WITH'] = f"WITH INDEX {self.with_index}"

        # Build ORDER BY clause
        if self.order_by_value:
            field, direction = self.order_by_value
            clauses['ORDER BY'] = f"ORDER BY {field} {direction}"

        # Build LIMIT clause
        if self.limit_value is not None:
            clauses['LIMIT'] = f"LIMIT {self.limit_value}"

        # Build START clause
        if self.start_value is not None:
            clauses['START'] = f"START {self.start_value}"

        # IMPORTANT: In SurrealQL, FETCH must be the last clause
        if self.fetch_fields:
            clauses['FETCH'] = f"FETCH {', '.join(self.fetch_fields)}"

        return clauses
    
    def _get_collection_name(self) -> Optional[str]:
        """Get the collection name for this queryset.
        
        Returns:
            Collection name or None if not available
        """
        document_class = getattr(self, 'document_class', None)
        if document_class and hasattr(document_class, '_get_collection_name'):
            return document_class._get_collection_name()
        return getattr(self, 'table_name', None)

    async def all(self) -> List[Any]:
        """Execute the query and return all results asynchronously.

        This method must be implemented by subclasses to execute the query
        and return the results.

        Returns:
            List of results

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement all")

    def all_sync(self) -> List[Any]:
        """Execute the query and return all results synchronously.

        This method must be implemented by subclasses to execute the query
        and return the results.

        Returns:
            List of results

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement all_sync")

    async def first(self) -> Optional[Any]:
        """Execute the query and return the first result asynchronously.

        This method limits the query to one result and returns the first item
        or None if no results are found.

        Returns:
            The first result or None if no results
        """
        self.limit_value = 1
        results = await self.all()
        return results[0] if results else None

    def first_sync(self) -> Optional[Any]:
        """Execute the query and return the first result synchronously.

        This method limits the query to one result and returns the first item
        or None if no results are found.

        Returns:
            The first result or None if no results
        """
        self.limit_value = 1
        results = self.all_sync()
        return results[0] if results else None

    async def get(self, **kwargs) -> Any:
        """Get a single document matching the query asynchronously.

        This method applies filters and ensures that exactly one document is returned.
        For ID-based lookups, it uses direct record syntax instead of WHERE clause.

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
            # If it's already a full record ID (table:id format)
            if isinstance(id_value, str) and ':' in id_value:
                query = f"SELECT * FROM {id_value}"
            else:
                # Get table name from document class if available
                table_name = getattr(self, 'document_class', None)
                if table_name:
                    table_name = table_name._get_collection_name()
                else:
                    table_name = getattr(self, 'table_name', None)

                if table_name:
                    query = f"SELECT * FROM {table_name}:{id_value}"
                else:
                    # Fall back to regular filtering if we can't determine the table
                    return await self._get_with_filters(**kwargs)

            result = await self.connection.client.query(query)
            if not result or not result[0]:
                raise DoesNotExist(f"Object with ID '{id_value}' does not exist.")
            return result[0][0]

        # For non-ID lookups, use regular filtering
        return await self._get_with_filters(**kwargs)

    def get_sync(self, **kwargs) -> Any:
        """Get a single document matching the query synchronously.

        This method applies filters and ensures that exactly one document is returned.
        For ID-based lookups, it uses direct record syntax instead of WHERE clause.

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
            # If it's already a full record ID (table:id format)
            if isinstance(id_value, str) and ':' in id_value:
                query = f"SELECT * FROM {id_value}"
            else:
                # Get table name from document class if available
                table_name = getattr(self, 'document_class', None)
                if table_name:
                    table_name = table_name._get_collection_name()
                else:
                    table_name = getattr(self, 'table_name', None)

                if table_name:
                    query = f"SELECT * FROM {table_name}:{id_value}"
                else:
                    # Fall back to regular filtering if we can't determine the table
                    return self._get_with_filters_sync(**kwargs)

            result = self.connection.client.query(query)
            if not result or not result[0]:
                raise DoesNotExist(f"Object with ID '{id_value}' does not exist.")
            return result[0][0]

        # For non-ID lookups, use regular filtering
        return self._get_with_filters_sync(**kwargs)

    async def _get_with_filters(self, **kwargs) -> Any:
        """Internal method to get a single document using filters asynchronously.

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
            raise DoesNotExist(f"Object matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned(f"Multiple objects returned instead of one")

        return results[0]

    def _get_with_filters_sync(self, **kwargs) -> Any:
        """Internal method to get a single document using filters synchronously.

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
        results = self.all_sync()

        if not results:
            raise DoesNotExist(f"Object matching query does not exist.")
        if len(results) > 1:
            raise MultipleObjectsReturned(f"Multiple objects returned instead of one")

        return results[0]

    async def count(self) -> int:
        """Count documents matching the query asynchronously.

        This method must be implemented by subclasses to count the number
        of documents matching the query.

        Returns:
            Number of matching documents

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement count")

    def count_sync(self) -> int:
        """Count documents matching the query synchronously.

        This method must be implemented by subclasses to count the number
        of documents matching the query.

        Returns:
            Number of matching documents

        Raises:
            NotImplementedError: If not implemented by a subclass
        """
        raise NotImplementedError("Subclasses must implement count_sync")

    def __await__(self):
        """Make the queryset awaitable.

        This method allows the queryset to be used with the await keyword,
        which will execute the query and return all results.

        Returns:
            Awaitable that resolves to the query results
        """
        return self.all().__await__()

    def page(self, number: int, size: int) -> 'BaseQuerySet':
        """Set pagination parameters using page number and size.

        This method calculates the appropriate LIMIT and START values
        based on the page number and size, providing a more convenient
        way to paginate results.

        Args:
            number: Page number (1-based, first page is 1)
            size: Number of items per page

        Returns:
            The query set instance for method chaining
        """
        if number < 1:
            raise ValueError("Page number must be 1 or greater")
        if size < 1:
            raise ValueError("Page size must be 1 or greater")

        self.limit_value = size
        self.start_value = (number - 1) * size
        return self

    async def paginate(self, page: int, per_page: int) -> PaginationResult:
        """Get a page of results with pagination metadata asynchronously.

        This method gets a page of results along with metadata about the
        pagination, such as the total number of items, the number of pages,
        and whether there are next or previous pages.

        Args:
            page: The page number (1-based)
            per_page: The number of items per page

        Returns:
            A PaginationResult containing the items and pagination metadata
        """
        # Get the total count
        total = await self.count()

        # Get the items for the current page
        items = await self.page(page, per_page).all()

        # Return a PaginationResult
        return PaginationResult(items, page, per_page, total)

    def paginate_sync(self, page: int, per_page: int) -> PaginationResult:
        """Get a page of results with pagination metadata synchronously.

        This method gets a page of results along with metadata about the
        pagination, such as the total number of items, the number of pages,
        and whether there are next or previous pages.

        Args:
            page: The page number (1-based)
            per_page: The number of items per page

        Returns:
            A PaginationResult containing the items and pagination metadata
        """
        # Get the total count
        total = self.count_sync()

        # Get the items for the current page
        items = self.page(page, per_page).all_sync()

        # Return a PaginationResult
        return PaginationResult(items, page, per_page, total)

    def get_raw_query(self) -> str:
        """Get the raw query string without executing it.

        This method builds and returns the query string without executing it.
        It can be used to get the raw query for manual execution or debugging.

        Returns:
            The raw query string
        """
        return self._build_query()

    def aggregate(self):
        """Create an aggregation pipeline from this query.

        This method returns an AggregationPipeline instance that can be used
        to build and execute complex aggregation queries with multiple stages.

        Returns:
            An AggregationPipeline instance for building and executing
            aggregation queries.
        """
        from .aggregation import AggregationPipeline
        return AggregationPipeline(self)

    def _clone(self) -> 'BaseQuerySet':
        """Create a new instance of the queryset with the same parameters.

        This method creates a new instance of the same class as the current
        instance and copies all the relevant attributes.

        Returns:
            A new queryset instance with the same parameters
        """
        # Create a new instance of the same class
        if hasattr(self, 'document_class'):
            # For QuerySet subclass
            clone = self.__class__(self.document_class, self.connection)
        elif hasattr(self, 'table_name'):
            # For SchemalessQuerySet subclass
            clone = self.__class__(self.table_name, self.connection)
        else:
            # For BaseQuerySet or other subclasses
            clone = self.__class__(self.connection)

        # Copy all the query parameters
        clone.query_parts = self.query_parts.copy()
        clone.limit_value = self.limit_value
        clone.start_value = self.start_value
        clone.order_by_value = self.order_by_value
        clone.group_by_fields = self.group_by_fields.copy()
        clone.split_fields = self.split_fields.copy()
        clone.fetch_fields = self.fetch_fields.copy()
        clone.with_index = self.with_index
        clone.select_fields = self.select_fields
        # Copy performance optimization attributes
        clone._bulk_id_selection = self._bulk_id_selection
        clone._id_range_selection = self._id_range_selection
        clone._prefer_direct_access = self._prefer_direct_access
        # Copy traversal state
        clone._traversal_path = self._traversal_path
        clone._traversal_unique = self._traversal_unique
        clone._traversal_max_depth = self._traversal_max_depth

        return clone
