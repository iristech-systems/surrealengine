import json
from typing import Any, Dict, List, Optional, Type, Union
from .exceptions import DoesNotExist, MultipleObjectsReturned
from surrealdb import RecordID
from .base_query import BaseQuerySet

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
        """Execute the query and return all results.

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



    async def get(self, **kwargs: Any) -> Any:
        """Get a single document matching the query.

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
        return query


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

    async def create_index(self, index_name: str, fields: List[str], unique: bool = False,
                           search: bool = False, analyzer: Optional[str] = None,
                           comment: Optional[str] = None) -> None:
        """Create an index on this table.

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
        await self.connection.client.query(query)

    @property
    def objects(self) -> SchemalessQuerySet:
        """Get a query set for this table.

        Returns:
            A SchemalessQuerySet for querying this table
        """
        return SchemalessQuerySet(self.name, self.connection)

    async def __call__(self, **kwargs: Any) -> List[Any]:
        """Query the table with filters.

        This method allows calling the table instance directly with filters
        to query the table. It returns the results as SimpleNamespace objects
        if they aren't already Document instances.

        Args:
            **kwargs: Field names and values to filter by

        Returns:
            List of results, either document instances or SimpleNamespace objects
        """
        queryset = SchemalessQuerySet(self.name, self.connection)
        results = await queryset.filter(**kwargs).all()

        # Convert results to SimpleNamespace objects if they aren't already Document instances
        if results and not hasattr(results[0], '_data'):  # Check if it's not a Document instance
            from types import SimpleNamespace
            results = [SimpleNamespace(**result) if isinstance(result, dict) else result
                       for result in results]

        return results


class SurrealEngine:
    """Dynamic database accessor.

    This class provides dynamic access to tables in the database without
    requiring predefined schemas. It allows accessing tables as attributes
    of the instance.

    Attributes:
        connection: The database connection to use for queries
    """

    def __init__(self, connection: Any) -> None:
        """Initialize a new SurrealEngine.

        Args:
            connection: The database connection to use for queries
        """
        self.connection = connection

    def __getattr__(self, name: str) -> SchemalessTable:
        """Get a table accessor for the given table name.

        This method allows accessing tables as attributes of the instance.

        Args:
            name: The name of the table

        Returns:
            A SchemalessTable for accessing the table
        """
        return SchemalessTable(name, self.connection)
