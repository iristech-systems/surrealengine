from typing import Any, Dict, List, Optional, Type, Union

from .base import Field

class OptionField(Field):
    """Option field type.

    This field type makes a field optional and guarantees it to be either
    None or a value of the specified type.

    Attributes:
        field_type: The field type for the value when not None
    """

    def __init__(self, field_type: Field, **kwargs: Any) -> None:
        """Initialize a new OptionField.

        Args:
            field_type: The field type for the value when not None
            **kwargs: Additional arguments to pass to the parent class
        """
        self.field_type = field_type
        super().__init__(**kwargs)
        self.py_type = Any

    def validate(self, value: Any) -> Any:
        """Validate the option value.

        This method checks if the value is None or a valid value for the field_type.

        Args:
            value: The value to validate

        Returns:
            The validated value

        Raises:
            ValueError: If the value is not None and fails validation for field_type
        """
        # Skip the parent's validation since we handle required differently
        if value is None:
            return None

        return self.field_type.validate(value)

    def to_db(self, value: Any) -> Any:
        """Convert Python value to database representation.

        This method converts a Python value to a database representation using
        the field_type's to_db method if the value is not None.

        Args:
            value: The Python value to convert

        Returns:
            The database representation of the value
        """
        if value is None:
            return None

        return self.field_type.to_db(value)

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python representation.

        This method converts a database value to a Python representation using
        the field_type's from_db method if the value is not None.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the value
        """
        if value is None:
            return None

        return self.field_type.from_db(value)


class FutureField(Field):
    """Field for future (computed) values.

    This field type represents a computed value in SurrealDB that is calculated
    at query time rather than stored in the database. It uses SurrealDB's
    <future> syntax to define a computation expression.

    Attributes:
        computation_expression: The SurrealDB expression to compute the value
    """

    def __init__(self, computation_expression: str, **kwargs: Any) -> None:
        """Initialize a new FutureField.

        Args:
            computation_expression: The SurrealDB expression to compute the value
            **kwargs: Additional arguments to pass to the parent class
        """
        self.computation_expression = computation_expression
        super().__init__(**kwargs)
        self.py_type = Any

    def to_db(self, value: Any) -> str:
        """Convert to SurrealDB future syntax.

        This method returns the SurrealDB <future> syntax with the computation
        expression, regardless of the input value.

        Args:
            value: The input value (ignored)

        Returns:
            The SurrealDB future syntax string
        """
        # For future fields, we return a special SurrealDB syntax
        return f"<future> {{ {self.computation_expression} }}"


class TableField(Field):
    """Table field type.

    This field type stores table names and provides validation and
    conversion between Python strings and SurrealDB table format.

    Example:
        ```python
        class Schema(Document):
            table_name = TableField()
            fields = DictField()
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new TableField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = str

    def validate(self, value: Any) -> Optional[str]:
        """Validate the table name.

        This method checks if the value is a valid table name.

        Args:
            value: The value to validate

        Returns:
            The validated table name

        Raises:
            TypeError: If the value is not a string
            ValueError: If the table name is invalid
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Expected string for table name in field '{self.name}', got {type(value)}")
            # Basic validation for table names
            if not value or ' ' in value:
                raise ValueError(f"Invalid table name '{value}' for field '{self.name}'")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python string to database representation.

        This method converts a Python string to a table name for storage in the database.

        Args:
            value: The Python string to convert

        Returns:
            The table name for the database
        """
        if value is not None and not isinstance(value, str):
            try:
                return str(value)
            except (TypeError, ValueError):
                pass
        return value


class RangeField(Field):
    """Field for storing ranges of values.

    This field type stores ranges of values with minimum and maximum bounds.
    It supports various types for the bounds, such as numbers, strings, and dates.

    Example:
        class PriceRange(Document):
            price_range = RangeField(min_type=FloatField(), max_type=FloatField())
            age_range = RangeField(min_type=IntField(), max_type=IntField())
    """

    def __init__(self, min_type: Field, max_type: Field = None, **kwargs: Any) -> None:
        """Initialize a new RangeField.

        Args:
            min_type: The field type for the minimum value
            max_type: The field type for the maximum value (defaults to same as min_type)
            **kwargs: Additional arguments to pass to the parent class
        """
        self.min_type = min_type
        self.max_type = max_type if max_type is not None else min_type
        super().__init__(**kwargs)
        self.py_type = Dict[str, Any]

    def validate(self, value: Any) -> Optional[Dict[str, Any]]:
        """Validate the range value.

        This method checks if the value is a valid range with minimum and maximum
        values that can be validated by the respective field types.

        Args:
            value: The value to validate

        Returns:
            The validated range value

        Raises:
            ValidationError: If the value is not a valid range
        """
        value = super().validate(value)

        if value is None:
            return None

        if not isinstance(value, dict):
            from ..exceptions import ValidationError
            raise ValidationError(f"Expected dict for field '{self.name}', got {type(value)}")

        # Ensure the range has min and max keys
        if 'min' not in value and 'max' not in value:
            from ..exceptions import ValidationError
            raise ValidationError(f"Range field '{self.name}' must have at least one of 'min' or 'max' keys")

        # Validate min value if present
        if 'min' in value:
            try:
                value['min'] = self.min_type.validate(value['min'])
            except (TypeError, ValueError) as e:
                from ..exceptions import ValidationError
                raise ValidationError(f"Invalid minimum value for field '{self.name}': {str(e)}")

        # Validate max value if present
        if 'max' in value:
            try:
                value['max'] = self.max_type.validate(value['max'])
            except (TypeError, ValueError) as e:
                from ..exceptions import ValidationError
                raise ValidationError(f"Invalid maximum value for field '{self.name}': {str(e)}")

        # Ensure min <= max if both are present
        if 'min' in value and 'max' in value:
            min_val = value['min']
            max_val = value['max']

            # Skip comparison if either value is None
            if min_val is not None and max_val is not None:
                # Try to compare the values
                try:
                    if min_val > max_val:
                        from ..exceptions import ValidationError
                        raise ValidationError(f"Minimum value ({min_val}) cannot be greater than maximum value ({max_val}) for field '{self.name}'")
                except TypeError:
                    # If values can't be compared, just skip the check
                    pass

        return value

    def to_db(self, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert Python range to database representation.

        Args:
            value: The Python range to convert

        Returns:
            The database representation of the range
        """
        if value is None:
            return None

        result = {}

        # Convert min value if present
        if 'min' in value and value['min'] is not None:
            result['min'] = self.min_type.to_db(value['min'])

        # Convert max value if present
        if 'max' in value and value['max'] is not None:
            result['max'] = self.max_type.to_db(value['max'])

        return result

    def from_db(self, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert database range to Python representation.

        Args:
            value: The database range to convert

        Returns:
            The Python representation of the range
        """
        if value is None:
            return None

        result = {}

        # Convert min value if present
        if 'min' in value and value['min'] is not None:
            result['min'] = self.min_type.from_db(value['min'])

        # Convert max value if present
        if 'max' in value and value['max'] is not None:
            result['max'] = self.max_type.from_db(value['max'])

        return result