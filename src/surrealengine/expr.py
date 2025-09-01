"""Expression builder for complex aggregation conditions.

This module provides utilities for building complex expressions
that can be used in conditional aggregations and filtering.
"""
import json
from typing import Any, Union, Optional
from .record_id_utils import RecordIdUtils
from .surrealql import escape_identifier, escape_literal


class Expr:
    class _CaseBuilder:
        def __init__(self):
            self._whens: list[tuple['Expr', 'Expr']] = []
            self._else: Optional['Expr'] = None
            self._alias: Optional[str] = None
        
        def when(self, condition: 'Expr|str', then: 'Expr|Any') -> 'Expr._CaseBuilder':
            cond_expr = condition if isinstance(condition, Expr) else Expr.raw(str(condition))
            then_expr = then if isinstance(then, Expr) else Expr.raw(str(escape_literal(then)))
            self._whens.append((cond_expr, then_expr))
            return self
        
        def else_(self, default: 'Expr|Any') -> 'Expr._CaseBuilder':
            self._else = default if isinstance(default, Expr) else Expr.raw(str(escape_literal(default)))
            return self
        
        def alias(self, name: str) -> 'Expr._CaseBuilder':
            self._alias = name
            return self
        
        def build(self) -> 'Expr':
            parts = ["CASE"]
            for cond, then in self._whens:
                parts.append(f"WHEN {cond} THEN {then}")
            if self._else is not None:
                parts.append(f"ELSE {self._else}")
            parts.append("END")
            expr = Expr(" ".join(parts))
            if self._alias:
                return expr.alias(self._alias)
            return expr
        
        def __str__(self) -> str:
            return str(self.build())
    
    @staticmethod
    def case() -> 'Expr._CaseBuilder':
        """Start building a CASE expression."""
        return Expr._CaseBuilder()

    """Build complex expressions for aggregations and filtering.
    
    This class provides a fluent interface for building SQL-like expressions
    that can be used in conditional aggregations (CountIf, SumIf, etc.) and
    filtering operations.
    
    Example:
        # Simple condition
        condition = Expr.eq("status", "active")
        
        # Complex condition with AND/OR
        condition = (
            Expr.eq("status", "active") & 
            (Expr.gt("amount", 100) | Expr.eq("priority", "high"))
        )
        
        # Use in aggregation
        pipeline.group(
            by_fields="category",
            active_count=CountIf(str(condition))
        )
    """

    @staticmethod
    def var(name: str) -> 'Expr':
        """Reference a query variable like $name.
        
        Args:
            name: Variable name without the leading $
        
        Returns:
            An expression representing the variable reference
        """
        # Do not escape; SurrealQL variables are prefixed with $
        return Expr(f"${name}")
    
    def __init__(self, expr: str):
        """Initialize an expression.
        
        Args:
            expr: The expression string
        """
        self.expr = expr
    
    def __str__(self) -> str:
        """Return the string representation of the expression."""
        return self.expr
    
    def __and__(self, other: 'Expr') -> 'Expr':
        """Combine expressions with AND operator.
        
        Args:
            other: Another expression to AND with
            
        Returns:
            A new expression with both conditions ANDed
        """
        return Expr(f"({self.expr} AND {other.expr})")
    
    def __or__(self, other: 'Expr') -> 'Expr':
        """Combine expressions with OR operator.
        
        Args:
            other: Another expression to OR with
            
        Returns:
            A new expression with both conditions ORed
        """
        return Expr(f"({self.expr} OR {other.expr})")
    
    def __invert__(self) -> 'Expr':
        """Negate the expression with NOT operator.
        
        Returns:
            A new expression with the condition negated
        """
        return Expr(f"NOT ({self.expr})")
    
    def alias(self, name: str) -> 'Expr':
        """Alias this expression in a SELECT projection.
        
        Args:
            name: Alias/field name
        """
        return Expr(f"({self.expr}) AS {escape_identifier(name)}")
    
    @staticmethod
    def field(name: str) -> 'Expr':
        """Create an expression for a field reference.
        
        Args:
            name: The field name
            
        Returns:
            An expression representing the field
        """
        return Expr(name)
    
    @staticmethod
    def eq(field: str, value: Any) -> 'Expr':
        """Create an equality expression.
        
        Args:
            field: The field name
            value: The value to compare against
            
        Returns:
            An expression for field = value
        """
        return Expr(f"{field} = {escape_literal(value)}")
    
    @staticmethod
    def ne(field: str, value: Any) -> 'Expr':
        """Create a not-equal expression.
        
        Args:
            field: The field name
            value: The value to compare against
            
        Returns:
            An expression for field != value
        """
        return Expr(f"{field} != {escape_literal(value)}")
    
    @staticmethod
    def gt(field: str, value: Union[int, float]) -> 'Expr':
        """Create a greater-than expression.
        
        Args:
            field: The field name
            value: The value to compare against
            
        Returns:
            An expression for field > value
        """
        return Expr(f"{field} > {escape_literal(value)}")
    
    @staticmethod
    def gte(field: str, value: Union[int, float]) -> 'Expr':
        """Create a greater-than-or-equal expression.
        
        Args:
            field: The field name
            value: The value to compare against
            
        Returns:
            An expression for field >= value
        """
        return Expr(f"{field} >= {escape_literal(value)}")
    
    @staticmethod
    def lt(field: str, value: Union[int, float]) -> 'Expr':
        """Create a less-than expression.
        
        Args:
            field: The field name
            value: The value to compare against
            
        Returns:
            An expression for field < value
        """
        return Expr(f"{field} < {escape_literal(value)}")
    
    @staticmethod
    def lte(field: str, value: Union[int, float]) -> 'Expr':
        """Create a less-than-or-equal expression.
        
        Args:
            field: The field name
            value: The value to compare against
            
        Returns:
            An expression for field <= value
        """
        return Expr(f"{field} <= {escape_literal(value)}")
    
    @staticmethod
    def between(field: str, low: Union[int, float], high: Union[int, float]) -> 'Expr':
        """Create a BETWEEN expression.
        
        Args:
            field: The field name
            low: The lower bound (inclusive)
            high: The upper bound (inclusive)
            
        Returns:
            An expression for low <= field <= high
        """
        return Expr(f"{field} BETWEEN {escape_literal(low)} AND {escape_literal(high)}")
    
    @staticmethod
    def in_(field: str, values: list) -> 'Expr':
        """Create an IN expression.
        
        Args:
            field: The field name
            values: List of values to check against
            
        Returns:
            An expression for field IN [values]
        """
        return Expr(f"{field} IN {escape_literal(values)}")
    
    @staticmethod
    def not_in(field: str, values: list) -> 'Expr':
        """Create a NOT IN expression.
        
        Args:
            field: The field name
            values: List of values to check against
            
        Returns:
            An expression for field NOT IN [values]
        """
        return Expr(f"{field} NOT IN {escape_literal(values)}")
    
    @staticmethod
    def contains(field: str, value: str) -> 'Expr':
        """Create a CONTAINS expression for string or array fields.
        
        Args:
            field: The field name
            value: The value to check for
            
        Returns:
            An expression for field CONTAINS value
        """
        return Expr(f"{field} CONTAINS {escape_literal(value)}")
    
    @staticmethod
    def starts_with(field: str, prefix: str) -> 'Expr':
        """Create a string starts-with expression.
        
        Args:
            field: The field name
            prefix: The prefix to check for
            
        Returns:
            An expression for checking if field starts with prefix
        """
        return Expr(f"string::starts_with({field}, {escape_literal(prefix)})")
    
    @staticmethod
    def ends_with(field: str, suffix: str) -> 'Expr':
        """Create a string ends-with expression.
        
        Args:
            field: The field name
            suffix: The suffix to check for
            
        Returns:
            An expression for checking if field ends with suffix
        """
        return Expr(f"string::ends_with({field}, {escape_literal(suffix)})")
    
    @staticmethod
    def is_null(field: str) -> 'Expr':
        """Create an IS NULL expression.
        
        Args:
            field: The field name
            
        Returns:
            An expression for field IS NULL
        """
        return Expr(f"{field} = NULL")
    
    @staticmethod
    def is_not_null(field: str) -> 'Expr':
        """Create an IS NOT NULL expression.
        
        Args:
            field: The field name
            
        Returns:
            An expression for field IS NOT NULL
        """
        return Expr(f"{field} != NULL")
    
    @staticmethod
    def regex(field: str, pattern: str) -> 'Expr':
        """Create a regex match expression.
        
        Args:
            field: The field name
            pattern: The regex pattern
            
        Returns:
            An expression for regex matching
        """
        return Expr(f"string::matches({field}, {escape_literal(pattern)})")
    
    @staticmethod
    def raw(expression: str) -> 'Expr':
        """Create a raw expression.
        
        Use this for complex expressions that aren't covered by the helper methods.
        
        Args:
            expression: The raw expression string
            
        Returns:
            An expression wrapping the raw string
        """
        return Expr(expression)
    
    # RecordID-specific methods
    @staticmethod
    def record_eq(field: str, record_id: Any, table_name: Optional[str] = None) -> 'Expr':
        """Create an equality expression for RecordID fields.
        
        This method handles various RecordID formats including URL-encoded versions.
        
        Args:
            field: The field name
            record_id: The RecordID in any supported format
            table_name: Optional table name for short ID format
            
        Returns:
            An expression for field = record_id
            
        Examples:
            >>> Expr.record_eq("user_id", "user:123")
            >>> Expr.record_eq("user_id", "user%3A123")  # URL-encoded
            >>> Expr.record_eq("user_id", "123", "user")  # Short format
        """
        normalized_id = RecordIdUtils.normalize_record_id(record_id, table_name)
        if normalized_id is None:
            # Fall back to regular string handling if normalization fails
            return Expr(f"{field} = {escape_literal(str(record_id))}")
        return Expr(f"{field} = {normalized_id}")
    
    @staticmethod
    def record_in(field: str, record_ids: list, table_name: Optional[str] = None) -> 'Expr':
        """Create an IN expression for RecordID fields.
        
        This method handles various RecordID formats in the list.
        
        Args:
            field: The field name
            record_ids: List of RecordIDs in any supported format
            table_name: Optional table name for short ID formats
            
        Returns:
            An expression for field IN [record_ids]
            
        Examples:
            >>> Expr.record_in("user_id", ["user:123", "user%3A456", "789"], "user")
        """
        normalized_ids = RecordIdUtils.batch_normalize(record_ids, table_name)
        if not normalized_ids:
            # If no IDs could be normalized, fall back to original list
            return Expr(f"{field} IN {escape_literal([str(rid) for rid in record_ids])}")
        return Expr(f"{field} IN [{', '.join(normalized_ids)}]")
    
    @staticmethod
    def record_ne(field: str, record_id: Any, table_name: Optional[str] = None) -> 'Expr':
        """Create a not-equal expression for RecordID fields.
        
        Args:
            field: The field name
            record_id: The RecordID in any supported format
            table_name: Optional table name for short ID format
            
        Returns:
            An expression for field != record_id
        """
        normalized_id = RecordIdUtils.normalize_record_id(record_id, table_name)
        if normalized_id is None:
            return Expr(f"{field} != {escape_literal(str(record_id))}")
        return Expr(f"{field} != {normalized_id}")
    
    @staticmethod
    def id_eq(record_id: Any, table_name: Optional[str] = None) -> 'Expr':
        """Create an equality expression for the id field specifically.
        
        This is a convenience method for the common case of filtering by ID.
        
        Args:
            record_id: The RecordID in any supported format
            table_name: Optional table name for short ID format
            
        Returns:
            An expression for id = record_id
            
        Examples:
            >>> Expr.id_eq("user:123")
            >>> Expr.id_eq("user%3A123")  # URL-encoded
            >>> Expr.id_eq("123", "user")  # Short format
        """
        return Expr.record_eq("id", record_id, table_name)
    
    @staticmethod
    def id_in(record_ids: list, table_name: Optional[str] = None) -> 'Expr':
        """Create an IN expression for the id field specifically.
        
        Args:
            record_ids: List of RecordIDs in any supported format
            table_name: Optional table name for short ID formats
            
        Returns:
            An expression for id IN [record_ids]
        """
        return Expr.record_in("id", record_ids, table_name)