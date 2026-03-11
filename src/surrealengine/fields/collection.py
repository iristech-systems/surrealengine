from typing import Any, Dict, List, Optional
from ..utils.tracking import TrackedList, TrackedDict

from .base import Field

class ListField(Field):
    """List field type.

    This field type stores lists of values and provides validation and
    conversion for the items in the list. The items can be of a specific
    field type, which is used to validate and convert each item.

    Attributes:
        field_type: The field type for items in the list

    Examples:
        Typed list for proper DDL (generates ``array<float>``):

        >>> embedding = ListField(item_type=float)
        >>> tags = ListField(item_type=str)

        Equivalent using a Field instance directly:

        >>> embedding = ListField(FloatField())
    """

    def __init__(self, field_type: Optional[Field] = None,
                 item_type: Optional[Any] = None,
                 max_items: Optional[int] = None,
                 surreal_functions: Optional[List[str]] = None, **kwargs: Any) -> None:
        """Initialize a new ListField.

        Args:
            field_type: The field type for items in the list (Field instance)
            item_type: Shorthand for field_type — accepts a Python primitive type
                (``float``, ``int``, ``str``, ``bool``) and auto-creates the
                corresponding Field instance.  Ignored when *field_type* is given.
            max_items: Maximum number of items allowed in the list
            surreal_functions: List of SurrealQL array functions to apply (array::sort, array::unique, etc.)
            **kwargs: Additional arguments to pass to the parent class
        """
        # Resolve item_type shorthand → Field instance
        if item_type is not None and field_type is None:
            from .scalar import FloatField, IntField, StringField, BooleanField
            _PYTHON_TO_FIELD: Dict[Any, Any] = {
                float: FloatField,
                int: IntField,
                str: StringField,
                bool: BooleanField,
            }
            if isinstance(item_type, type) and item_type in _PYTHON_TO_FIELD:
                field_type = _PYTHON_TO_FIELD[item_type]()
            elif isinstance(item_type, Field):
                field_type = item_type

        self.field_type = field_type
        self.max_items = max_items
        self.surreal_functions = surreal_functions or []
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
            ValueError: If an item in the list fails validation or max_items is exceeded
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, list) and not isinstance(value, TrackedList):
                raise TypeError(f"Expected list for field '{self.name}', got {type(value)}")

            # Check max_items constraint
            if self.max_items is not None and len(value) > self.max_items:
                raise ValueError(f"List field '{self.name}' exceeds max_items limit of {self.max_items}, got {len(value)} items")

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
        converting each item using the field_type if provided.  The return
        value is always a plain ``list`` (never a ``TrackedList`` subclass) so
        that the SurrealDB SDK's serializer receives a native type it can
        reliably encode via CBOR/JSON.

        Args:
            value: The Python list to convert

        Returns:
            The database representation of the list as a plain list
        """
        if value is not None:
            if self.field_type:
                return [self.field_type.to_db(item) for item in value]
            # Coerce TrackedList (or any list subclass) to a plain list so the
            # SDK encoder handles it as a regular array.
            return list(value)
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
            return TrackedList([self.field_type.from_db(item) for item in value])
        return TrackedList(value) if value is not None else None


class DictField(Field):
    """Dict field type.

    This field type stores dictionaries of values and provides validation and
    conversion for the values in the dictionary. The values can be of a specific
    field type, which is used to validate and convert each value.

    Attributes:
        field_type: The field type for values in the dictionary
    """

    def __init__(self, field_type: Optional[Field] = None, 
                 schema: Optional[Dict[str, Field]] = None, 
                 flexible: bool = True, **kwargs: Any) -> None:
        """Initialize a new DictField.

        Args:
            field_type: The field type for values in the dictionary
            schema: Optional schema defining specific field types for dictionary keys
            flexible: Whether to allow additional fields not defined in schema (default: True)
            **kwargs: Additional arguments to pass to the parent class
        """
        self.field_type = field_type
        self.schema = schema
        self.flexible = flexible
        super().__init__(**kwargs)
        self.py_type = dict

    def validate(self, value: Any) -> Any:
        """Validate the dictionary value.

        This method checks if the value is a valid dictionary and validates each
        value in the dictionary using the field_type if provided, or using
        specific field types from schema if available.

        Args:
            value: The value to validate

        Returns:
            The validated dictionary value

        Raises:
            TypeError: If the value is not a dictionary
            ValueError: If a value in the dictionary fails validation
        """
        validated = super().validate(value)
        if validated is not None:
            if not isinstance(validated, dict) and not isinstance(validated, TrackedDict):
                raise TypeError(f"Expected dict for field '{self.name}', got {type(validated)}")

            # Use schema-based validation if schema is provided
            if validated and self.schema:
                for key, field in self.schema.items():
                    if key in validated:
                        try:
                            validated[key] = field.validate(validated[key])
                        except (TypeError, ValueError) as e:
                            raise ValueError(f"Error validating key '{key}' in dict field '{self.name}': {str(e)}")
            # Fall back to field_type validation for all keys if no schema
            elif self.field_type:
                for key, item in validated.items():
                    if isinstance(self.field_type, Field):
                        try:
                            validated[key] = self.field_type.validate(item)
                        except (TypeError, ValueError) as e:
                            raise ValueError(f"Error validating key '{key}' in dict field '{self.name}': {str(e)}")
        
        return validated

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SurrealDB 3.0.0 removed implicit deduplication for arrays.
        # We enforce it at the database level by setting the implicit VALUE clause logic if not provided.
        # This will be handled in schema.py or via field definition, but we can store it here.
        # Usually, this is handled in schema.py during DEFINE FIELD generation, but we'll mark a flag
        self._is_set = True


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