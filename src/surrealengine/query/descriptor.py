from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast
from ..connection import ConnectionRegistry
from ..context import get_active_connection
from .base import QuerySet
from ..pagination import PaginationResult


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

    def using(self, connection: Any) -> 'QuerySet':
        """Create a QuerySet using the specified connection.

        This allows switching connections (e.g. to a RawSurrealConnection)
        directly from the manager.

        Args:
            connection: The connection instance to use.

        Returns:
            A QuerySet using the specified connection.
        """
        return QuerySet(self.owner, connection)

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
        # Don't set a default connection here, let each method get the appropriate connection
        self.connection = None
        return self

    def __call__(self, query=None, limit: Optional[int] = None, start: Optional[int] = None,
                       page: Optional[tuple] = None, **kwargs: Any) -> Union[List[Any], Any]:
        """Allow direct filtering through call syntax.

        Polyglot method: executes synchronously if the active connection is synchronous,
        otherwise returns an awaitable.

        Args:
            query: Q object or QueryExpression for complex queries
            limit: Maximum number of results to return (for pagination)
            start: Number of results to skip (for pagination)
            page: Tuple of (page_number, page_size) for pagination
            **kwargs: Field names and values to filter by

        Returns:
            List of matching documents (or awaitable resolving to it)
        """
        # Get the connection (implicit context or default async)
        # Note: We default to async_mode=True if no context is found, preserving backward compatibility
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        
        # Apply query object if provided
        if query is not None:
            queryset = queryset.filter(query)
        
        # Apply filters and pagination
        if kwargs:
            queryset = queryset.filter(**kwargs)

        if page is not None:
            page_number, page_size = page
            queryset = queryset.page(page_number, page_size)
        else:
            if limit is not None:
                queryset = queryset.limit(limit)
            if start is not None:
                queryset = queryset.start(start)

        # Return results using Polyglot .all()
        return queryset.all()

    def call_sync(self, query=None, limit: Optional[int] = None, start: Optional[int] = None,
                  page: Optional[tuple] = None, **kwargs: Any) -> List[Any]:
        """Allow direct filtering through call syntax synchronously.

        This method allows calling the descriptor directly with filters or query objects
        to query the document class. It supports pagination through limit and start parameters
        or the page parameter.

        Args:
            query: Q object or QueryExpression for complex queries
            limit: Maximum number of results to return (for pagination)
            start: Number of results to skip (for pagination)
            page: Tuple of (page_number, page_size) for pagination
            **kwargs: Field names and values to filter by

        Returns:
            List of matching documents
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        
        # Apply query object if provided
        if query is not None:
            queryset = queryset.filter(query)
        
        # Apply filters and pagination
        if kwargs:
            queryset = queryset.filter(**kwargs)

        if page is not None:
            page_number, page_size = page
            queryset = queryset.page(page_number, page_size)
        else:
            if limit is not None:
                queryset = queryset.limit(limit)
            if start is not None:
                queryset = queryset.start(start)

        # Return results
        return queryset.all_sync()

    def get(self, **kwargs: Any) -> Union[Any, Any]:
        """Allow direct get operation.

        Polyglot method: executes synchronously if the active connection is synchronous,
        otherwise returns an awaitable.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document (or awaitable resolving to it)

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.get(**kwargs)

    def get_sync(self, **kwargs: Any) -> Any:
        """Allow direct get operation asynchronously.

        This method allows getting a single document matching the given filters.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.get_sync(**kwargs)


    def update(self, returning: Optional[str] = None, **kwargs: Any) -> Union[List[Any], Any]:
        """Update all documents in the collection.

        Polyglot method: executes synchronously if the active connection is synchronous,
        otherwise returns an awaitable.

        WARNING: This updates ALL documents in the collection if no filters are applied
        (which is always the case when calling objects.update()).

        Args:
            returning: Return policy ('before', 'after', 'diff', or None)
            **kwargs: Field names and values to update

        Returns:
            List of updated documents (or awaitable resolving to it)
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.update(returning=returning, **kwargs)

    def update_sync(self, returning: Optional[str] = None, **kwargs: Any) -> List[Any]:
        """Update all documents in the collection synchronously.

        WARNING: This updates ALL documents in the collection if no filters are applied
        (which is always the case when calling objects.update()).

        Args:
            returning: Return policy ('before', 'after', 'diff', or None)
            **kwargs: Field names and values to update

        Returns:
            List of updated documents
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.update_sync(returning=returning, **kwargs)

    def delete(self) -> Union[int, Any]:
        """Delete all documents in the collection.

        Polyglot method: executes synchronously if the active connection is synchronous,
        otherwise returns an awaitable.

        WARNING: This deletes ALL documents in the collection.

        Returns:
            Number of deleted documents (or awaitable resolving to it)
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.delete()

    def delete_sync(self) -> int:
        """Delete all documents in the collection synchronously.

        WARNING: This deletes ALL documents in the collection.

        Returns:
            Number of deleted documents
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.delete_sync()

    def filter(self, query=None, **kwargs: Any) -> QuerySet:
        """Create a QuerySet with filters using the default async connection.

        This method creates a new QuerySet with the given filters using the default async connection.

        Args:
            query: Q object or QueryExpression for complex queries
            **kwargs: Field names and values to filter by

        Returns:
            A QuerySet with the given filters
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.filter(query=query, **kwargs)

    def filter_sync(self, query=None, **kwargs: Any) -> QuerySet:
        """Create a QuerySet with filters using the default sync connection.

        This method creates a new QuerySet with the given filters using the default sync connection.

        Args:
            query: Q object or QueryExpression for complex queries
            **kwargs: Field names and values to filter by

        Returns:
            A QuerySet with the given filters
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.filter(query=query, **kwargs)

    def limit(self, value: int) -> QuerySet:
        """Set the maximum number of results to return.

        Args:
            value: Maximum number of results

        Returns:
            A QuerySet with the limit applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.limit(value)

    def limit_sync(self, value: int) -> QuerySet:
        """Set the maximum number of results to return using the default sync connection.

        Args:
            value: Maximum number of results

        Returns:
            A QuerySet with the limit applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.limit(value)

    def traverse(self, path: str, max_depth: Optional[int] = None, unique: bool = True) -> QuerySet:
        """Configure a graph traversal for this query using the default async connection.

        Args:
            path: Arrow path segment(s), e.g. "->likes->user" or "<-follows".
            max_depth: Optional bound for depth.
            unique: When True, deduplicate results via GROUP BY id.

        Returns:
            A QuerySet configured with traversal.
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.traverse(path, max_depth, unique)

    def traverse_sync(self, path: str, max_depth: Optional[int] = None, unique: bool = True) -> QuerySet:
        """Configure a graph traversal for this query using the default sync connection.

        Args:
            path: Arrow path segment(s), e.g. "->likes->user" or "<-follows".
            max_depth: Optional bound for depth.
            unique: When True, deduplicate results via GROUP BY id.

        Returns:
            A QuerySet configured with traversal.
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.traverse(path, max_depth, unique)

    def out(self, target: Union[str, Type, None] = None) -> QuerySet:
        """Traverse outgoing edges or nodes using the default async connection.
        
        Args:
            target: The relation or document class to traverse to, or a string table name.
        
        Returns:
            A QuerySet with the traversal appended.
        """
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.out(target)

    def out_sync(self, target: Union[str, Type, None] = None) -> QuerySet:
        """Traverse outgoing edges or nodes using the default sync connection.
        
        Args:
            target: The relation or document class to traverse to, or a string table name.
        
        Returns:
            A QuerySet with the traversal appended.
        """
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.out(target)

    def in_(self, target: Union[str, Type, None] = None) -> QuerySet:
        """Traverse incoming edges or nodes using the default async connection.
        
        Args:
            target: The relation or document class to traverse from, or a string table name.
        
        Returns:
            A QuerySet with the traversal appended.
        """
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.in_(target)

    def in_sync(self, target: Union[str, Type, None] = None) -> QuerySet:
        """Traverse incoming edges or nodes using the default sync connection.
        
        Args:
            target: The relation or document class to traverse from, or a string table name.
        
        Returns:
            A QuerySet with the traversal appended.
        """
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.in_(target)

    def both(self, target: Union[str, Type, None] = None) -> QuerySet:
        """Traverse both incoming and outgoing edges or nodes using the default async connection.
        
        Args:
            target: The relation or document class to traverse, or a string table name.
        
        Returns:
            A QuerySet with the traversal appended.
        """
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.both(target)

    def both_sync(self, target: Union[str, Type, None] = None) -> QuerySet:
        """Traverse both incoming and outgoing edges or nodes using the default sync connection.
        
        Args:
            target: The relation or document class to traverse, or a string table name.
        
        Returns:
            A QuerySet with the traversal appended.
        """
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.both(target)

    def shortest_path(self, src: Union[str, Any], dst: Union[str, Any], edge: str) -> QuerySet:
        """Helper for shortest path queries using the default async connection.

        Args:
            src: Source record ID or string
            dst: Destination record ID or string
            edge: Edge name to traverse

        Returns:
            A QuerySet configured for shortest path (if supported).
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.shortest_path(src, dst, edge)

    def shortest_path_sync(self, src: Union[str, Any], dst: Union[str, Any], edge: str) -> QuerySet:
        """Helper for shortest path queries using the default sync connection.

        Args:
            src: Source record ID or string
            dst: Destination record ID or string
            edge: Edge name to traverse

        Returns:
            A QuerySet configured for shortest path (if supported).
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.shortest_path(src, dst, edge)

    def with_index(self, index: str) -> QuerySet:
        """Use the specified index for the query using the default async connection.

        Args:
            index: Name of the index to use

        Returns:
            A QuerySet with the index applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.with_index(index)

    def with_index_sync(self, index: str) -> QuerySet:
        """Use the specified index for the query using the default sync connection.

        Args:
            index: Name of the index to use

        Returns:
            A QuerySet with the index applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.with_index(index)

    def no_index(self) -> QuerySet:
        """Do not use any index for the query using the default async connection.

        Returns:
            A QuerySet with the NOINDEX clause applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.no_index()

    def no_index_sync(self) -> QuerySet:
        """Do not use any index for the query using the default sync connection.

        Returns:
            A QuerySet with the NOINDEX clause applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.no_index()

    def live(self, *args, **kwargs):
        """Subscribe to changes on this table via LIVE queries as an async generator.

        This method delegates to QuerySet.live().

        Returns:
            An async generator yielding LiveEvent objects
        """
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.live(*args, **kwargs)

    async def reactive(self) -> 'ReactiveQuerySet':
        """
        Return a ReactiveQuerySet that stays in sync with the database.

        This method initializes a ReactiveQuerySet, which performs an initial fetch
        and then subscribes to live updates to keep the local list current.

        Returns:
            A new ReactiveQuerySet instance.
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.reactive()


    def start(self, value: int) -> QuerySet:
        """Set the number of results to skip (for pagination).

        Args:
            value: Number of results to skip

        Returns:
            A QuerySet with the start applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.start(value)

    def start_sync(self, value: int) -> QuerySet:
        """Set the number of results to skip (for pagination) using the default sync connection.

        Args:
            value: Number of results to skip

        Returns:
            A QuerySet with the start applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.start(value)

    def order_by(self, field: str, direction: str = 'ASC') -> QuerySet:
        """Set the field and direction to order results by.

        Args:
            field: Field name to order by
            direction: Direction to order by ('ASC' or 'DESC')

        Returns:
            A QuerySet with the order by applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.order_by(field, direction)

    def order_by_sync(self, field: str, direction: str = 'ASC') -> QuerySet:
        """Set the field and direction to order results by using the default sync connection.

        Args:
            field: Field name to order by
            direction: Direction to order by ('ASC' or 'DESC')

        Returns:
            A QuerySet with the order by applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.order_by(field, direction)

    def group_by(self, *fields: str) -> QuerySet:
        """Group the results by the specified fields.

        This method sets the fields to group the results by using the GROUP BY clause.

        Args:
            *fields: Field names to group by

        Returns:
            A QuerySet with the group by applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.group_by(*fields)

    def group_by_sync(self, *fields: str) -> QuerySet:
        """Group the results by the specified fields using the default sync connection.

        This method sets the fields to group the results by using the GROUP BY clause.

        Args:
            *fields: Field names to group by

        Returns:
            A QuerySet with the group by applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.group_by(*fields)

    def split(self, *fields: str) -> QuerySet:
        """Split the results by the specified fields.

        This method sets the fields to split the results by using the SPLIT clause.

        Args:
            *fields: Field names to split by

        Returns:
            A QuerySet with the split applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.split(*fields)

    def split_sync(self, *fields: str) -> QuerySet:
        """Split the results by the specified fields using the default sync connection.

        This method sets the fields to split the results by using the SPLIT clause.

        Args:
            *fields: Field names to split by

        Returns:
            A QuerySet with the split applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.split(*fields)

    def fetch(self, *fields: str) -> QuerySet:
        """Fetch related records for the specified fields.

        This method sets the fields to fetch related records for using the FETCH clause.

        Args:
            *fields: Field names to fetch related records for

        Returns:
            A QuerySet with the fetch applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.fetch(*fields)

    def fetch_sync(self, *fields: str) -> QuerySet:
        """Fetch related records for the specified fields using the default sync connection.

        This method sets the fields to fetch related records for using the FETCH clause.

        Args:
            *fields: Field names to fetch related records for

        Returns:
            A QuerySet with the fetch applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.fetch(*fields)

    async def to_arrow(self) -> Any:
        """
        Execute the query and return the results as a PyArrow Table.
        """
        # Use existing connection if set (e.g. via qs.connection = conn hack)
        connection = self.connection or self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.to_arrow()

    async def to_polars(self) -> Any:
        """
        Execute the query and return the results as a Polars DataFrame.
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.to_polars()


    async def first(self) -> Any:
        """Get the first result from the query asynchronously.

        Returns:
            The first matching document or None if no matches

        Raises:
            DoesNotExist: If no matching document is found
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.first()

    def first_sync(self) -> Any:
        """Get the first result from the query synchronously.

        Returns:
            The first matching document or None if no matches

        Raises:
            DoesNotExist: If no matching document is found
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.first_sync()

    def page(self, number: int, size: int) -> QuerySet:
        """Set pagination parameters using page number and size.

        Args:
            number: Page number (1-based, first page is 1)
            size: Number of items per page

        Returns:
            A QuerySet with pagination applied
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.page(number, size)

    def page_sync(self, number: int, size: int) -> QuerySet:
        """Set pagination parameters using page number and size using the default sync connection.

        Args:
            number: Page number (1-based, first page is 1)
            size: Number of items per page

        Returns:
            A QuerySet with pagination applied
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.page(number, size)

    async def paginate(self, page: int, per_page: int) -> 'PaginationResult':
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
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        # Return the paginated results
        return await queryset.paginate(page, per_page)

    def paginate_sync(self, page: int, per_page: int) -> 'PaginationResult':
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
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        # Return the paginated results
        return queryset.paginate_sync(page, per_page)

    def aggregate(self):
        """Create an aggregation pipeline from this query.

        This method returns an AggregationPipeline instance that can be used
        to build and execute complex aggregation queries with multiple stages.

        Returns:
            An AggregationPipeline instance for building and executing
            aggregation queries.
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.aggregate()

    def aggregate_sync(self):
        """Create an aggregation pipeline from this query using the default sync connection.

        This method returns an AggregationPipeline instance that can be used
        to build and execute complex aggregation queries with multiple stages.

        Returns:
            An AggregationPipeline instance for building and executing
            aggregation queries.
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.aggregate()

    async def join(self, field_name: str, target_fields: Optional[List[str]] = None, dereference: bool = True, dereference_depth: int = 1) -> List[Any]:
        """Perform a JOIN-like operation on a reference field.

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
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.join(field_name, target_fields, dereference=dereference, dereference_depth=dereference_depth)

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
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.join_sync(field_name, target_fields, dereference=dereference, dereference_depth=dereference_depth)

    def get_many(self, ids: List[Union[str, Any]]) -> QuerySet:
        """Get multiple records by IDs using optimized direct record access.
        
        This method uses SurrealDB's direct record selection syntax for better
        performance compared to WHERE clause filtering.
        
        Args:
            ids: List of record IDs (can be strings or other ID types)
            
        Returns:
            The query set instance configured for direct record access
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.get_many(ids)

    def get_many_sync(self, ids: List[Union[str, Any]]) -> QuerySet:
        """Get multiple records by IDs using optimized direct record access synchronously.
        
        Args:
            ids: List of record IDs (can be strings or other ID types)
            
        Returns:
            The query set instance configured for direct record access
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.get_many(ids)

    def get_range(self, start_id: Union[str, Any], end_id: Union[str, Any], 
                  inclusive: bool = True) -> QuerySet:
        """Get a range of records by ID using optimized range syntax.
        
        This method uses SurrealDB's range selection syntax for better
        performance compared to WHERE clause filtering.
        
        Args:
            start_id: Starting ID of the range
            end_id: Ending ID of the range  
            inclusive: Whether the range is inclusive (default: True)
            
        Returns:
            The query set instance configured for range access
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.get_range(start_id, end_id, inclusive)

    def get_range_sync(self, start_id: Union[str, Any], end_id: Union[str, Any], 
                       inclusive: bool = True) -> QuerySet:
        """Get a range of records by ID using optimized range syntax synchronously.
        
        Args:
            start_id: Starting ID of the range
            end_id: Ending ID of the range  
            inclusive: Whether the range is inclusive (default: True)
            
        Returns:
            The query set instance configured for range access
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.get_range(start_id, end_id, inclusive)

    async def bulk_create(self, documents: List[Any], batch_size: int = 1000,
                         validate: bool = True, return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation asynchronously.

        This method creates multiple documents in a single operation, processing
        them in batches for better performance.

        Args:
            documents: List of Document instances to create
            batch_size: Number of documents per batch (default: 1000)
            validate: Whether to validate documents (default: True)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.bulk_create(documents, batch_size, validate, return_documents)

    def bulk_create_sync(self, documents: List[Any], batch_size: int = 1000,
                        validate: bool = True, return_documents: bool = True) -> Union[List[Any], int]:
        """Create multiple documents in a single operation synchronously.

        Args:
            documents: List of Document instances to create
            batch_size: Number of documents per batch (default: 1000)
            validate: Whether to validate documents (default: True)
            return_documents: Whether to return created documents (default: True)

        Returns:
            List of created documents with their IDs set if return_documents=True,
            otherwise returns the count of created documents
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.bulk_create_sync(documents, batch_size, validate, return_documents)

    async def all(self) -> List[Any]:
        """Execute the query and return all results asynchronously.
        
        Returns:
            List of all documents matching any implicit query
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.all()

    def all_sync(self) -> List[Any]:
        """Execute the query and return all results synchronously.
        
        Returns:
            List of all documents matching any implicit query
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.all_sync()

    async def count(self) -> int:
        """Count all documents asynchronously.
        
        Returns:
            Number of documents
        """
        # Get the connection (implicit context or default async)
        connection = self.connection or get_active_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.count()

    def count_sync(self) -> int:
        """Count all documents synchronously.
        
        Returns:
            Number of documents
        """
        # Get the connection (implicit context or default sync)
        connection = self.connection or get_active_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.count_sync()
