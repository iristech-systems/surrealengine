"""
Query expression system for SurrealEngine

This module provides a query expression system that allows building complex
queries programmatically and passing them to objects() and filter() methods.
"""

from typing import Any, Dict, List, Optional, Union
import json
from .surrealql import escape_literal


class Q:
    """Query expression builder for complex queries.
    
    This class allows building complex query expressions that can be used
    with filter() and objects() methods.
    
    Examples:
        Simple query:

        >>> q = Q(age__gt=25)
        >>> users = User.objects.filter(q).all()  # example

        Complex AND/OR queries:

        >>> q1 = Q(age__gt=25) & Q(active=True)  # AND condition
        >>> active_older_users = User.objects.filter(q1).all()  # example

        >>> q2 = Q(age__lt=30) | Q(username="charlie")  # OR condition
        >>> users_or = User.objects.filter(q2).all()  # example

        Using NOT:

        >>> q3 = ~Q(active=True)  # NOT active
        >>> inactive_users = User.objects.filter(q3).all()  # example

        Raw queries:

        >>> q4 = Q.raw("age > 20 AND username CONTAINS 'a'")
        >>> users_raw = User.objects.filter(q4).all()  # example

        Query operators:

        >>> queries = [
        ...     Q(age__in=[25, 30]),  # IN operator
        ...     Q(username__startswith="a"),  # STARTSWITH
        ...     Q(email__contains="example"),  # CONTAINS
        ...     Q(age__gte=25) & Q(age__lte=35),  # Range
        ... ]

        Using with objects() method:

        >>> query = Q(published=True) & Q(views__gt=75)
        >>> popular_posts = Post.objects(query)  # example

        Combining with additional filters:

        >>> base_query = Q(published=True)
        >>> high_view_posts = Post.objects(base_query, views__gt=150)  # example
    """
    
    def __init__(self, **kwargs):
        """Initialize a query expression.
        
        Args:
            **kwargs: Field filters to include in the query
        """
        self.conditions = []
        self.operator = 'AND'
        self.raw_query = None
        
        # Add conditions from kwargs
        for key, value in kwargs.items():
            self.conditions.append((key, value))
    
    def __and__(self, other: 'Q') -> 'Q':
        """Combine with another Q object using AND."""
        result = Q()
        result.conditions = [self, other]
        result.operator = 'AND'
        return result
    
    def __or__(self, other: 'Q') -> 'Q':
        """Combine with another Q object using OR."""
        result = Q()
        result.conditions = [self, other]
        result.operator = 'OR'
        return result
    
    def __invert__(self) -> 'Q':
        """Negate this query using NOT."""
        result = Q()
        result.conditions = [self]
        result.operator = 'NOT'
        return result
    
    @classmethod
    def raw(cls, query_string: str) -> 'Q':
        """Create a raw query expression.
        
        Args:
            query_string: Raw SurrealQL WHERE clause
            
        Returns:
            Q object with raw query
        """
        result = cls()
        result.raw_query = query_string
        return result
    
    def to_conditions(self) -> List[tuple]:
        """Convert this Q object to a list of conditions.
        
        Returns:
            List of (field, operator, value) tuples
        """
        if self.raw_query:
            # Return raw query as a special condition
            return [('__raw__', '=', self.raw_query)]
        
        if not self.conditions:
            return []
        
        # This method is now only safe for leaf nodes.
        # It does not handle nested Q objects.
        if all(isinstance(cond, tuple) and len(cond) == 2 for cond in self.conditions):
            result = []
            for field, value in self.conditions:
                # Parse field__operator syntax
                if '__' in field:
                    parts = field.split('__')
                    field_name = parts[0]
                    operator = parts[1]
                    
                    # Map Django-style operators to SurrealDB operators
                    op_map = {
                        'gt': '>',
                        'lt': '<', 
                        'gte': '>=',
                        'lte': '<=',
                        'ne': '!=',
                        'in': 'INSIDE',
                        'nin': 'NOT INSIDE',
                        'contains': 'CONTAINS',
                        'startswith': 'STARTSWITH',
                        'endswith': 'ENDSWITH',
                        'regex': 'REGEX'
                    }
                    
                    surreal_op = op_map.get(operator, '=')
                    result.append((field_name, surreal_op, value))
                else:
                    result.append((field, '=', value))
            return result
        
        return []
    
    def to_where_clause(self) -> str:
        """Convert this Q object to a WHERE clause string.
        
        Returns:
            WHERE clause string for SurrealQL
        """
        if self.raw_query:
            return self.raw_query

        if not self.conditions:
            return ""

        # Check if this is an internal node (created with & or | or ~)
        is_internal_node = any(isinstance(c, Q) for c in self.conditions)

        if is_internal_node:
            # Recursively build clauses for children
            child_clauses = []
            for c in self.conditions:
                if isinstance(c, Q):
                    child_clauses.append(f"({c.to_where_clause()})")

            if self.operator == 'NOT':
                return f"NOT {child_clauses[0]}"
            
            return f" {self.operator} ".join(child_clauses)
        
        else:
            # This is a leaf node (e.g., Q(age__gt=25, active=True))
            # All conditions inside a single Q object are ANDed together.
            conditions = self.to_conditions()
            condition_strs = []
            for field, op, value in conditions:
                if field == '__raw__':
                    condition_strs.append(value)
                else:
                    # Handle special operators
                    if op in ('CONTAINS', 'STARTSWITH', 'ENDSWITH'):
                        if op == 'CONTAINS':
                            condition_strs.append(f"string::contains({field}, {escape_literal(value)})")
                        elif op == 'STARTSWITH':
                            condition_strs.append(f"string::starts_with({field}, {escape_literal(value)})")
                        elif op == 'ENDSWITH':
                            condition_strs.append(f"string::ends_with({field}, {escape_literal(value)})")
                    elif op == 'REGEX':
                        condition_strs.append(f"string::matches({field}, {escape_literal(value)})")
                    elif op in ('INSIDE', 'NOT INSIDE'):
                        value_str = escape_literal(value)
                        condition_strs.append(f"{field} {op} {value_str}")
                    else:
                        # Regular operators with proper escaping
                        condition_strs.append(f"{field} {op} {escape_literal(value)}")
            
            return ' AND '.join(condition_strs)


class QueryExpression:
    """Higher-level query expression that can include fetch, grouping, etc.
    
    This class provides a more comprehensive query building interface
    that includes not just WHERE conditions but also FETCH, GROUP BY, etc.

    Examples:
        QueryExpression with FETCH for dereferencing:

        >>> expr = QueryExpression(where=Q(published=True)).fetch("author")
        >>> posts_with_authors = Post.objects.filter(expr).all()  # example

        Complex QueryExpression with multiple clauses:

        >>> complex_expr = (QueryExpression(where=Q(active=True))
        ...                .order_by("age", "DESC")
        ...                .limit(2))
        >>> top_users = User.objects.filter(complex_expr).all()  # example

        QueryExpression with grouping:

        >>> expr = (QueryExpression(where=Q(published=True))
        ...         .group_by("category")
        ...         .order_by("created_at", "DESC"))

        QueryExpression with pagination:

        >>> expr = (QueryExpression(where=Q(active=True))
        ...         .order_by("created_at", "DESC")
        ...         .limit(10)
        ...         .start(20))  # Skip first 20 records

        Combining with fetch for complex relationships:

        >>> expr = (QueryExpression(where=Q(type="article"))
        ...         .fetch("author", "category", "tags")
        ...         .order_by("published_at", "DESC"))
    """
    
    def __init__(self, where: Optional[Q] = None):
        """Initialize a query expression.
        
        Args:
            where: Q object for WHERE clause conditions
        """
        self.where = where
        self.fetch_fields = []
        self.group_by_fields = []
        self.order_by_field = None
        self.order_by_direction = 'ASC'
        self.limit_value = None
        self.start_value = None
    
    
    def fetch(self, *fields: str) -> 'QueryExpression':
        """Add FETCH clause to resolve references.
        
        Args:
            *fields: Field names to fetch
            
        Returns:
            Self for method chaining
        """
        self.fetch_fields.extend(fields)
        return self
    
    def group_by(self, *fields: str) -> 'QueryExpression':
        """Add GROUP BY clause.
        
        Args:
            *fields: Field names to group by
            
        Returns:
            Self for method chaining
        """
        self.group_by_fields.extend(fields)
        return self
    
    def order_by(self, field: str, direction: str = 'ASC') -> 'QueryExpression':
        """Add ORDER BY clause.
        
        Args:
            field: Field name to order by
            direction: 'ASC' or 'DESC'
            
        Returns:
            Self for method chaining
        """
        self.order_by_field = field
        self.order_by_direction = direction
        return self
    
    def limit(self, value: int) -> 'QueryExpression':
        """Add LIMIT clause.
        
        Args:
            value: Maximum number of results
            
        Returns:
            Self for method chaining
        """
        self.limit_value = value
        return self
    
    def start(self, value: int) -> 'QueryExpression':
        """Add START clause for pagination.
        
        Args:
            value: Number of results to skip
            
        Returns:
            Self for method chaining
        """
        self.start_value = value
        return self
    
    def apply_to_queryset(self, queryset):
        """Apply this expression to a queryset.
        
        Args:
            queryset: BaseQuerySet to apply expression to
            
        Returns:
            Modified queryset
        """
        # Apply WHERE conditions using the corrected to_where_clause method
        if self.where:
            where_clause = self.where.to_where_clause()
            if where_clause:
                queryset.query_parts.append(('__raw__', '=', where_clause))
        
        # Apply FETCH
        if self.fetch_fields:
            queryset.fetch_fields.extend(self.fetch_fields)
        
        # Apply GROUP BY
        if self.group_by_fields:
            queryset.group_by_fields.extend(self.group_by_fields)
        
        # Apply ORDER BY
        if self.order_by_field:
            queryset.order_by_value = (self.order_by_field, self.order_by_direction)
        
        # Apply LIMIT
        if self.limit_value:
            queryset.limit_value = self.limit_value
        
        # Apply START
        if self.start_value:
            queryset.start_value = self.start_value
        
        return queryset
