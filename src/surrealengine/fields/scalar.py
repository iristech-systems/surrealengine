import re
from typing import Any, List, Optional, Pattern, Type, Union

from .base import Field

class StringField(Field):
    """String field type.

    This field type stores string values and provides validation for
    minimum length, maximum length, and regex pattern matching.

    Attributes:
        min_length: Minimum length of the string
        max_length: Maximum length of the string
        regex: Regular expression pattern to match

    Examples:
        Basic string field:

        >>> name = StringField(required=True)

        String with length constraints:

        >>> title = StringField(max_length=100, required=True)
        >>> username = StringField(min_length=3, max_length=20)

        String with regex validation:

        >>> email = StringField(regex=r'^[^@]+@[^@]+\.[^@]+$')
        >>> slug = StringField(regex=r'^[a-z0-9-]+$')

        Indexed string field:

        >>> name = StringField(indexed=True, unique=True)
        >>> category = StringField(indexed=True)

        String field with choices:

        >>> status = StringField(choices=['active', 'inactive', 'pending'])

        String field for schema definition:

        >>> name = StringField(required=True, define_schema=True)
    """

    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None,
                 regex: Optional[str] = None, choices: Optional[list] = None, **kwargs: Any) -> None:
        """Initialize a new StringField.

        Args:
            min_length: Minimum length of the string
            max_length: Maximum length of the string
            regex: Regular expression pattern to match
            choices: List of valid choices for this field
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        self.min_length = min_length
        self.max_length = max_length
        self.regex: Optional[Pattern] = re.compile(regex) if regex else None
        self.regex_pattern: Optional[str] = regex
        self.choices: Optional[list] = choices
        super().__init__(**kwargs)
        self.py_type = str

    def validate(self, value: Any) -> Optional[str]:
        """Validate the string value.

        This method checks if the value is a valid string and meets the
        constraints for minimum length, maximum length, and regex pattern.

        Args:
            value: The value to validate

        Returns:
            The validated string value

        Raises:
            TypeError: If the value is not a string
            ValueError: If the value does not meet the constraints
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Expected string for field '{self.name}', got {type(value)}")

            if self.min_length is not None and len(value) < self.min_length:
                raise ValueError(f"String value for '{self.name}' is too short")

            if self.max_length is not None and len(value) > self.max_length:
                raise ValueError(f"String value for '{self.name}' is too long")

            if self.regex and not self.regex.match(value):
                raise ValueError(f"String value for '{self.name}' does not match pattern")

            if self.choices and value not in self.choices:
                raise ValueError(f"String value for '{self.name}' is not a valid choice")

        return value


class NumberField(Field):
    """Base class for numeric fields.

    This field type is the base class for all numeric field types.
    It provides validation for minimum and maximum values.

    Attributes:
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Examples:
        Basic number field:

        >>> score = NumberField()

        Number with range constraints:

        >>> priority = NumberField(min_value=1, max_value=5, default=3)
        >>> percentage = NumberField(min_value=0, max_value=100)
        >>> age = NumberField(min_value=0)

        Required number field:

        >>> price = NumberField(min_value=0, required=True)
    """

    def __init__(self, min_value: Optional[Union[int, float]] = None,
                 max_value: Optional[Union[int, float]] = None, **kwargs: Any) -> None:
        """Initialize a new NumberField.

        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        self.min_value = min_value
        self.max_value = max_value
        super().__init__(**kwargs)
        self.py_type = Union[int, float]

    def validate(self, value: Any) -> Optional[Union[int, float]]:
        """Validate the numeric value.

        This method checks if the value is a valid number and meets the
        constraints for minimum and maximum values.

        Args:
            value: The value to validate

        Returns:
            The validated numeric value

        Raises:
            TypeError: If the value is not a number
            ValueError: If the value does not meet the constraints
        """
        value = super().validate(value)
        if value is not None:
            from decimal import Decimal
            if not isinstance(value, (int, float, Decimal)):
                raise TypeError(f"Expected number for field '{self.name}', got {type(value)}")

            if self.min_value is not None and value < self.min_value:
                raise ValueError(f"Value for '{self.name}' is too small")

            if self.max_value is not None and value > self.max_value:
                raise ValueError(f"Value for '{self.name}' is too large")

        return value


class IntField(NumberField):
    """Integer field type.

    This field type stores integer values and provides validation
    to ensure the value is an integer.

    Examples:
        Basic integer field:

        >>> age = IntField(min_value=0)
        >>> count = IntField(default=0)

        Integer with constraints:

        >>> priority = IntField(min_value=1, max_value=5, default=3)
        >>> year = IntField(min_value=1900, max_value=2100)

        Required integer:

        >>> user_id = IntField(required=True)
        >>> views = IntField(default=0, min_value=0)
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new IntField.

        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        super().__init__(**kwargs)
        self.py_type = int

    def validate(self, value: Any) -> Optional[int]:
        """Validate the integer value.

        This method checks if the value is a valid integer.

        Args:
            value: The value to validate

        Returns:
            The validated integer value

        Raises:
            TypeError: If the value is not an integer
        """
        value = super().validate(value)
        if value is not None and not isinstance(value, int):
            raise TypeError(f"Expected integer for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[int]:
        """Convert Python value to database representation.

        This method converts a Python value to an integer for storage in the database.

        Args:
            value: The Python value to convert

        Returns:
            The integer value for the database
        """
        if value is not None:
            return int(value)
        return value


class FloatField(NumberField):
    """Float field type.

    This field type stores floating-point values and provides validation
    to ensure the value can be converted to a float.

    Examples:
        Basic float field:

        >>> price = FloatField(min_value=0)
        >>> rating = FloatField(min_value=0.0, max_value=5.0)

        Float with precision:

        >>> estimated_hours = FloatField(min_value=0.1)
        >>> percentage = FloatField(min_value=0.0, max_value=100.0)

        Financial data:

        >>> balance = FloatField(default=0.0)
        >>> tax_rate = FloatField(min_value=0.0, max_value=1.0)
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new FloatField.

        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        super().__init__(**kwargs)
        self.py_type = float

    def validate(self, value: Any) -> Optional[float]:
        """Validate the float value.

        This method checks if the value can be converted to a float.

        Args:
            value: The value to validate

        Returns:
            The validated float value

        Raises:
            TypeError: If the value cannot be converted to a float
        """
        value = super().validate(value)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                raise TypeError(f"Expected float for field '{self.name}', got {type(value)}")
        return value


class BooleanField(Field):
    """Boolean field type.

    This field type stores boolean values and provides validation
    to ensure the value is a boolean.

    Examples:
        Basic boolean field:

        >>> active = BooleanField(default=True)
        >>> completed = BooleanField(default=False)

        Required boolean:

        >>> is_primary_author = BooleanField(default=True)
        >>> published = BooleanField(default=False)

        Boolean with indexing:

        >>> active = BooleanField(default=True, indexed=True)
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new BooleanField.

        Args:
            required: Whether the field is required (default: False)
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed (default: False)
            unique: Whether the index should enforce uniqueness (default: False)
            search: Whether the index is a search index (default: False)
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        super().__init__(**kwargs)
        self.py_type = bool

    def validate(self, value: Any) -> Optional[bool]:
        """Validate the boolean value.

        This method checks if the value is a valid boolean.

        Args:
            value: The value to validate

        Returns:
            The validated boolean value

        Raises:
            TypeError: If the value is not a boolean
        """
        value = super().validate(value)
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"Expected boolean for field '{self.name}', got {type(value)}")
        return value