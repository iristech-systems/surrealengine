import json
from typing import Any, Dict, List, Optional, Type, Union


class GraphQuery:
    """Helper for complex graph queries.

    This class provides a fluent interface for building and executing complex
    graph traversal queries in SurrealDB. It allows defining a starting point,
    traversal path, end point, and filters for the query.

    Attributes:
        connection: The database connection to use for queries
        query_parts: List of query parts
        start_class: The document class to start the traversal from
        start_filters: Filters to apply to the starting documents
        path_spec: The traversal path specification
        end_class: The document class to end the traversal at
        end_filters: Filters to apply to the end results
    """

    def __init__(self, connection: Any) -> None:
        """Initialize a new GraphQuery.

        Args:
            connection: The database connection to use for queries
        """
        self.connection = connection
        self.query_parts: List[Any] = []

    def start_from(self, document_class: Type, **filters: Any) -> 'GraphQuery':
        """Set the starting point for the graph query.

        Args:
            document_class: The document class to start the traversal from
            **filters: Filters to apply to the starting documents

        Returns:
            The GraphQuery instance for method chaining
        """
        self.start_class = document_class
        self.start_filters = filters
        return self

    def traverse(self, path_spec: str) -> 'GraphQuery':
        """Define a traversal path.

        Args:
            path_spec: The traversal path specification, e.g., "->[relation]->"

        Returns:
            The GraphQuery instance for method chaining
        """
        self.path_spec = path_spec
        return self

    def end_at(self, document_class: Optional[Type] = None) -> 'GraphQuery':
        """Set the end point document type.

        Args:
            document_class: The document class to end the traversal at

        Returns:
            The GraphQuery instance for method chaining
        """
        self.end_class = document_class
        return self

    def filter_results(self, **filters: Any) -> 'GraphQuery':
        """Add filters to the end results.

        Args:
            **filters: Filters to apply to the end results

        Returns:
            The GraphQuery instance for method chaining
        """
        self.end_filters = filters
        return self

    async def execute(self) -> List[Any]:
        """Execute the graph query.

        This method builds and executes the graph query based on the components
        defined using the fluent interface methods. It validates that the required
        components are present, builds the query string, executes it, and processes
        the results.

        Returns:
            List of results, either document instances or raw results

        Raises:
            ValueError: If required components are missing
        """
        # Build query based on components
        if not hasattr(self, 'start_class'):
            raise ValueError("Must specify a starting document class with start_from()")

        if not hasattr(self, 'path_spec'):
            raise ValueError("Must specify a traversal path with traverse()")

        # Start with the FROM clause
        collection = self.start_class._get_collection_name()
        query = f"SELECT "

        # Define what to select
        if hasattr(self, 'end_class') and self.end_class:
            end_collection = self.end_class._get_collection_name()
            query += f"* FROM {end_collection}"
            is_end_query = True
        else:
            query += f"{self.path_spec} as path FROM {collection}"
            is_end_query = False

        # Add WHERE clause for start filters
        where_clauses = []
        if hasattr(self, 'start_filters') and self.start_filters:
            if is_end_query:
                path_query = f" WHERE {self.path_spec}"

                # Add start filters
                start_conditions = []
                for field, value in self.start_filters.items():
                    from .surrealql import escape_literal
                    start_conditions.append(f"{field} = {escape_literal(value)}")

                if start_conditions:
                    path_query += f"({collection} WHERE {' AND '.join(start_conditions)})"
                else:
                    path_query += f"{collection}"

                where_clauses.append(path_query)
            else:
                for field, value in self.start_filters.items():
                    from .surrealql import escape_literal
                    where_clauses.append(f"{field} = {escape_literal(value)}")

        # Add end filters
        if hasattr(self, 'end_filters') and self.end_filters:
            for field, value in self.end_filters.items():
                from .surrealql import escape_literal
                where_clauses.append(f"{field} = {escape_literal(value)}")

        # Complete the query
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Execute the query
        result = await self.connection.client.query(query)

        # Process results
        if not result or not result[0]:
            return []

        if is_end_query and hasattr(self, 'end_class'):
            # Return document instances
            return [self.end_class.from_db(doc) for doc in result[0]]
        else:
            # Return raw results
            return result[0]
