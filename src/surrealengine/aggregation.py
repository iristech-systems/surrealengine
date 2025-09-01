"""Aggregation pipeline for SurrealEngine.

This module provides support for building and executing aggregation pipelines
in SurrealEngine. Aggregation pipelines allow for complex data transformations
and analysis through a series of stages.
"""
import json
from .surrealql import escape_literal
import re
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from .connection import ConnectionRegistry

if TYPE_CHECKING:
    from .query import QuerySet


class AggregationPipeline:
    """Pipeline for building and executing aggregation queries.
    
    This class provides a fluent interface for building complex aggregation
    pipelines with multiple stages, similar to MongoDB's aggregation framework.
    """
    
    def __init__(self, query_set: 'QuerySet'):
        """Initialize a new AggregationPipeline.
        
        Args:
            query_set: The QuerySet to build the pipeline from
        """
        self.query_set = query_set
        self.stages = []
        self.connection = query_set.connection
        
    def group(self, by_fields=None, **aggregations):
        """Group by fields and apply aggregations.
        
        Args:
            by_fields: Field or list of fields to group by
            **aggregations: Named aggregation functions to apply
            
        Returns:
            The pipeline instance for method chaining
        """
        self.stages.append({
            'type': 'group',
            'by_fields': by_fields if isinstance(by_fields, list) else ([by_fields] if by_fields else []),
            'aggregations': aggregations
        })
        return self
        
    def project(self, **fields):
        """Select or compute fields to include in output.
        
        Args:
            **fields: Field mappings for projection
            
        Returns:
            The pipeline instance for method chaining
        """
        self.stages.append({
            'type': 'project',
            'fields': fields
        })
        return self
        
    def sort(self, **fields):
        """Sort results by fields.
        
        Args:
            **fields: Field names and sort directions ('ASC' or 'DESC')
            
        Returns:
            The pipeline instance for method chaining
        """
        self.stages.append({
            'type': 'sort',
            'fields': fields
        })
        return self
        
    def limit(self, count):
        """Limit number of results.
        
        Args:
            count: Maximum number of results to return
            
        Returns:
            The pipeline instance for method chaining
        """
        self.stages.append({
            'type': 'limit',
            'count': count
        })
        return self
        
    def skip(self, count):
        """Skip number of results.
        
        Args:
            count: Number of results to skip
            
        Returns:
            The pipeline instance for method chaining
        """
        self.stages.append({
            'type': 'skip',
            'count': count
        })
        return self
        
    def with_index(self, index):
        """Use the specified index for the query.
        
        Args:
            index: Name of the index to use
            
        Returns:
            The pipeline instance for method chaining
        """
        self.stages.append({
            'type': 'with_index',
            'index': index
        })
        return self
        
    def match(self, **conditions):
        """Filter documents before aggregation (similar to WHERE clause).
        
        This method adds filtering conditions that are applied before
        any aggregation operations. Multiple conditions are combined with AND.
        
        Args:
            **conditions: Field-value pairs for filtering (e.g., status='active')
            
        Returns:
            The pipeline instance for method chaining
            
        Example:
            pipeline.match(status='completed', price__gt=100)
        """
        self.stages.append({
            'type': 'match',
            'conditions': conditions
        })
        return self
        
    def having(self, **conditions):
        """Filter aggregated results (similar to HAVING clause).
        
        This method adds filtering conditions that are applied after
        aggregation operations. Use this to filter based on aggregated values.
        
        Args:
            **conditions: Field-value pairs for filtering aggregated results
            
        Returns:
            The pipeline instance for method chaining
            
        Example:
            pipeline.group(by_fields='category', total=Sum('price')).having(total__gt=1000)
        """
        self.stages.append({
            'type': 'having',
            'conditions': conditions
        })
        return self
        
    def build_query(self):
        """Build the SurrealQL query from the pipeline stages.
        
        Returns:
            The SurrealQL query string
        """
        # Start with the base query from the query set
        base_query = self.query_set.get_raw_query()
        
        # Extract the FROM clause and any clauses that come after it
        from_index = base_query.upper().find("FROM")
        if from_index == -1:
            return base_query
            
        # Split the query into the SELECT part and the rest
        select_part = base_query[:from_index].strip()
        rest_part = base_query[from_index:].strip()
        
        # Process the stages to modify the query
        for stage in self.stages:
            if stage['type'] == 'match':
                # Handle MATCH stage (pre-aggregation filtering)
                conditions = stage['conditions']
                
                if conditions:
                    # Build WHERE conditions
                    where_conditions = []
                    for field, value in conditions.items():
                        # Handle Django-style operators
                        if '__' in field:
                            field_name, op = field.rsplit('__', 1)
                            if op == 'gt':
                                where_conditions.append(f"{field_name} > {escape_literal(value)}")
                            elif op == 'lt':
                                where_conditions.append(f"{field_name} < {escape_literal(value)}")
                            elif op == 'gte':
                                where_conditions.append(f"{field_name} >= {escape_literal(value)}")
                            elif op == 'lte':
                                where_conditions.append(f"{field_name} <= {escape_literal(value)}")
                            elif op == 'ne':
                                where_conditions.append(f"{field_name} != {escape_literal(value)}")
                            elif op == 'in':
                                where_conditions.append(f"{field_name} IN {escape_literal(value)}")
                            elif op == 'nin':
                                where_conditions.append(f"{field_name} NOT IN {escape_literal(value)}")
                            elif op == 'contains':
                                where_conditions.append(f"{field_name} CONTAINS {escape_literal(value)}")
                            elif op == 'startswith':
                                where_conditions.append(f"string::starts_with({field_name}, {escape_literal(value)})")
                            elif op == 'endswith':
                                where_conditions.append(f"string::ends_with({field_name}, {escape_literal(value)})")
                            else:
                                # Default to equality
                                where_conditions.append(f"{field_name} = {escape_literal(value)}")
                        else:
                            # Simple equality
                            where_conditions.append(f"{field} = {escape_literal(value)}")
                    
                    where_clause = f"WHERE {' AND '.join(where_conditions)}"
                    
                    # Check if there's already a WHERE clause
                    if "WHERE" in rest_part.upper():
                        # Append to existing WHERE clause
                        where_index = rest_part.upper().find("WHERE")
                        # Find the end of WHERE clause
                        for clause in ["GROUP BY", "SPLIT", "FETCH", "ORDER BY", "LIMIT", "START"]:
                            clause_index = rest_part.upper().find(clause, where_index)
                            if clause_index != -1:
                                # Insert before the next clause
                                existing_where = rest_part[where_index:clause_index].strip()
                                new_where = f"{existing_where} AND {' AND '.join(where_conditions)}"
                                rest_part = f"{rest_part[:where_index]}{new_where} {rest_part[clause_index:]}"
                                break
                        else:
                            # No other clause after WHERE
                            rest_part = f"{rest_part} AND {' AND '.join(where_conditions)}"
                    else:
                        # Add WHERE clause before GROUP BY or other clauses
                        for clause in ["GROUP BY", "SPLIT", "FETCH", "ORDER BY", "LIMIT", "START"]:
                            clause_index = rest_part.upper().find(clause)
                            if clause_index != -1:
                                rest_part = f"{rest_part[:clause_index]}{where_clause} {rest_part[clause_index:]}"
                                break
                        else:
                            # No other clauses, add to the end
                            rest_part = f"{rest_part} {where_clause}"
            
            elif stage['type'] == 'group':
                # Handle GROUP BY stage
                by_fields = stage['by_fields']
                aggregations = stage['aggregations']
                
                # Build the GROUP BY clause or GROUP ALL
                if by_fields:
                    group_clause = f"GROUP BY {', '.join(by_fields)}"
                else:
                    # If no explicit group fields but aggregations exist with array functions,
                    # we can use GROUP ALL to enable row-collection semantics.
                    group_clause = "GROUP ALL"
                
                if by_fields or aggregations:
                    # Inject group clause if not already present
                    upper = rest_part.upper()
                    if "GROUP BY" in upper or "GROUP ALL" in upper:
                        # Replace existing group clause
                        rest_part = re.sub(r'GROUP (?:BY|ALL).*?(?=(ORDER BY|LIMIT|START|$))', group_clause, rest_part, flags=re.IGNORECASE)
                    else:
                        # Add the group clause before ORDER BY, LIMIT, or START
                        inserted = False
                        for clause in ["ORDER BY", "LIMIT", "START"]:
                            clause_index = rest_part.upper().find(clause)
                            if clause_index != -1:
                                rest_part = f"{rest_part[:clause_index]}{group_clause} {rest_part[clause_index:]}"
                                inserted = True
                                break
                        if not inserted:
                            rest_part = f"{rest_part} {group_clause}"
                
                # Build the SELECT part with aggregations
                if aggregations:
                    # Start with the group by fields
                    select_fields = by_fields.copy() if by_fields else []
                    
                    # Add the aggregations
                    for name, agg in aggregations.items():
                        select_fields.append(f"{agg} AS {name}")
                    
                    # Replace the SELECT part
                    select_part = f"SELECT {', '.join(select_fields)}"
            
            elif stage['type'] == 'project':
                # Handle PROJECT stage
                fields = stage['fields']
                
                # Build the SELECT part with projections
                if fields:
                    select_fields = []
                    
                    # Add the projections
                    for name, expr in fields.items():
                        if expr is True:
                            # Include the field as is
                            select_fields.append(name)
                        else:
                            # Include the field with an expression
                            select_fields.append(f"{expr} AS {name}")
                    
                    # Replace the SELECT part
                    select_part = f"SELECT {', '.join(select_fields)}"
            
            elif stage['type'] == 'having':
                # Handle HAVING stage (post-aggregation filtering)
                conditions = stage['conditions']
                
                if conditions:
                    # Build HAVING conditions
                    having_conditions = []
                    for field, value in conditions.items():
                        # Handle Django-style operators
                        if '__' in field:
                            field_name, op = field.rsplit('__', 1)
                            if op == 'gt':
                                having_conditions.append(f"{field_name} > {escape_literal(value)}")
                            elif op == 'lt':
                                having_conditions.append(f"{field_name} < {escape_literal(value)}")
                            elif op == 'gte':
                                having_conditions.append(f"{field_name} >= {escape_literal(value)}")
                            elif op == 'lte':
                                having_conditions.append(f"{field_name} <= {escape_literal(value)}")
                            elif op == 'ne':
                                having_conditions.append(f"{field_name} != {escape_literal(value)}")
                            elif op == 'in':
                                having_conditions.append(f"{field_name} IN {escape_literal(value)}")
                            elif op == 'nin':
                                having_conditions.append(f"{field_name} NOT IN {escape_literal(value)}")
                            else:
                                # Default to equality
                                having_conditions.append(f"{field_name} = {escape_literal(value)}")
                        else:
                            # Simple equality
                            having_conditions.append(f"{field} = {escape_literal(value)}")
                    
                    # For SurrealDB, HAVING is implemented as a WHERE clause on the aggregated results
                    # We need to wrap the entire query in a subquery and apply WHERE on it
                    # This will be handled at the end of query building
                    self.having_conditions = having_conditions
            
            elif stage['type'] == 'sort':
                # Handle SORT stage
                fields = stage['fields']
                
                # Build the ORDER BY clause
                if fields:
                    order_by_parts = []
                    
                    # Add the sort fields
                    for field, direction in fields.items():
                        order_by_parts.append(f"{field} {direction}")
                    
                    order_by_clause = f"ORDER BY {', '.join(order_by_parts)}"
                    
                    # Check if there's already an ORDER BY clause
                    if "ORDER BY" in rest_part.upper():
                        # Replace the existing ORDER BY clause
                        rest_part = re.sub(r'ORDER BY.*?(?=(LIMIT|START|$))', order_by_clause, rest_part, flags=re.IGNORECASE)
                    else:
                        # Add the ORDER BY clause before LIMIT or START
                        for clause in ["LIMIT", "START"]:
                            clause_index = rest_part.upper().find(clause)
                            if clause_index != -1:
                                rest_part = f"{rest_part[:clause_index]}{order_by_clause} {rest_part[clause_index:]}"
                                break
                        else:
                            # No LIMIT or START, so add to the end
                            rest_part = f"{rest_part} {order_by_clause}"
            
            elif stage['type'] == 'limit':
                # Handle LIMIT stage
                count = stage['count']
                
                # Build the LIMIT clause
                limit_clause = f"LIMIT {count}"
                
                # Check if there's already a LIMIT clause
                if "LIMIT" in rest_part.upper():
                    # Replace the existing LIMIT clause
                    rest_part = re.sub(r'LIMIT.*?(?=(START|$))', limit_clause, rest_part, flags=re.IGNORECASE)
                else:
                    # Add the LIMIT clause before START
                    start_index = rest_part.upper().find("START")
                    if start_index != -1:
                        rest_part = f"{rest_part[:start_index]}{limit_clause} {rest_part[start_index:]}"
                    else:
                        # No START, so add to the end
                        rest_part = f"{rest_part} {limit_clause}"
            
            elif stage['type'] == 'skip':
                # Handle SKIP stage
                count = stage['count']
                
                # Build the START clause
                start_clause = f"START {count}"
                
                # Check if there's already a START clause
                if "START" in rest_part.upper():
                    # Replace the existing START clause
                    rest_part = re.sub(r'START.*?(?=$)', start_clause, rest_part, flags=re.IGNORECASE)
                else:
                    # Add the START clause to the end
                    rest_part = f"{rest_part} {start_clause}"
            
            elif stage['type'] == 'with_index':
                # Handle WITH_INDEX stage
                index = stage['index']
                
                # Build the WITH clause
                with_clause = f"WITH INDEX {index}"
                
                # Check if there's already a WITH clause
                if "WITH" in rest_part.upper():
                    # Replace the existing WITH clause
                    rest_part = re.sub(r'WITH.*?(?=(WHERE|GROUP BY|SPLIT|FETCH|ORDER BY|LIMIT|START|$))', with_clause, rest_part, flags=re.IGNORECASE)
                else:
                    # Add the WITH clause before WHERE, GROUP BY, SPLIT, FETCH, ORDER BY, LIMIT, or START
                    for clause in ["WHERE", "GROUP BY", "SPLIT", "FETCH", "ORDER BY", "LIMIT", "START"]:
                        clause_index = rest_part.upper().find(clause)
                        if clause_index != -1:
                            rest_part = f"{rest_part[:clause_index]}{with_clause} {rest_part[clause_index:]}"
                            break
                    else:
                        # No WHERE, GROUP BY, SPLIT, FETCH, ORDER BY, LIMIT, or START, so add to the end
                        rest_part = f"{rest_part} {with_clause}"
        
        # Combine the SELECT part with the rest of the query
        final_query = f"{select_part} {rest_part}"
        
        # Handle HAVING conditions by wrapping in a subquery
        if hasattr(self, 'having_conditions') and self.having_conditions:
            # Wrap the entire query in a subquery and apply WHERE conditions
            having_where = " AND ".join(self.having_conditions)
            final_query = f"SELECT * FROM ({final_query}) WHERE {having_where}"
        
        return final_query
        
    async def execute(self, connection=None):
        """Execute the pipeline and return results.
        
        Args:
            connection: Optional connection to use
            
        Returns:
            A list of result rows (dicts) from the final SELECT statement
        """
        query = self.build_query()
        connection = connection or self.connection or ConnectionRegistry.get_default_connection()
        results = await connection.client.query(query)

        # Normalize RPC response to a list of row dicts, similar to QuerySet.all()
        if not results:
            return []

        rows = None
        if isinstance(results, list):
            if results and isinstance(results[0], dict):
                rows = results
            else:
                for part in reversed(results):
                    if isinstance(part, list):
                        rows = part
                        break
        else:
            rows = results
        if not rows:
            return []
        if isinstance(rows, dict):
            rows = [rows]
        return rows
        
    def execute_sync(self, connection=None):
        """Execute the pipeline synchronously.
        
        Args:
            connection: Optional connection to use
            
        Returns:
            A list of result rows (dicts) from the final SELECT statement
        """
        query = self.build_query()
        connection = connection or self.connection or ConnectionRegistry.get_default_connection()
        results = connection.client.query(query)

        # Normalize RPC response to a list of row dicts, similar to QuerySet.all_sync()
        if not results:
            return []

        rows = None
        if isinstance(results, list):
            if results and isinstance(results[0], dict):
                rows = results
            else:
                for part in reversed(results):
                    if isinstance(part, list):
                        rows = part
                        break
        else:
            rows = results
        if not rows:
            return []
        if isinstance(rows, dict):
            rows = [rows]
        return rows