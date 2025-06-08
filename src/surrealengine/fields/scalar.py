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
    """

    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None,
                 regex: Optional[str] = None, choices: Optional[list] = None, **kwargs: Any) -> None:
        """Initialize a new StringField.

        Args:
            min_length: Minimum length of the string
            max_length: Maximum length of the string
            regex: Regular expression pattern to match
            **kwargs: Additional arguments to pass to the parent class
        """
        self.min_length = min_length
        self.max_length = max_length
        self.regex: Optional[Pattern] = re.compile(regex) if regex else None
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
    """

    def __init__(self, min_value: Optional[Union[int, float]] = None,
                 max_value: Optional[Union[int, float]] = None, **kwargs: Any) -> None:
        """Initialize a new NumberField.

        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            **kwargs: Additional arguments to pass to the parent class
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
            if not isinstance(value, (int, float)):
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
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new IntField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
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
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new FloatField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
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
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new BooleanField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
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