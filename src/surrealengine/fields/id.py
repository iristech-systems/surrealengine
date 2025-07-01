from typing import Any, List, Optional, Tuple, Union
from surrealdb import RecordID

from .base import Field

class RecordIDField(Field):
    """RecordID field type.

    This field type stores record IDs and provides validation and
    conversion between Python values and SurrealDB record ID format.

    A RecordID consists of a table name and a unique identifier, formatted as
    `table:id`. This field can accept a string in this format, or a tuple/list
    with the table name and ID.

    Example:
        ```python
        class Reference(Document):
            target = RecordIDField()
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new RecordIDField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = str

    def validate(self, value: Any) -> Optional[str]:
        """Validate the record ID.

        This method checks if the value is a valid record ID.

        Args:
            value: The value to validate

        Returns:
            The validated record ID

        Raises:
            TypeError: If the value cannot be converted to a record ID
            ValueError: If the record ID format is invalid
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, RecordID):
                return str(value)
            elif isinstance(value, str):
                # Check if it's in the format "table:id"
                if ':' not in value:
                    raise ValueError(f"Invalid record ID format for field '{self.name}', expected 'table:id'")
                return value
            elif isinstance(value, (list, tuple)) and len(value) == 2:
                # Convert [table, id] to "table:id"
                table, id_val = value
                if not isinstance(table, str) or not table:
                    raise ValueError(f"Invalid table name in record ID for field '{self.name}'")
                return f"{table}:{id_val}"
            else:
                raise TypeError(f"Expected record ID string or [table, id] list/tuple for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python value to database representation.

        This method converts a Python value to a record ID for storage in the database.

        Args:
            value: The Python value to convert

        Returns:
            The record ID for the database
        """
        if value is None:
            return None

        if isinstance(value, RecordID):
            return str(value)
        elif isinstance(value, str) and ':' in value:
            return value
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            table, id_val = value
            return f"{table}:{id_val}"

        return str(value)

    def from_db(self, value: Any) -> Optional[str]:
        """Convert database value to Python representation.

        This method converts a record ID from the database to a Python representation.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the record ID
        """
        # Record IDs are already in the correct format from the database
        return value