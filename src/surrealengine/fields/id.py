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

    def __init__(self, table_name: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize a new RecordIDField.

        Args:
            table_name: Optional table name to enforce for this field
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = (str, RecordID)
        self.table_name = table_name

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
        validated = super().validate(value)
        if validated is not None:
            if isinstance(validated, RecordID):
                pass
            elif isinstance(validated, str):
                # Check if it's in the format "table:id"
                if ':' not in validated:
                    raise ValueError(f"Invalid record ID format for field '{self.name}', expected 'table:id'")
            elif isinstance(validated, (list, tuple)) and len(validated) == 2:
                # Convert [table, id] to RecordID
                table, id_val = validated
                if not isinstance(table, str) or not table:
                     raise ValueError(f"Invalid table name in record ID for field '{self.name}'")
                validated = RecordID(table, id_val)
            else:
                raise TypeError(f"Expected record ID object, string or [table, id] list/tuple for field '{self.name}', got {type(validated)}")
            
            # Check table name constraint if specified
            # Check table name constraint if specified
            if validated and self.table_name:
                if isinstance(validated, RecordID):
                    table = validated.table
                else:
                    table, _ = validated.split(':', 1)

                if table != self.table_name:
                    raise ValueError(f"RecordID must be from table '{self.table_name}', got '{table}'")
        
        return validated

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
            return value
        elif isinstance(value, str) and ':' in value:
             table, id_val = value.split(':', 1)
             return RecordID(table, id_val)
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            table, id_val = value
            return RecordID(table, id_val)

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