from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast
from surrealengine.connection import ConnectionRegistry
from .base import QuerySet


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
        # Don't set a default connection here, let each method get the appropriate connection
        self.connection = None
        return self

    async def __call__(self, **kwargs: Any) -> List[Any]:
        """Allow direct filtering through call syntax asynchronously.

        This method allows calling the descriptor directly with filters
        to query the document class.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            List of matching documents
        """
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        # Apply filters and return results
        return await queryset.filter(**kwargs).all()

    def call_sync(self, **kwargs: Any) -> List[Any]:
        """Allow direct filtering through call syntax synchronously.

        This method allows calling the descriptor directly with filters
        to query the document class.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            List of matching documents
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        # Apply filters and return results
        return queryset.filter(**kwargs).all_sync()

    async def get(self, **kwargs: Any) -> Any:
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
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.get(**kwargs)

    def get_sync(self, **kwargs: Any) -> Any:
        """Allow direct get operation synchronously.

        This method allows getting a single document matching the given filters.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            The matching document

        Raises:
            DoesNotExist: If no matching document is found
            MultipleObjectsReturned: If multiple matching documents are found
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.get_sync(**kwargs)

    def filter(self, **kwargs: Any) -> QuerySet:
        """Create a QuerySet with filters using the default async connection.

        This method creates a new QuerySet with the given filters using the default async connection.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            A QuerySet with the given filters
        """
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.filter(**kwargs)

    def filter_sync(self, **kwargs: Any) -> QuerySet:
        """Create a QuerySet with filters using the default sync connection.

        This method creates a new QuerySet with the given filters using the default sync connection.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            A QuerySet with the given filters
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.filter(**kwargs)

    def limit(self, value: int) -> QuerySet:
        """Set the maximum number of results to return.

        Args:
            value: Maximum number of results

        Returns:
            A QuerySet with the limit applied
        """
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.limit(value)

    def limit_sync(self, value: int) -> QuerySet:
        """Set the maximum number of results to return using the default sync connection.

        Args:
            value: Maximum number of results

        Returns:
            A QuerySet with the limit applied
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.limit(value)

    def start(self, value: int) -> QuerySet:
        """Set the number of results to skip (for pagination).

        Args:
            value: Number of results to skip

        Returns:
            A QuerySet with the start applied
        """
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return queryset.start(value)

    def start_sync(self, value: int) -> QuerySet:
        """Set the number of results to skip (for pagination) using the default sync connection.

        Args:
            value: Number of results to skip

        Returns:
            A QuerySet with the start applied
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
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
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
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
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
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
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
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
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
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
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
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
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
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
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
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
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.fetch(*fields)

    async def first(self) -> Any:
        """Get the first result from the query asynchronously.

        Returns:
            The first matching document or None if no matches

        Raises:
            DoesNotExist: If no matching document is found
        """
        # Get the default async connection
        connection = ConnectionRegistry.get_default_connection(async_mode=True)
        queryset = QuerySet(self.owner, connection)
        return await queryset.first()

    def first_sync(self) -> Any:
        """Get the first result from the query synchronously.

        Returns:
            The first matching document or None if no matches

        Raises:
            DoesNotExist: If no matching document is found
        """
        # Get the default sync connection
        connection = ConnectionRegistry.get_default_connection(async_mode=False)
        queryset = QuerySet(self.owner, connection)
        return queryset.first_sync()