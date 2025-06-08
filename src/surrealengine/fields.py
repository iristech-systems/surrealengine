import datetime
import re
import uuid
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Pattern, Type, TypeVar, Union, cast
from surrealdb.data.types.datetime import IsoDateTimeWrapper
from surrealdb import RecordID
from .exceptions import ValidationError
from .signals import (
    pre_validate, post_validate, pre_to_db, post_to_db,
    pre_from_db, post_from_db, SIGNAL_SUPPORT
)
import json

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
        define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
    """

    def __init__(self, required: bool = False, default: Any = None, db_field: Optional[str] = None,
                 define_schema: bool = False, indexed: bool = False, unique: bool = False, 
                 search: bool = False, analyzer: Optional[str] = None, index_with: Optional[List[str]] = None) -> None:
        """Initialize a new Field.

        Args:
            required: Whether the field is required
            default: Default value for the field
            db_field: Name of the field in the database (defaults to the field name)
            define_schema: Whether to define this field in the schema (even for SCHEMALESS tables)
            indexed: Whether the field should be indexed
            unique: Whether the index should enforce uniqueness
            search: Whether the index is a search index
            analyzer: Analyzer to use for search indexes
            index_with: List of other field names to include in the index
        """
        self.required = required
        self.default = default
        self.name: Optional[str] = None  # Will be set during document class creation
        self.db_field = db_field
        self.owner_document: Optional[Type] = None
        self.define_schema = define_schema
        self.indexed = indexed
        self.unique = unique
        self.search = search
        self.analyzer = analyzer
        self.index_with = index_with
        self.py_type = Any

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
        # Trigger pre_validate signal
        if SIGNAL_SUPPORT:
            pre_validate.send(self.__class__, field=self, value=value)

        if value is None and self.required:
            raise ValueError(f"Field '{self.name}' is required")

        result = value

        # Trigger post_validate signal
        if SIGNAL_SUPPORT:
            post_validate.send(self.__class__, field=self, value=result)

        return result

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
        # Trigger pre_to_db signal
        if SIGNAL_SUPPORT:
            pre_to_db.send(self.__class__, field=self, value=value)

        result = value

        # Trigger post_to_db signal
        if SIGNAL_SUPPORT:
            post_to_db.send(self.__class__, field=self, value=result)

        return result

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python representation.

        This method converts a value from the database to a Python value.
        Subclasses should override this method to provide type-specific conversion.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the value
        """
        # Trigger pre_from_db signal
        if SIGNAL_SUPPORT:
            pre_from_db.send(self.__class__, field=self, value=value)

        result = value

        # Trigger post_from_db signal
        if SIGNAL_SUPPORT:
            post_from_db.send(self.__class__, field=self, value=result)

        return result


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


class DateTimeField(Field):
    """DateTime field type.

    This field type stores datetime values and provides validation and
    conversion between Python datetime objects and SurrealDB datetime format.

    SurrealDB v2.0.0+ requires datetime values to have a `d` prefix or be cast
    as <datetime>. This field handles the conversion automatically, so you can
    use standard Python datetime objects in your code.

    Example:
        ```python
        class Event(Document):
            created_at = DateTimeField(default=datetime.datetime.now)
            scheduled_for = DateTimeField()

        # Python datetime objects are automatically converted to SurrealDB format
        event = Event(scheduled_for=datetime.datetime.now() + datetime.timedelta(days=7))
        await event.save()
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new DateTimeField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = datetime.datetime

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

    def to_db(self, value: Any) -> Optional[Any]:
        """Convert Python datetime to database representation.

        This method converts a Python datetime object to a SurrealDB datetime format
        for storage in the database. SurrealDB v2.0.0+ requires datetime values
        to have a `d` prefix or be cast as <datetime>.

        Args:
            value: The Python datetime to convert

        Returns:
            String with the datetime in SurrealDB format (<datetime>"iso_string")
        """
        if value is not None:
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except ValueError:
                    pass
            if isinstance(value, datetime.datetime):
                # Format as <datetime>"iso_string" to ensure SurrealDB treats it as a datetime
                return value
        return value

    def from_db(self, value: Any) -> Optional[datetime.datetime]:
        """Convert database value to Python datetime.

        This method converts a value from the database to a Python datetime object.
        It handles both string representations and IsoDateTimeWrapper instances.

        Args:
            value: The database value to convert

        Returns:
            The Python datetime object
        """
        if value is not None:
            # Handle IsoDateTimeWrapper instances
            if isinstance(value, IsoDateTimeWrapper):
                try:
                    return datetime.datetime.fromisoformat(value.dt)
                except ValueError:
                    pass
            # Handle string representations
            elif isinstance(value, str):
                # Remove `d` prefix if present (SurrealDB format)
                if value.startswith("d'") and value.endswith("'"):
                    value = value[2:-1]
                try:
                    return datetime.datetime.fromisoformat(value)
                except ValueError:
                    pass
            # Handle datetime objects directly
            elif isinstance(value, datetime.datetime):
                return value
        return value


class TimeSeriesField(DateTimeField):
    """Field for time series data.

    This field type extends DateTimeField and adds support for time series data.
    It can be used to store timestamps for time series data and supports
    additional metadata for time series operations.

    Example:
        class SensorReading(Document):
            timestamp = TimeSeriesField(index=True)
            value = FloatField()

            class Meta:
                time_series = True
                time_field = "timestamp"
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new TimeSeriesField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Optional[datetime.datetime]:
        """Validate the timestamp value.

        This method checks if the value is a valid timestamp for time series data.

        Args:
            value: The value to validate

        Returns:
            The validated timestamp value
        """
        return super().validate(value)


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
        self.py_type = Union[Type, str, dict]

    def validate(self, value: Any) -> Any:
        """Validate the reference value.

        This method checks if the value is a valid reference to another document.
        It accepts a document instance, an ID string, a dictionary with an ID, or a RecordID object.

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
            if not isinstance(value, (self.document_type, str, dict, RecordID)):
                raise TypeError(
                    f"Expected {self.document_type.__name__}, id string, record dict, or RecordID for field '{self.name}', got {type(value)}")

            if isinstance(value, self.document_type) and value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")

        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python reference to database representation.

        This method converts a Python reference (document instance, ID string,
        dictionary with an ID, or RecordID object) to a database representation.

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

        # If it's a RecordID object
        if isinstance(value, RecordID):
            return str(value)

        # If it's a document instance
        if isinstance(value, self.document_type):
            if value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")
            return value.id

        # If it's a dict (partial reference)
        if isinstance(value, dict) and value.get('id'):
            return value['id']

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
    """Field for handling geometric data in SurrealDB.

    This field validates and processes geometric data according to SurrealDB's
    geometry specification. It supports various geometry types including Point,
    LineString, Polygon, MultiPoint, MultiLineString, and MultiPolygon.

    Attributes:
        required (bool): Whether the field is required. Defaults to False.

    Example:
        ```python
        class Location(Document):
            point = GeometryField()

        # Using GeometryPoint for precise coordinate handling
        from surrealengine.geometry import GeometryPoint
        loc = Location(point=GeometryPoint([-122.4194, 37.7749]))
        ```
    """

    def __init__(self, required: bool = False, **kwargs):
        """Initialize a GeometryField.

        Args:
            required (bool, optional): Whether this field is required. Defaults to False.
            **kwargs: Additional field options to be passed to the parent Field class.
        """
        super().__init__(required=required, **kwargs)
        self.py_type = dict

    def validate(self, value):
        """Validate geometry data.

        Ensures the geometry data follows SurrealDB's expected format with proper structure
        and coordinates. Does not modify the numeric values to preserve SurrealDB's
        native geometry handling.

        Args:
            value: The geometry value to validate. Can be a GeometryPoint object or
                  a dict with 'type' and 'coordinates' fields.

        Returns:
            dict: The validated geometry data.

        Raises:
            ValidationError: If the geometry data is invalid or improperly formatted.
        """
        if value is None:
            if self.required:
                raise ValidationError("This field is required")
            return None

        # Handle GeometryPoint and other Geometry objects
        if hasattr(value, 'to_json'):
            return value.to_json()

        if not isinstance(value, dict):
            raise ValidationError("Geometry value must be a dictionary")

        if "type" not in value or "coordinates" not in value:
            raise ValidationError("Geometry must have 'type' and 'coordinates' fields")

        if not isinstance(value["coordinates"], list):
            raise ValidationError("Coordinates must be a list")

        # Validate structure based on geometry type without modifying values
        if value["type"] == "Point":
            if len(value["coordinates"]) != 2:
                raise ValidationError("Point coordinates must be a list of two numbers")
        elif value["type"] in ("LineString", "MultiPoint"):
            if not all(isinstance(point, list) and len(point) == 2 for point in value["coordinates"]):
                raise ValidationError("LineString/MultiPoint coordinates must be a list of [x,y] points")
        elif value["type"] in ("Polygon", "MultiLineString"):
            if not all(isinstance(line, list) and
                       all(isinstance(point, list) and len(point) == 2 for point in line)
                       for line in value["coordinates"]):
                raise ValidationError("Polygon/MultiLineString must be a list of coordinate arrays")
        elif value["type"] == "MultiPolygon":
            if not all(isinstance(polygon, list) and
                       all(isinstance(line, list) and
                           all(isinstance(point, list) and len(point) == 2 for point in line)
                           for line in polygon)
                       for polygon in value["coordinates"]):
                raise ValidationError("MultiPolygon must be a list of polygon arrays")

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
        self.py_type = Union[Type, str, dict]

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

    This field type stores decimal values with arbitrary precision using Python''s
    Decimal class. It provides validation to ensure the value is a valid decimal."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new DecimalField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = Decimal

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

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new DurationField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = datetime.timedelta

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

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new BytesField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = bytes

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

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new RegexField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = Pattern

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


class UUIDField(Field):
    """UUID field type.

    This field type stores UUID values and provides validation and
    conversion between Python UUID objects and SurrealDB UUID format.

    Example:
        ```python
        class User(Document):
            id = UUIDField(default=uuid.uuid4)
            api_key = UUIDField()
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new UUIDField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = uuid.UUID

    def validate(self, value: Any) -> Optional[uuid.UUID]:
        """Validate the UUID value.

        This method checks if the value is a valid UUID or can be
        converted to a UUID.

        Args:
            value: The value to validate

        Returns:
            The validated UUID value

        Raises:
            TypeError: If the value cannot be converted to a UUID
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, uuid.UUID):
                return value
            try:
                return uuid.UUID(str(value))
            except (ValueError, TypeError, AttributeError):
                raise TypeError(f"Expected UUID for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python UUID to database representation.

        This method converts a Python UUID object to a string for storage in the database.

        Args:
            value: The Python UUID to convert

        Returns:
            The string representation of the UUID for the database
        """
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            try:
                return str(uuid.UUID(str(value)))
            except (ValueError, TypeError, AttributeError):
                pass
        return value

    def from_db(self, value: Any) -> Optional[uuid.UUID]:
        """Convert database value to Python UUID.

        This method converts a string from the database to a Python UUID object.

        Args:
            value: The database value to convert

        Returns:
            The Python UUID object
        """
        if value is not None:
            if isinstance(value, uuid.UUID):
                return value
            try:
                return uuid.UUID(str(value))
            except (ValueError, TypeError, AttributeError):
                pass
        return value


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

        if isinstance(value, str) and ':' in value:
            return value
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            table, id_val = value
            return f"{table}:{id_val}"

        return value

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


class LiteralField(Field):
    """Field for union/enum-like values.

    Allows a field to accept multiple different types or specific values,
    similar to a union or enum type in other languages.

    Example:
        class Product(Document):
            status = LiteralField(["active", "discontinued", "out_of_stock"])
            id_or_name = LiteralField([IntField(), StringField()])
    """

    def __init__(self, allowed_values: List[Any], **kwargs: Any) -> None:
        """Initialize a new LiteralField.

        Args:
            allowed_values: List of allowed values or field types
            **kwargs: Additional arguments to pass to the parent class
        """
        self.allowed_values = allowed_values
        self.allowed_fields = [v for v in allowed_values if isinstance(v, Field)]
        self.allowed_literals = [v for v in allowed_values if not isinstance(v, Field)]
        super().__init__(**kwargs)
        self.py_type = Union[tuple(f.py_type for f in self.allowed_fields)] if self.allowed_fields else Any

    def validate(self, value: Any) -> Any:
        """Validate that the value is one of the allowed values or types.

        Args:
            value: The value to validate

        Returns:
            The validated value

        Raises:
            ValidationError: If the value is not one of the allowed values or types
        """
        value = super().validate(value)

        if value is None:
            return None

        # Check if the value is one of the allowed literals
        if value in self.allowed_literals:
            return value

        # Try to validate with each allowed field type
        for field in self.allowed_fields:
            try:
                return field.validate(value)
            except (TypeError, ValueError):
                continue

        # If we get here, the value is not valid
        if self.allowed_literals:
            literals_str = ", ".join(repr(v) for v in self.allowed_literals)
            error_msg = f"Value for field '{self.name}' must be one of: {literals_str}"
            if self.allowed_fields:
                field_types = ", ".join(f.__class__.__name__ for f in self.allowed_fields)
                error_msg += f" or a valid value for one of these types: {field_types}"
        else:
            field_types = ", ".join(f.__class__.__name__ for f in self.allowed_fields)
            error_msg = f"Value for field '{self.name}' must be a valid value for one of these types: {field_types}"

        raise ValidationError(error_msg)

    def to_db(self, value: Any) -> Any:
        """Convert Python value to database representation.

        Args:
            value: The Python value to convert

        Returns:
            The database representation of the value
        """
        if value is None:
            return None

        # If the value is one of the allowed literals, return it as is
        if value in self.allowed_literals:
            return value

        # Try to convert with each allowed field type
        for field in self.allowed_fields:
            try:
                field.validate(value)  # Validate first to ensure it's the right type
                return field.to_db(value)
            except (TypeError, ValueError):
                continue

        # If we get here, the value should have been caught by validate()
        return value

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python representation.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the value
        """
        if value is None:
            return None

        # If the value is one of the allowed literals, return it as is
        if value in self.allowed_literals:
            return value

        # Try to convert with each allowed field type
        for field in self.allowed_fields:
            try:
                # We can't validate here because we don't know the DB representation
                # Just try to convert and see if it works
                return field.from_db(value)
            except (TypeError, ValueError):
                continue

        # If we get here, just return the value as is
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
            raise ValidationError(f"Expected dict for field '{self.name}', got {type(value)}")

        # Ensure the range has min and max keys
        if 'min' not in value and 'max' not in value:
            raise ValidationError(f"Range field '{self.name}' must have at least one of 'min' or 'max' keys")

        # Validate min value if present
        if 'min' in value:
            try:
                value['min'] = self.min_type.validate(value['min'])
            except (TypeError, ValueError) as e:
                raise ValidationError(f"Invalid minimum value for field '{self.name}': {str(e)}")

        # Validate max value if present
        if 'max' in value:
            try:
                value['max'] = self.max_type.validate(value['max'])
            except (TypeError, ValueError) as e:
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


class EmailField(StringField):
    """Field for storing email addresses with validation.

    This field type stores email addresses and validates them against a regex pattern.

    Example:
        class User(Document):
            email = EmailField(required=True)
    """

    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    def __init__(self, **kwargs: Any) -> None:
        """Initialize an EmailField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(regex=self.EMAIL_REGEX.pattern, **kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate that the value is a valid email address.

        Args:
            value: The value to validate

        Returns:
            The validated email address

        Raises:
            ValidationError: If the value is not a valid email address
        """
        if value is None and not self.required:
            return None

        if value is not None and not isinstance(value, str):
            raise ValidationError(f"EmailField '{self.name}' only accepts string values")

        return super().validate(value)


class URLField(StringField):
    """Field for storing URLs with validation.

    This field type stores URLs and validates them against a regex pattern.

    Example:
        class Website(Document):
            url = URLField(required=True)
    """

    # Simpler URL regex pattern that should match most common URLs
    URL_REGEX = re.compile(
        r'^(https?|ftp)://'  # scheme
        r'([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?'  # domain
        r'(/[a-zA-Z0-9._~:/?#[\]@!$&\'()*+,;=%-]*)?$',  # path
        re.IGNORECASE
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a URLField."""
        # Pass the pattern string directly
        super().__init__(regex=self.URL_REGEX.pattern, **kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate that the value is a valid URL.

        Args:
            value: The value to validate

        Returns:
            The validated URL

        Raises:
            ValidationError: If the value is not a valid URL
        """
        if value is None and not self.required:
            return None

        if value is not None and not isinstance(value, str):
            raise ValidationError(f"URLField '{self.name}' only accepts string values")

        return super().validate(value)




class IPAddressField(StringField):
    """Field for storing IP addresses with validation.

    This field type stores IP addresses and validates them against regex patterns
    for IPv4 and/or IPv6 addresses.

    Example:
        class Server(Document):
            ip = IPAddressField(version="ipv4")
    """

    IPV4_REGEX = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
    IPV6_REGEX = re.compile(r'^([0-9a-f]{1,4}:){7}[0-9a-f]{1,4}$', re.IGNORECASE)

    def __init__(self, version: str = 'both', **kwargs: Any) -> None:
        """Initialize an IPAddressField.

        Args:
            version: IP version to validate ('ipv4', 'ipv6', or 'both')
            **kwargs: Additional arguments to pass to the parent class
        """
        self.version = version.lower()
        if self.version not in ('ipv4', 'ipv6', 'both'):
            raise ValueError("version must be 'ipv4', 'ipv6', or 'both'")
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate that the value is a valid IP address.

        Args:
            value: The value to validate

        Returns:
            The validated IP address

        Raises:
            ValidationError: If the value is not a valid IP address
        """
        if value is None and not self.required:
            return None

        if value is not None and not isinstance(value, str):
            raise ValidationError(f"IPAddressField '{self.name}' only accepts string values")

        if value is not None:
            if self.version in ('ipv4', 'both') and self.IPV4_REGEX.match(value):
                # Validate each octet is between 0 and 255
                octets = value.split('.')
                if all(0 <= int(octet) <= 255 for octet in octets):
                    return value

            if self.version in ('ipv6', 'both') and self.IPV6_REGEX.match(value):
                return value

            raise ValidationError(f"'{value}' is not a valid IP address for field '{self.name}'")

        return value


class SlugField(StringField):
    """Field for storing URL slugs with validation.

    This field type stores URL slugs and validates them against a regex pattern.

    Example:
        class Article(Document):
            slug = SlugField(required=True)
    """

    SLUG_REGEX = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a SlugField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(regex=self.SLUG_REGEX.pattern, **kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate that the value is a valid slug.

        Args:
            value: The value to validate

        Returns:
            The validated slug

        Raises:
            ValidationError: If the value is not a valid slug
        """
        if value is None and not self.required:
            return None

        if value is not None and not isinstance(value, str):
            raise ValidationError(f"SlugField '{self.name}' only accepts string values")

        return super().validate(value)


class ChoiceField(Field):
    """Field for storing values from a predefined set of choices.

    This field type stores values from a predefined set of choices and validates
    that the value is one of the allowed choices.

    Example:
        class Product(Document):
            status = ChoiceField(choices=["active", "inactive", "discontinued"])
    """

    def __init__(self, choices: List[Any], **kwargs: Any) -> None:
        """Initialize a ChoiceField.

        Args:
            choices: List of valid choices
            **kwargs: Additional arguments to pass to the parent class
        """
        self.choices = choices
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Any:
        """Validate that the value is one of the predefined choices.

        Args:
            value: The value to validate

        Returns:
            The validated value

        Raises:
            ValidationError: If the value is not one of the predefined choices
        """
        value = super().validate(value)

        if value is not None and value not in self.choices:
            raise ValidationError(f"'{value}' is not a valid choice for field '{self.name}'. Valid choices are: {self.choices}")

        return value
