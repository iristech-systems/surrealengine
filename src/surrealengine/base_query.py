import json
from typing import Any, Dict, List, Optional, Tuple, Union, Type, cast
from .exceptions import MultipleObjectsReturned, DoesNotExist
from surrealdb import RecordID
from .pagination import PaginationResult

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

    def is_async_connection(self) -> bool:
        """Check if the connection is asynchronous.

        Returns:
            True if the connection is asynchronous, False otherwise
        """
        SurrealEngineAsyncConnection, SurrealEngineSyncConnection = _get_connection_classes()
        return isinstance(self.connection, SurrealEngineAsyncConnection)

    def filter(self, **kwargs) -> 'BaseQuerySet':
        """Add filter conditions to the query.

        This method supports Django-style field lookups with double-underscore operators:
        - field__gt: Greater than
        - field__lt: Less than
        - field__gte: Greater than or equal
        - field__lte: Less than or equal
        - field__ne: Not equal
        - field__in: Inside (for arrays)
        - field__nin: Not inside (for arrays)
        - field__contains: Contains (for strings or arrays)
        - field__startswith: Starts with (for strings)
        - field__endswith: Ends with (for strings)
        - field__regex: Matches regex pattern (for strings)

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The query set instance for method chaining

        Raises:
            ValueError: If an unknown operator is provided
        """
        for k, v in kwargs.items():
            if k == 'id':
                if isinstance(v, RecordID):
                    self.query_parts.append((k, '=', str(v)))
                elif isinstance(v, str) and ':' in v:
                    # Handle full record ID format (collection:id)
                    self.query_parts.append((k, '=', v))
                else:
                    # Handle short ID format by prefixing with collection name
                    collection = getattr(self, 'document_class', None)
                    if collection:
                        full_id = f"{collection._get_collection_name()}:{v}"
                        self.query_parts.append((k, '=', full_id))
                    else:
                        self.query_parts.append((k, '=', v))
                continue

            parts = k.split('__')
            field = parts[0]

            # Handle operators
            if len(parts) > 1:
                op = parts[1]
                if op == 'gt':
                    self.query_parts.append((field, '>', v))
                elif op == 'lt':
                    self.query_parts.append((field, '<', v))
                elif op == 'gte':
                    self.query_parts.append((field, '>=', v))
                elif op == 'lte':
                    self.query_parts.append((field, '<=', v))
                elif op == 'ne':
                    self.query_parts.append((field, '!=', v))
                elif op == 'in':
                    self.query_parts.append((field, 'INSIDE', v))
                elif op == 'nin':
                    self.query_parts.append((field, 'NOT INSIDE', v))
                elif op == 'contains':
                    if isinstance(v, str):
                        self.query_parts.append((f"string::contains({field}, '{v}')", '=', True))
                    else:
                        self.query_parts.append((field, 'CONTAINS', v))
                elif op == 'startswith':
                    self.query_parts.append((f"string::startsWith({field}, '{v}')", '=', True))
                elif op == 'endswith':
                    self.query_parts.append((f"string::endsWith({field}, '{v}')", '=', True))
                elif op == 'regex':
                    self.query_parts.append((f"string::matches({field}, r'{v}')", '=', True))
                else:
                    raise ValueError(f"Unknown operator: {op}")
            else:
                # Simple equality
                self.query_parts.append((field, '=', v))

        return self

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
            # Handle special cases
            if op == '=' and isinstance(field, str) and '::' in field:
                conditions.append(f"{field}")
            else:
                # Special handling for RecordIDs - don't quote them
                if field == 'id' and isinstance(value, str) and ':' in value:
                    conditions.append(f"{field} {op} {value}")
                # Special handling for INSIDE and NOT INSIDE operators
                elif isinstance(value, RecordID) or (isinstance(value, str) and ':' in field):
                    conditions.append(f"{field} {op} {value}")
                elif op in ('INSIDE', 'NOT INSIDE'):
                    value_str = json.dumps(value)
                    conditions.append(f"{field} {op} {value_str}")
                else:
                    conditions.append(f"{field} {op} {json.dumps(value)}")
        return conditions

    def _build_clauses(self) -> Dict[str, str]:
        """Build query clauses from the query parameters.

        This method builds the various clauses for the query string, including
        WHERE, GROUP BY, SPLIT, FETCH, WITH, ORDER BY, LIMIT, and START.

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

        # Build FETCH clause
        if self.fetch_fields:
            clauses['FETCH'] = f"FETCH {', '.join(self.fetch_fields)}"

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

        return clauses

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
