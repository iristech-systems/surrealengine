import json


class GraphQuery:
    """Helper for complex graph queries."""

    def __init__(self, connection):
        self.connection = connection
        self.query_parts = []

    def start_from(self, document_class, **filters):
        """Set the starting point for the graph query."""
        self.start_class = document_class
        self.start_filters = filters
        return self

    def traverse(self, path_spec):
        """Define a traversal path."""
        self.path_spec = path_spec
        return self

    def end_at(self, document_class=None):
        """Set the end point document type."""
        self.end_class = document_class
        return self

    def filter_results(self, **filters):
        """Add filters to the end results."""
        self.end_filters = filters
        return self

    async def execute(self):
        """Execute the graph query."""
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
                    start_conditions.append(f"{field} = {json.dumps(value)}")

                if start_conditions:
                    path_query += f"({collection} WHERE {' AND '.join(start_conditions)})"
                else:
                    path_query += f"{collection}"

                where_clauses.append(path_query)
            else:
                for field, value in self.start_filters.items():
                    where_clauses.append(f"{field} = {json.dumps(value)}")

        # Add end filters
        if hasattr(self, 'end_filters') and self.end_filters:
            for field, value in self.end_filters.items():
                where_clauses.append(f"{field} = {json.dumps(value)}")

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