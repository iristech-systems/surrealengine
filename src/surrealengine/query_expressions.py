"""
Query expression system for SurrealEngine

This module provides a query expression system that allows building complex
queries programmatically and passing them to objects() and filter() methods.
"""

from typing import Any, Dict, List, Optional, Union
import json


class Q:
    """Query expression builder for complex queries.
    
    This class allows building complex query expressions that can be used
    with filter() and objects() methods.
    
    Example:
        # Complex AND/OR queries
        query = Q(age__gt=18) & Q(active=True)
        users = User.objects.filter(query)
        
        # Complex queries with objects()
        query = Q(department="engineering") | Q(department="sales")
        users = User.objects(query)
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
        
        # If conditions are simple (field, value) tuples, return them
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
        
        # For complex nested conditions, we need to handle recursively
        # This is a simplified implementation - for full support we'd need
        # more sophisticated query tree building
        all_conditions = []
        for cond in self.conditions:
            if isinstance(cond, Q):
                all_conditions.extend(cond.to_conditions())
            elif isinstance(cond, tuple) and len(cond) == 2:
                field, value = cond
                all_conditions.append((field, '=', value))
        
        return all_conditions
    
    def to_where_clause(self) -> str:
        """Convert this Q object to a WHERE clause string.
        
        Returns:
            WHERE clause string for SurrealQL
        """
        if self.raw_query:
            return self.raw_query
        
        conditions = self.to_conditions()
        if not conditions:
            return ""
        
        # Build condition strings
        condition_strs = []
        for field, op, value in conditions:
            if field == '__raw__':
                condition_strs.append(value)
            else:
                # Handle special operators
                if op in ('CONTAINS', 'STARTSWITH', 'ENDSWITH'):
                    if op == 'CONTAINS':
                        condition_strs.append(f"string::contains({field}, '{value}')")
                    elif op == 'STARTSWITH':
                        condition_strs.append(f"string::starts_with({field}, '{value}')")
                    elif op == 'ENDSWITH':
                        condition_strs.append(f"string::ends_with({field}, '{value}')")
                elif op == 'REGEX':
                    condition_strs.append(f"string::matches({field}, r'{value}')")
                elif op in ('INSIDE', 'NOT INSIDE'):
                    value_str = json.dumps(value)
                    condition_strs.append(f"{field} {op} {value_str}")
                else:
                    # Regular operators
                    if isinstance(value, str) and not (isinstance(value, str) and ':' in value):
                        # Quote string values
                        condition_strs.append(f"{field} {op} '{value}'")
                    else:
                        # Don't quote numbers, booleans, or record IDs
                        condition_strs.append(f"{field} {op} {json.dumps(value)}")
        
        # Join with operator
        if self.operator == 'AND':
            return ' AND '.join(condition_strs)
        elif self.operator == 'OR':
            return ' OR '.join(condition_strs)
        elif self.operator == 'NOT':
            return f"NOT ({' AND '.join(condition_strs)})"
        else:
            return ' AND '.join(condition_strs)


class QueryExpression:
    """Higher-level query expression that can include fetch, grouping, etc.
    
    This class provides a more comprehensive query building interface
    that includes not just WHERE conditions but also FETCH, GROUP BY, etc.
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
        # Apply WHERE conditions
        if self.where:
            conditions = self.where.to_conditions()
            for field, op, value in conditions:
                if field == '__raw__':
                    # Add raw condition - this would need special handling in BaseQuerySet
                    queryset.query_parts.append(('__raw__', '=', value))
                else:
                    queryset.query_parts.append((field, op, value))
        
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