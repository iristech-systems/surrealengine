from typing import Any, Dict, List, Optional

from .base import Field

class ListField(Field):
    """List field type.

    This field type stores lists of values and provides validation and
    conversion for the items in the list. The items can be of a specific
    field type, which is used to validate and convert each item.

    Attributes:
        field_type: The field type for items in the list
    """

    def __init__(self, field_type: Optional[Field] = None, **kwargs: Any) -> None:
        """Initialize a new ListField.

        Args:
            field_type: The field type for items in the list
            **kwargs: Additional arguments to pass to the parent class
        """
        self.field_type = field_type
        super().__init__(**kwargs)
        self.py_type = list

    def validate(self, value: Any) -> Optional[List[Any]]:
        """Validate the list value.

        This method checks if the value is a valid list and validates each
        item in the list using the field_type if provided.

        Args:
            value: The value to validate

        Returns:
            The validated list value

        Raises:
            TypeError: If the value is not a list
            ValueError: If an item in the list fails validation
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, list):
                raise TypeError(f"Expected list for field '{self.name}', got {type(value)}")

            if self.field_type:
                for i, item in enumerate(value):
                    if isinstance(self.field_type, Field):
                        try:
                            value[i] = self.field_type.validate(item)
                        except (TypeError, ValueError) as e:
                            raise ValueError(f"Error validating item {i} in list field '{self.name}': {str(e)}")
        return value

    def to_db(self, value: Optional[List[Any]]) -> Optional[List[Any]]:
        """Convert Python list to database representation.

        This method converts a Python list to a database representation by
        converting each item using the field_type if provided.

        Args:
            value: The Python list to convert

        Returns:
            The database representation of the list
        """
        if value is not None and self.field_type:
            return [self.field_type.to_db(item) for item in value]
        return value

    def from_db(self, value: Optional[List[Any]]) -> Optional[List[Any]]:
        """Convert database list to Python representation.

        This method converts a database list to a Python representation by
        converting each item using the field_type if provided.

        Args:
            value: The database list to convert

        Returns:
            The Python representation of the list
        """
        if value is not None and self.field_type:
            return [self.field_type.from_db(item) for item in value]
        return value


class DictField(Field):
    """Dict field type.

    This field type stores dictionaries of values and provides validation and
    conversion for the values in the dictionary. The values can be of a specific
    field type, which is used to validate and convert each value.

    Attributes:
        field_type: The field type for values in the dictionary
    """

    def __init__(self, field_type: Optional[Field] = None, **kwargs: Any) -> None:
        """Initialize a new DictField.

        Args:
            field_type: The field type for values in the dictionary
            **kwargs: Additional arguments to pass to the parent class
        """
        self.field_type = field_type
        super().__init__(**kwargs)
        self.py_type = dict

    def validate(self, value: Any) -> Optional[Dict[str, Any]]:
        """Validate the dictionary value.

        This method checks if the value is a valid dictionary and validates each
        value in the dictionary using the field_type if provided.

        Args:
            value: The value to validate

        Returns:
            The validated dictionary value

        Raises:
            TypeError: If the value is not a dictionary
            ValueError: If a value in the dictionary fails validation
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, dict):
                raise TypeError(f"Expected dict for field '{self.name}', got {type(value)}")

            if self.field_type:
                for key, item in value.items():
                    if isinstance(self.field_type, Field):
                        try:
                            value[key] = self.field_type.validate(item)
                        except (TypeError, ValueError) as e:
                            raise ValueError(f"Error validating key '{key}' in dict field '{self.name}': {str(e)}")
        return value

    def to_db(self, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert Python dictionary to database representation.

        This method converts a Python dictionary to a database representation by
        converting each value using the field_type if provided.

        Args:
            value: The Python dictionary to convert

        Returns:
            The database representation of the dictionary
        """
        if value is not None and self.field_type and isinstance(self.field_type, Field):
            return {key: self.field_type.to_db(item) for key, item in value.items()}
        return value

    def from_db(self, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert database dictionary to Python representation.

        This method converts a database dictionary to a Python representation by
        converting each value using the field_type if provided.

        Args:
            value: The database dictionary to convert

        Returns:
            The Python representation of the dictionary
        """
        if value is not None and self.field_type and isinstance(self.field_type, Field):
            return {key: self.field_type.from_db(item) for key, item in value.items()}
        return value


class SetField(ListField):
    """Set field type.

    This field type stores sets of unique values and provides validation and
    conversion for the items in the set. Values are automatically deduplicated.

    Example:
        class User(Document):
            tags = SetField(StringField())
    """

    def validate(self, value: Any) -> Optional[List[Any]]:
        """Validate the list value and ensure uniqueness.

        This method checks if the value is a valid list and validates each
        item in the list using the field_type if provided. It also ensures
        that all items in the list are unique.

        Args:
            value: The value to validate

        Returns:
            The validated and deduplicated list value
        """
        value = super().validate(value)
        if value is not None:
            # Deduplicate values during validation
            deduplicated = []
            seen = set()
            for item in value:
                # Use a string representation for comparison to handle non-hashable types
                item_str = str(item)
                if item_str not in seen:
                    seen.add(item_str)
                    deduplicated.append(item)
            return deduplicated
        return value

    def to_db(self, value: Optional[List[Any]]) -> Optional[List[Any]]:
        """Convert Python list to database representation with deduplication.
        """
        if value is not None:
            # Deduplicate values before sending to DB
            deduplicated = []
            for item in value:
                db_item = self.field_type.to_db(item) if self.field_type else item
                if db_item not in deduplicated:
                    deduplicated.append(db_item)
            return deduplicated
        return value