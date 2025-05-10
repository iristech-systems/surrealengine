import datetime
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Pattern, Type, TypeVar, Union, cast

# Type variable for field types
T = TypeVar('T')

class Field:
    """Base class for all field types.

    This class provides the foundation for all field types in the document model.
    It includes methods for validation and conversion between Python and database
    representations.

    Attributes:
        required: Whether the field is required
        default: Default value for the field
        name: Name of the field (set during document class creation)
        db_field: Name of the field in the database
        owner_document: The document class that owns this field
    """

    def __init__(self, required: bool = False, default: Any = None, db_field: Optional[str] = None) -> None:
        """Initialize a new Field.

        Args:
            required: Whether the field is required
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
        """
        self.required = required
        self.default = default
        self.name: Optional[str] = None  # Will be set during document class creation
        self.db_field = db_field
        self.owner_document: Optional[Type] = None

    def validate(self, value: Any) -> Any:
        """Validate the field value.

        This method checks if the value is valid for this field type.
        Subclasses should override this method to provide type-specific validation.

        Args:
            value: The value to validate

        Returns:
            The validated value

        Raises:
            ValueError: If the value is invalid
        """
        if value is None and self.required:
            raise ValueError(f"Field '{self.name}' is required")
        return value

    def to_db(self, value: Any) -> Any:
        """Convert Python value to database representation.

        This method converts a Python value to a representation that can be
        stored in the database. Subclasses should override this method to
        provide type-specific conversion.

        Args:
            value: The Python value to convert

        Returns:
            The database representation of the value
        """
        return value

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python representation.

        This method converts a value from the database to a Python value.
        Subclasses should override this method to provide type-specific conversion.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the value
        """
        return value


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
                 regex: Optional[str] = None, **kwargs: Any) -> None:
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
        super().__init__(**kwargs)

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


class DateTimeField(Field):
    """DateTime field type.

    This field type stores datetime values and provides validation and
    conversion between Python datetime objects and ISO format strings.
    """

    def validate(self, value: Any) -> Optional[datetime.datetime]:
        """Validate the datetime value.

        This method checks if the value is a valid datetime or can be
        converted to a datetime from an ISO format string.

        Args:
            value: The value to validate

        Returns:
            The validated datetime value

        Raises:
            TypeError: If the value cannot be converted to a datetime
        """
        value = super().validate(value)
        if value is not None and not isinstance(value, datetime.datetime):
            try:
                return datetime.datetime.fromisoformat(value)
            except (TypeError, ValueError):
                raise TypeError(f"Expected datetime for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python datetime to database representation.

        This method converts a Python datetime object to an ISO format string
        for storage in the database.

        Args:
            value: The Python datetime to convert

        Returns:
            The ISO format string for the database
        """
        if value is not None:
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except ValueError:
                    pass
            if isinstance(value, datetime.datetime):
                return value.isoformat()
        return value

    def from_db(self, value: Any) -> Optional[datetime.datetime]:
        """Convert database value to Python datetime.

        This method converts an ISO format string from the database to a
        Python datetime object.

        Args:
            value: The database value to convert

        Returns:
            The Python datetime object
        """
        if value is not None and isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                pass
        return value


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
        if value is not None and self.field_type:
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
        if value is not None and self.field_type:
            return {key: self.field_type.from_db(item) for key, item in value.items()}
        return value


class ReferenceField(Field):
    """Reference to another document.

    This field type stores references to other documents in the database.
    It can accept a document instance, an ID string, or a dictionary with an ID.

    Attributes:
        document_type: The type of document being referenced
    """

    def __init__(self, document_type: Type, **kwargs: Any) -> None:
        """Initialize a new ReferenceField.

        Args:
            document_type: The type of document being referenced
            **kwargs: Additional arguments to pass to the parent class
        """
        self.document_type = document_type
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Any:
        """Validate the reference value.

        This method checks if the value is a valid reference to another document.
        It accepts a document instance, an ID string, or a dictionary with an ID.

        Args:
            value: The value to validate

        Returns:
            The validated reference value

        Raises:
            TypeError: If the value is not a valid reference
            ValueError: If the referenced document is not saved
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, (self.document_type, str, dict)):
                raise TypeError(
                    f"Expected {self.document_type.__name__}, id string, or record dict for field '{self.name}', got {type(value)}")

            if isinstance(value, self.document_type) and value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")

        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python reference to database representation.

        This method converts a Python reference (document instance, ID string,
        or dictionary with an ID) to a database representation.

        Args:
            value: The Python reference to convert

        Returns:
            The database representation of the reference

        Raises:
            ValueError: If the referenced document is not saved
        """
        if value is None:
            return None

        # If it's already a record ID string
        if isinstance(value, str):
            return value

        # If it's a document instance
        if isinstance(value, self.document_type):
            if value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")
            return f"{self.document_type._meta['collection']}:{value.id}"

        # If it's a dict (partial reference)
        if isinstance(value, dict) and value.get('id'):
            return f"{self.document_type._meta['collection']}:{value['id']}"

        return value

    def from_db(self, value: Any) -> Any:
        """Convert database reference to Python representation.

        This method converts a database reference to a Python representation.
        For string references with a colon, it returns the string as is.

        Args:
            value: The database reference to convert

        Returns:
            The Python representation of the reference
        """
        if isinstance(value, str) and ':' in value:
            # This is just the ID reference, actual dereferencing
            # will be done in a separate query
            return value
        return value


class GeometryField(Field):
    """Base field for geometry types.

    This field type stores GeoJSON objects for representing geographic features.
    It validates that the value is a dictionary (GeoJSON object).
    """

    def validate(self, value: Any) -> Optional[Dict[str, Any]]:
        """Validate the geometry value.

        This method checks if the value is a valid GeoJSON object (dictionary).

        Args:
            value: The value to validate

        Returns:
            The validated geometry value

        Raises:
            TypeError: If the value is not a dictionary
        """
        value = super().validate(value)
        if value is not None and not isinstance(value, dict):
            raise TypeError(f"Expected GeoJSON object for field '{self.name}', got {type(value)}")
        return value


class RelationField(Field):
    """Field representing a relation between documents.

    This field type stores relations between documents in the database.
    It can accept a document instance, an ID string, or a dictionary with an ID.

    Attributes:
        to_document: The type of document being related to
    """

    def __init__(self, to_document: Type, **kwargs: Any) -> None:
        """Initialize a new RelationField.

        Args:
            to_document: The type of document being related to
            **kwargs: Additional arguments to pass to the parent class
        """
        self.to_document = to_document
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Any:
        """Validate the relation value.

        This method checks if the value is a valid relation to another document.
        It accepts a document instance, an ID string, or a dictionary with an ID.

        Args:
            value: The value to validate

        Returns:
            The validated relation value

        Raises:
            TypeError: If the value is not a valid relation
        """
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, (self.to_document, str, dict)):
                raise TypeError(
                    f"Expected {self.to_document.__name__}, id string, or record dict for field '{self.name}', got {type(value)}")

        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python relation to database representation.

        This method converts a Python relation (document instance, ID string,
        or dictionary with an ID) to a database representation.

        Args:
            value: The Python relation to convert

        Returns:
            The database representation of the relation

        Raises:
            ValueError: If the related document is not saved
        """
        if value is None:
            return None

        # If it's already a record ID string
        if isinstance(value, str):
            if ':' not in value:
                return f"{self.to_document._get_collection_name()}:{value}"
            return value

        # If it's a document instance
        if isinstance(value, self.to_document):
            if value.id is None:
                raise ValueError(f"Cannot relate to an unsaved {self.to_document.__name__} document")
            return f"{self.to_document._get_collection_name()}:{value.id}"

        # If it's a dict
        if isinstance(value, dict) and value.get('id'):
            return f"{self.to_document._get_collection_name()}:{value['id']}"

        return value

    def from_db(self, value: Any) -> Any:
        """Convert database relation to Python representation.

        This method converts a database relation to a Python representation.
        For string relations with a colon, it returns the string as is.

        Args:
            value: The database relation to convert

        Returns:
            The Python representation of the relation
        """
        if isinstance(value, str) and ':' in value:
            # This is just the ID reference, actual dereferencing
            # will be done in a separate query
            return value
        return value


class DecimalField(NumberField):
    """Decimal field type.

    This field type stores decimal values with arbitrary precision using Python's
    Decimal class. It provides validation to ensure the value is a valid decimal.
    """

    def validate(self, value: Any) -> Optional[Decimal]:
        """Validate the decimal value.

        This method checks if the value is a valid decimal or can be
        converted to a decimal.

        Args:
            value: The value to validate

        Returns:
            The validated decimal value

        Raises:
            TypeError: If the value cannot be converted to a decimal
        """
        value = super().validate(value)
        if value is not None:
            try:
                return Decimal(str(value))
            except (TypeError, ValueError):
                raise TypeError(f"Expected decimal for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python decimal to database representation.

        This method converts a Python decimal to a string for storage in the database.

        Args:
            value: The Python decimal to convert

        Returns:
            The string representation of the decimal for the database
        """
        if value is not None:
            return str(Decimal(str(value)))
        return value

    def from_db(self, value: Any) -> Optional[Decimal]:
        """Convert database value to Python decimal.

        This method converts a string from the database to a Python Decimal object.

        Args:
            value: The database value to convert

        Returns:
            The Python Decimal object
        """
        if value is not None:
            try:
                return Decimal(str(value))
            except (TypeError, ValueError):
                pass
        return value


class DurationField(Field):
    """Duration field type.

    This field type stores durations of time and provides validation and
    conversion between Python timedelta objects and SurrealDB duration strings.
    """

    def validate(self, value: Any) -> Optional[datetime.timedelta]:
        """Validate the duration value.

        This method checks if the value is a valid timedelta or can be
        converted to a timedelta from a string.

        Args:
            value: The value to validate

        Returns:
            The validated timedelta value

        Raises:
            TypeError: If the value cannot be converted to a timedelta
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, datetime.timedelta):
                return value
            if isinstance(value, str):
                try:
                    # Parse SurrealDB duration format (e.g., "1y2m3d4h5m6s")
                    # This is a simplified implementation and may need to be expanded
                    total_seconds = 0
                    num_buffer = ""
                    for char in value:
                        if char.isdigit():
                            num_buffer += char
                        elif char == 'y' and num_buffer:
                            total_seconds += int(num_buffer) * 365 * 24 * 60 * 60
                            num_buffer = ""
                        elif char == 'm' and num_buffer:
                            # Ambiguous: could be month or minute
                            # Assume month if previous char was 'y', otherwise minute
                            if 'y' in value[:value.index(char)]:
                                total_seconds += int(num_buffer) * 30 * 24 * 60 * 60
                            else:
                                total_seconds += int(num_buffer) * 60
                            num_buffer = ""
                        elif char == 'd' and num_buffer:
                            total_seconds += int(num_buffer) * 24 * 60 * 60
                            num_buffer = ""
                        elif char == 'h' and num_buffer:
                            total_seconds += int(num_buffer) * 60 * 60
                            num_buffer = ""
                        elif char == 's' and num_buffer:
                            total_seconds += int(num_buffer)
                            num_buffer = ""
                    return datetime.timedelta(seconds=total_seconds)
                except (ValueError, TypeError):
                    pass
            raise TypeError(f"Expected duration for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python timedelta to database representation.

        This method converts a Python timedelta object to a SurrealDB duration string
        for storage in the database.

        Args:
            value: The Python timedelta to convert

        Returns:
            The SurrealDB duration string for the database
        """
        if value is None:
            return None

        if isinstance(value, str):
            # If it's already a string, validate it as a duration
            self.validate(value)
            return value

        if isinstance(value, datetime.timedelta):
            # Convert timedelta to SurrealDB duration format
            seconds = int(value.total_seconds())
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)

            result = ""
            if days > 0:
                result += f"{days}d"
            if hours > 0:
                result += f"{hours}h"
            if minutes > 0:
                result += f"{minutes}m"
            if seconds > 0 or not result:
                result += f"{seconds}s"

            return result

        raise TypeError(f"Cannot convert {type(value)} to duration")

    def from_db(self, value: Any) -> Optional[datetime.timedelta]:
        """Convert database value to Python timedelta.

        This method converts a SurrealDB duration string from the database to a
        Python timedelta object.

        Args:
            value: The database value to convert

        Returns:
            The Python timedelta object
        """
        if value is not None and isinstance(value, str):
            return self.validate(value)
        return value


class BytesField(Field):
    """Bytes field type.

    This field type stores binary data as byte arrays and provides validation and
    conversion between Python bytes objects and SurrealDB bytes format.
    """

    def validate(self, value: Any) -> Optional[bytes]:
        """Validate the bytes value.

        This method checks if the value is a valid bytes object or can be
        converted to bytes.

        Args:
            value: The value to validate

        Returns:
            The validated bytes value

        Raises:
            TypeError: If the value cannot be converted to bytes
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                try:
                    return value.encode('utf-8')
                except UnicodeEncodeError:
                    pass
            raise TypeError(f"Expected bytes for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python bytes to database representation.

        This method converts a Python bytes object to a SurrealDB bytes format
        for storage in the database.

        Args:
            value: The Python bytes to convert

        Returns:
            The SurrealDB bytes format for the database
        """
        if value is None:
            return None

        if isinstance(value, bytes):
            # Convert bytes to SurrealDB bytes format
            # SurrealDB uses <bytes>"base64_encoded_string" format
            import base64
            encoded = base64.b64encode(value).decode('ascii')
            return f'<bytes>"{encoded}"'

        if isinstance(value, str) and value.startswith('<bytes>"') and value.endswith('"'):
            # If it's already in SurrealDB bytes format, return as is
            return value

        raise TypeError(f"Cannot convert {type(value)} to bytes")

    def from_db(self, value: Any) -> Optional[bytes]:
        """Convert database value to Python bytes.

        This method converts a SurrealDB bytes format from the database to a
        Python bytes object.

        Args:
            value: The database value to convert

        Returns:
            The Python bytes object
        """
        if value is None:
            return None

        if isinstance(value, bytes):
            return value

        if isinstance(value, str) and value.startswith('<bytes>"') and value.endswith('"'):
            # Extract and decode the base64 encoded string
            import base64
            encoded = value[8:-1]  # Remove <bytes>" and "
            return base64.b64decode(encoded)

        return value


class RegexField(Field):
    """Regex field type.

    This field type stores regular expressions and provides validation and
    conversion between Python regex pattern objects and SurrealDB regex format.
    """

    def validate(self, value: Any) -> Optional[Pattern]:
        """Validate the regex value.

        This method checks if the value is a valid regex pattern or can be
        compiled into a regex pattern.

        Args:
            value: The value to validate

        Returns:
            The validated regex pattern

        Raises:
            TypeError: If the value cannot be compiled into a regex pattern
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, Pattern):
                return value
            if isinstance(value, str):
                try:
                    return re.compile(value)
                except re.error:
                    pass
            raise TypeError(f"Expected regex pattern for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python regex pattern to database representation.

        This method converts a Python regex pattern object to a SurrealDB regex format
        for storage in the database.

        Args:
            value: The Python regex pattern to convert

        Returns:
            The SurrealDB regex format for the database
        """
        if value is None:
            return None

        if isinstance(value, Pattern):
            # Convert Pattern to SurrealDB regex format
            # SurrealDB uses /pattern/ format
            pattern = value.pattern
            return f'/{pattern}/'

        if isinstance(value, str):
            if value.startswith('/') and value.endswith('/'):
                # If it's already in SurrealDB regex format, return as is
                return value
            else:
                # Compile to validate and then convert
                try:
                    pattern = re.compile(value).pattern
                    return f'/{pattern}/'
                except re.error:
                    pass

        raise TypeError(f"Cannot convert {type(value)} to regex")

    def from_db(self, value: Any) -> Optional[Pattern]:
        """Convert database value to Python regex pattern.

        This method converts a SurrealDB regex format from the database to a
        Python regex pattern object.

        Args:
            value: The database value to convert

        Returns:
            The Python regex pattern object
        """
        if value is None:
            return None

        if isinstance(value, Pattern):
            return value

        if isinstance(value, str) and value.startswith('/') and value.endswith('/'):
            # Extract and compile the pattern
            pattern = value[1:-1]  # Remove / and /
            try:
                return re.compile(pattern)
            except re.error:
                pass

        return value


class RangeField(Field):
    """Range field type.

    This field type stores ranges of values and provides validation and
    conversion between Python range objects and SurrealDB range format.
    """

    def __init__(self, value_type: Optional[Type] = None, **kwargs: Any) -> None:
        """Initialize a new RangeField.

        Args:
            value_type: The type of values in the range (e.g., int, float, str)
            **kwargs: Additional arguments to pass to the parent class
        """
        self.value_type = value_type
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Any:
        """Validate the range value.

        This method checks if the value is a valid range representation.

        Args:
            value: The value to validate

        Returns:
            The validated range value

        Raises:
            TypeError: If the value is not a valid range representation
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, range):
                return value
            if isinstance(value, (list, tuple)) and len(value) == 2:
                start, end = value
                if self.value_type:
                    try:
                        start = None if start is None else self.value_type(start)
                        end = None if end is None else self.value_type(end)
                    except (TypeError, ValueError):
                        raise TypeError(f"Range values must be of type {self.value_type.__name__}")
                return (start, end)
            if isinstance(value, str) and '..' in value:
                parts = value.split('..')
                if len(parts) == 2:
                    start = parts[0].strip() if parts[0].strip() else None
                    end = parts[1].strip() if parts[1].strip() else None

                    # Handle inclusive end with =
                    inclusive_end = False
                    if end and end.startswith('='):
                        inclusive_end = True
                        end = end[1:]

                    if self.value_type:
                        try:
                            start = None if start is None else self.value_type(start)
                            end = None if end is None else self.value_type(end)
                            if inclusive_end and end is not None:
                                # For inclusive end, add 1 for numeric types
                                if self.value_type == int:
                                    end += 1
                                elif self.value_type == float:
                                    end += 0.000001  # Small increment for float
                        except (TypeError, ValueError):
                            raise TypeError(f"Range values must be of type {self.value_type.__name__}")
                    return (start, end)
            raise TypeError(f"Expected range for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python range to database representation.

        This method converts a Python range object or tuple to a SurrealDB range format
        for storage in the database.

        Args:
            value: The Python range to convert

        Returns:
            The SurrealDB range format for the database
        """
        if value is None:
            return None

        if isinstance(value, range):
            # Convert range to SurrealDB range format
            start = value.start
            # range.stop is exclusive, but SurrealDB's upper bound is inclusive by default
            end = value.stop - 1 if value.stop is not None else None

            start_str = '' if start is None else str(start)
            end_str = '' if end is None else str(end)

            return f'{start_str}..{end_str}'

        if isinstance(value, (list, tuple)) and len(value) == 2:
            start, end = value
            start_str = '' if start is None else str(start)
            end_str = '' if end is None else str(end)

            return f'{start_str}..{end_str}'

        if isinstance(value, str) and '..' in value:
            # If it's already in SurrealDB range format, return as is
            return value

        raise TypeError(f"Cannot convert {type(value)} to range")

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python range representation.

        This method converts a SurrealDB range format from the database to a
        Python range object or tuple.

        Args:
            value: The database value to convert

        Returns:
            The Python range representation
        """
        if value is None:
            return None

        if isinstance(value, range):
            return value

        if isinstance(value, (list, tuple)) and len(value) == 2:
            return value

        if isinstance(value, str) and '..' in value:
            parts = value.split('..')
            if len(parts) == 2:
                start = parts[0].strip() if parts[0].strip() else None
                end = parts[1].strip() if parts[1].strip() else None

                # Handle inclusive end with =
                inclusive_end = False
                if end and end.startswith('='):
                    inclusive_end = True
                    end = end[1:]

                if self.value_type:
                    try:
                        start = None if start is None else self.value_type(start)
                        end = None if end is None else self.value_type(end)
                        if inclusive_end and end is not None:
                            # For inclusive end, add 1 for numeric types
                            if self.value_type == int:
                                end += 1
                            elif self.value_type == float:
                                end += 0.000001  # Small increment for float
                    except (TypeError, ValueError):
                        pass

                # If both start and end are integers, return a range object
                if isinstance(start, int) and isinstance(end, int):
                    return range(start, end)

                return (start, end)

        return value


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
