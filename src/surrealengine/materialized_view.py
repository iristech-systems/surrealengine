"""Materialized views for SurrealEngine.

This module provides support for materialized views in SurrealEngine.
Materialized views are precomputed views of data that can be used to
improve query performance for frequently accessed aggregated data.
"""
from __future__ import annotations  # Enable string-based type annotations
from typing import Any, Dict, List, Optional, Type, Union, TYPE_CHECKING, Callable

# Remove the direct import of Document
# from .document import Document
from .query import QuerySet
from .connection import ConnectionRegistry


class Aggregation:
    """Base class for aggregation functions.

    This class represents an aggregation function that can be used in a materialized view.
    Subclasses should implement the __str__ method to return the SurrealQL representation
    of the aggregation function.
    """

    def __init__(self, field: str = None):
        """Initialize a new Aggregation.

        Args:
            field: The field to aggregate (optional)
        """
        self.field = field

    def __str__(self) -> str:
        """Return the SurrealQL representation of the aggregation function."""
        raise NotImplementedError("Subclasses must implement __str__")


class Count(Aggregation):
    """Count aggregation function.

    This class represents the count() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the count function."""
        return "count()"


class Mean(Aggregation):
    """Mean aggregation function.

    This class represents the math::mean() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the mean function."""
        if self.field:
            return f"math::mean({self.field})"
        return "math::mean()"


class Sum(Aggregation):
    """Sum aggregation function.

    This class represents the math::sum() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the sum function."""
        if self.field:
            return f"math::sum({self.field})"
        return "math::sum()"


class Min(Aggregation):
    """Min aggregation function.

    This class represents the math::min() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the min function."""
        if self.field:
            return f"math::min({self.field})"
        return "math::min()"


class Max(Aggregation):
    """Max aggregation function.

    This class represents the math::max() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the max function."""
        if self.field:
            return f"math::max({self.field})"
        return "math::max()"


class ArrayGroup(Aggregation):
    """Array group aggregation function.

    This class represents the array::group() aggregation function in SurrealQL v2.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the array group function."""
        if self.field:
            return f"array::group({self.field})"
        return "array::group()"

# Backwards-compat alias to preserve any imports using ArrayCollect
class ArrayCollect(ArrayGroup):
    pass


class Median(Aggregation):
    """Median aggregation function.

    This class represents the math::median() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the median function."""
        if self.field:
            return f"math::median({self.field})"
        return "math::median()"


class StdDev(Aggregation):
    """Standard deviation aggregation function.

    This class represents the math::stddev() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the standard deviation function."""
        if self.field:
            return f"math::stddev({self.field})"
        return "math::stddev()"


class Variance(Aggregation):
    """Variance aggregation function.

    This class represents the math::variance() aggregation function in SurrealQL.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the variance function."""
        if self.field:
            return f"math::variance({self.field})"
        return "math::variance()"


class Percentile(Aggregation):
    """Percentile aggregation function.

    This class represents the math::percentile() aggregation function in SurrealQL.
    """

    def __init__(self, field: str = None, percentile: float = 50):
        """Initialize a new Percentile.

        Args:
            field: The field to aggregate (optional)
            percentile: The percentile to calculate (default: 50)
        """
        super().__init__(field)
        self.percentile = percentile

    def __str__(self) -> str:
        """Return the SurrealQL representation of the percentile function."""
        if self.field:
            return f"math::percentile({self.field}, {self.percentile})"
        return f"math::percentile(value, {self.percentile})"


class Distinct(Aggregation):
    """Distinct aggregation function.

    This class represents a distinct-of-values across grouped rows.
    Safe for scalar fields by wrapping each row's value in an array first.
    """

    def __str__(self) -> str:
        """Return the SurrealQL representation of the distinct function."""
        if self.field:
            # Wrap scalar values per-row to satisfy array functions in v2
            return f"array::group([{self.field}])"
        return "array::group([])"


class GroupConcat(Aggregation):
    """Group concatenation aggregation function.

    This class represents a custom aggregation function that concatenates values
    with a separator.
    """

    def __init__(self, field: str = None, separator: str = ", "):
        """Initialize a new GroupConcat.

        Args:
            field: The field to aggregate (optional)
            separator: The separator to use (default: ", ")
        """
        super().__init__(field)
        self.separator = separator

    def __str__(self) -> str:
        """Return the SurrealQL representation of the group concat function."""
        # Escape single quotes in separator for safe literal
        sep = self.separator.replace("'", "''")
        if self.field:
            return f"array::join(array::group([{self.field}]), '{sep}')"
        return f"array::join(array::group([]), '{sep}')"


class CountIf(Aggregation):
    """Conditional count aggregation function.

    This class represents a conditional count aggregation that counts
    records matching a specific condition.
    """

    def __init__(self, condition: str):
        """Initialize a new CountIf.

        Args:
            condition: The condition to evaluate (e.g., "status = 'active'")
        """
        super().__init__()
        self.condition = condition

    def __str__(self) -> str:
        """Return the SurrealQL representation of the conditional count function."""
        # Using IF THEN ELSE syntax for SurrealDB
        return f"count(IF {self.condition} THEN 1 ELSE NULL END)"


class SumIf(Aggregation):
    """Conditional sum aggregation function.

    This class represents a conditional sum aggregation that sums
    field values where a condition is true.
    """

    def __init__(self, field: str, condition: str):
        """Initialize a new SumIf.

        Args:
            field: The field to sum
            condition: The condition to evaluate
        """
        super().__init__(field)
        self.condition = condition

    def __str__(self) -> str:
        """Return the SurrealQL representation of the conditional sum function."""
        return f"math::sum(IF {self.condition} THEN {self.field} ELSE 0 END)"


class MeanIf(Aggregation):
    """Conditional mean aggregation function.

    This class represents a conditional mean aggregation that averages
    field values where a condition is true.
    """

    def __init__(self, field: str, condition: str):
        """Initialize a new MeanIf.

        Args:
            field: The field to average
            condition: The condition to evaluate
        """
        super().__init__(field)
        self.condition = condition

    def __str__(self) -> str:
        """Return the SurrealQL representation of the conditional mean function."""
        return f"math::mean(IF {self.condition} THEN {self.field} ELSE NULL END)"


class MinIf(Aggregation):
    """Conditional min aggregation function.

    This class represents a conditional min aggregation that finds the minimum
    field value where a condition is true.
    """

    def __init__(self, field: str, condition: str):
        """Initialize a new MinIf.

        Args:
            field: The field to find minimum of
            condition: The condition to evaluate
        """
        super().__init__(field)
        self.condition = condition

    def __str__(self) -> str:
        """Return the SurrealQL representation of the conditional min function."""
        return f"math::min(IF {self.condition} THEN {self.field} ELSE NULL END)"


class MaxIf(Aggregation):
    """Conditional max aggregation function.

    This class represents a conditional max aggregation that finds the maximum
    field value where a condition is true.
    """

    def __init__(self, field: str, condition: str):
        """Initialize a new MaxIf.

        Args:
            field: The field to find maximum of
            condition: The condition to evaluate
        """
        super().__init__(field)
        self.condition = condition

    def __str__(self) -> str:
        """Return the SurrealQL representation of the conditional max function."""
        return f"math::max(IF {self.condition} THEN {self.field} ELSE NULL END)"


class DistinctCountIf(Aggregation):
    """Conditional distinct count aggregation function.

    This class represents a conditional distinct count aggregation that counts
    unique field values where a condition is true.
    """

    def __init__(self, field: str, condition: str):
        """Initialize a new DistinctCountIf.

        Args:
            field: The field to count distinct values of
            condition: The condition to evaluate
        """
        super().__init__(field)
        self.condition = condition

    def __str__(self) -> str:
        """Return the SurrealQL representation of the conditional distinct count function."""
        # Build row-wise array to satisfy array::group input requirements
        arr = f"IF {self.condition} THEN [{self.field}] ELSE [] END"
        grouped = f"array::group({arr})"
        # array::group flattens and dedupes, so array::len(grouped) yields distinct count
        return f"array::len({grouped})"


class MaterializedView:
    """Materialized view for SurrealDB.

    This class represents a materialized view in SurrealDB, which is a
    precomputed view of data that can be used to improve query performance
    for frequently accessed aggregated data.

    Attributes:
        name: The name of the materialized view
        query: The query that defines the materialized view
        refresh_interval: The interval at which the view is refreshed
        document_class: The document class that the view is based on
        aggregations: Dictionary of field names and aggregation functions
        select_fields: List of fields to select (if None, selects all fields)
    """

    def __init__(self, name: str, query: QuerySet, refresh_interval: str = None,
                 document_class: Type["Document"] = None, aggregations: Dict[str, Aggregation] = None,
                 select_fields: List[str] = None) -> None:
        """Initialize a new MaterializedView.

        Args:
            name: The name of the materialized view
            query: The query that defines the materialized view
            refresh_interval: The interval at which the view is refreshed (e.g., "1h", "30m")
            document_class: The document class that the view is based on
            aggregations: Dictionary of field names and aggregation functions
            select_fields: List of fields to select (if None, selects all fields)
        """
        # Import Document inside the method to avoid circular imports
        from .document import Document

        self.name = name
        self.query = query
        self.refresh_interval = refresh_interval
        self.document_class = document_class or Document
        self.aggregations = aggregations or {}
        self.select_fields = select_fields

    def _build_custom_query(self) -> str:
        """Build a custom query string that includes aggregation functions and select fields.

        This method builds a custom query string based on the query passed to the constructor,
        but with the addition of aggregation functions and select fields.

        Returns:
            The custom query string
        """
        # Get the base query string
        base_query = self.query._build_query()

        # If there are no aggregations or select fields, return the base query
        if not self.aggregations and not self.select_fields:
            return base_query

        # Extract the FROM clause and any clauses that come after it
        from_index = base_query.upper().find("FROM")
        if from_index == -1:
            # If there's no FROM clause, we can't modify the query
            return base_query

        # Split the query into the SELECT part and the rest
        select_part = base_query[:from_index].strip()
        rest_part = base_query[from_index:].strip()

        # If there are no aggregations or select fields, return the base query
        if not self.aggregations and not self.select_fields:
            return base_query

        # Build the new SELECT part
        new_select_part = "SELECT"

        # Add the select fields
        fields = []
        if self.select_fields:
            fields.extend(self.select_fields)

        # Add the aggregation functions
        for field_name, aggregation in self.aggregations.items():
            fields.append(f"{aggregation} AS {field_name}")

        # Check if there are GROUP BY fields in the query and add them to the SELECT clause
        # This is necessary because SurrealDB requires GROUP BY fields to be in the SELECT clause
        group_by_index = rest_part.upper().find("GROUP BY")
        if group_by_index != -1:
            # Extract the GROUP BY clause
            group_by_clause = rest_part[group_by_index:].strip()
            # Find the next clause after GROUP BY (if any)
            next_clause_index = -1
            for clause in ["SPLIT", "FETCH", "WITH", "ORDER BY", "LIMIT", "START"]:
                clause_index = group_by_clause.upper().find(clause, len("GROUP BY"))
                if clause_index != -1 and (next_clause_index == -1 or clause_index < next_clause_index):
                    next_clause_index = clause_index

            # Extract the GROUP BY fields
            if next_clause_index != -1:
                group_by_fields_str = group_by_clause[len("GROUP BY"):next_clause_index].strip()
            else:
                group_by_fields_str = group_by_clause[len("GROUP BY"):].strip()

            # Split the GROUP BY fields and add them to the SELECT fields if not already included
            group_by_fields = [field.strip() for field in group_by_fields_str.split(",")]
            for field in group_by_fields:
                if field and field not in fields:
                    fields.append(field)

        # If there are no fields, use * to select all fields
        if not fields:
            fields.append("*")

        # Add the fields to the SELECT part
        new_select_part += " " + ", ".join(fields)

        # Combine the new SELECT part with the rest of the query
        return f"{new_select_part} {rest_part}"

    async def create(self, connection=None) -> None:
        """Create the materialized view in the database.

        Args:
            connection: The database connection to use (optional)
        """
        connection = connection or ConnectionRegistry.get_default_connection()

        # Build the query for creating the materialized view
        query_str = self._build_custom_query()
        create_query = f"DEFINE TABLE {self.name} TYPE NORMAL AS {query_str}"

        # Note: SurrealDB materialized views are automatically updated when underlying data changes
        # The refresh_interval parameter is ignored as SurrealDB doesn't support the EVERY clause

        # Execute the query
        await connection.client.query(create_query)

    def create_sync(self, connection=None) -> None:
        """Create the materialized view in the database synchronously.

        Args:
            connection: The database connection to use (optional)
        """
        connection = connection or ConnectionRegistry.get_default_connection()

        # Build the query for creating the materialized view
        query_str = self._build_custom_query()
        create_query = f"DEFINE TABLE {self.name} TYPE NORMAL AS {query_str}"

        # Execute the query
        connection.client.query(create_query)

    async def drop(self, connection=None) -> None:
        """Drop the materialized view from the database.

        Args:
            connection: The database connection to use (optional)
        """
        connection = connection or ConnectionRegistry.get_default_connection()

        # Build the query for dropping the materialized view
        drop_query = f"REMOVE TABLE {self.name}"


        # Execute the query
        await connection.client.query(drop_query)

    def drop_sync(self, connection=None) -> None:
        """Drop the materialized view from the database synchronously.

        Args:
            connection: The database connection to use (optional)
        """
        connection = connection or ConnectionRegistry.get_default_connection()

        # Build the query for dropping the materialized view
        drop_query = f"REMOVE TABLE {self.name}"


        # Execute the query
        connection.client.query(drop_query)

    async def refresh(self, connection=None) -> None:
        """Manually refresh the materialized view.

        Note: SurrealDB materialized views are automatically updated when underlying data changes.
        This method might not work as expected.

        Args:
            connection: The database connection to use (optional)
        """
        connection = connection or ConnectionRegistry.get_default_connection()

        # Build the query for refreshing the materialized view
        refresh_query = f"REFRESH VIEW {self.name}"

        # Execute the query
        await connection.client.query(refresh_query)

    def refresh_sync(self, connection=None) -> None:
        """Manually refresh the materialized view.

                Note: SurrealDB materialized views are automatically updated when underlying data changes.
                This method might not work as expected.

                Args:
                    connection: The database connection to use (optional)
                """
        connection = connection or ConnectionRegistry.get_default_connection()

        # Build the query for refreshing the materialized view
        refresh_query = f"REFRESH VIEW {self.name}"

        # Execute the query
        connection.client.query(refresh_query)

    @property
    def objects(self) -> QuerySet:
        """Get a QuerySet for querying the materialized view.

        Returns:
            A QuerySet for querying the materialized view
        """
        # Create a temporary document class for the materialized view
        view_class = type(f"{self.name.capitalize()}View", (self.document_class,), {
            "Meta": type("Meta", (), {"collection": self.name})
        })

        # Return a QuerySet for the view class
        connection = ConnectionRegistry.get_default_connection()
        return QuerySet(view_class, connection)

    async def execute_raw_query(self, connection=None):
        """Execute a raw query against the materialized view.

        This is a workaround for the "no decoder for tag" error that can occur
        when querying materialized views using the objects property.

        Args:
            connection: The database connection to use (optional)

        Returns:
            The query results
        """
        connection = connection or ConnectionRegistry.get_default_connection()
        query = f"SELECT * FROM {self.name}"
        return await connection.client.query(query)

    def execute_raw_query_sync(self, connection=None):
        """Execute a raw query against the materialized view synchronously.

        This is a workaround for the "no decoder for tag" error that can occur
        when querying materialized views using the objects property.

        Args:
            connection: The database connection to use (optional)

        Returns:
            The query results
        """
        connection = connection or ConnectionRegistry.get_default_connection()
        query = f"SELECT * FROM {self.name}"
        return connection.client.query(query)
