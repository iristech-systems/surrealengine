import datetime
import re


class Field:
    """Base class for all field types."""

    def __init__(self, required=False, default=None, db_field=None):
        self.required = required
        self.default = default
        self.name = None  # Will be set during document class creation
        self.db_field = db_field

    def validate(self, value):
        """Validate the field value."""
        if value is None and self.required:
            raise ValueError(f"Field '{self.name}' is required")
        return value

    def to_db(self, value):
        """Convert Python value to database representation."""
        return value

    def from_db(self, value):
        """Convert database value to Python representation."""
        return value


class StringField(Field):
    """String field type."""

    def __init__(self, min_length=None, max_length=None, regex=None, **kwargs):
        self.min_length = min_length
        self.max_length = max_length
        self.regex = re.compile(regex) if regex else None
        super().__init__(**kwargs)

    def validate(self, value):
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
    """Base class for numeric fields."""

    def __init__(self, min_value=None, max_value=None, **kwargs):
        self.min_value = min_value
        self.max_value = max_value
        super().__init__(**kwargs)

    def validate(self, value):
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
    """Integer field type."""

    def validate(self, value):
        value = super().validate(value)
        if value is not None and not isinstance(value, int):
            raise TypeError(f"Expected integer for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value):
        if value is not None:
            return int(value)
        return value


class FloatField(NumberField):
    """Float field type."""

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                raise TypeError(f"Expected float for field '{self.name}', got {type(value)}")
        return value


class BooleanField(Field):
    """Boolean field type."""

    def validate(self, value):
        value = super().validate(value)
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"Expected boolean for field '{self.name}', got {type(value)}")
        return value


class DateTimeField(Field):
    """DateTime field type."""

    def validate(self, value):
        value = super().validate(value)
        if value is not None and not isinstance(value, datetime.datetime):
            try:
                return datetime.datetime.fromisoformat(value)
            except (TypeError, ValueError):
                raise TypeError(f"Expected datetime for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value):
        if value is not None:
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except ValueError:
                    pass
            if isinstance(value, datetime.datetime):
                return value.isoformat()
        return value

    def from_db(self, value):
        if value is not None and isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                pass
        return value


class ListField(Field):
    """List field type."""

    def __init__(self, field_type=None, **kwargs):
        self.field_type = field_type
        super().__init__(**kwargs)

    def validate(self, value):
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

    def to_db(self, value):
        if value is not None and self.field_type:
            return [self.field_type.to_db(item) for item in value]
        return value

    def from_db(self, value):
        if value is not None and self.field_type:
            return [self.field_type.from_db(item) for item in value]
        return value


class DictField(Field):
    """Dict field type."""

    def __init__(self, field_type=None, **kwargs):
        self.field_type = field_type
        super().__init__(**kwargs)

    def validate(self, value):
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

    def to_db(self, value):
        if value is not None and self.field_type:
            return {key: self.field_type.to_db(item) for key, item in value.items()}
        return value

    def from_db(self, value):
        if value is not None and self.field_type:
            return {key: self.field_type.from_db(item) for key, item in value.items()}
        return value


class ReferenceField(Field):
    """Reference to another document."""

    def __init__(self, document_type, **kwargs):
        self.document_type = document_type
        super().__init__(**kwargs)

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, (self.document_type, str, dict)):
                raise TypeError(
                    f"Expected {self.document_type.__name__}, id string, or record dict for field '{self.name}', got {type(value)}")

            if isinstance(value, self.document_type) and value.id is None:
                raise ValueError(f"Cannot reference an unsaved {self.document_type.__name__} document")

        return value

    def to_db(self, value):
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

    def from_db(self, value):
        if isinstance(value, str) and ':' in value:
            # This is just the ID reference, actual dereferencing
            # will be done in a separate query
            return value
        return value


class GeometryField(Field):
    """Base field for geometry types."""

    def validate(self, value):
        value = super().validate(value)
        if value is not None and not isinstance(value, dict):
            raise TypeError(f"Expected GeoJSON object for field '{self.name}', got {type(value)}")
        return value


class RelationField(Field):
    """Field representing a relation between documents."""

    def __init__(self, to_document, **kwargs):
        self.to_document = to_document
        super().__init__(**kwargs)

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, (self.to_document, str, dict)):
                raise TypeError(
                    f"Expected {self.to_document.__name__}, id string, or record dict for field '{self.name}', got {type(value)}")

        return value

    def to_db(self, value):
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

    def from_db(self, value):
        if isinstance(value, str) and ':' in value:
            # This is just the ID reference, actual dereferencing
            # will be done in a separate query
            return value
        return value


class FutureField(Field):#todo
    """Field for future (computed) values"""

    def __init__(self, computation_expression, **kwargs):
        self.computation_expression = computation_expression
        super().__init__(**kwargs)

    def to_db(self, value):
        # For future fields, we return a special SurrealDB syntax
        return f"<future> {{ {self.computation_expression} }}"

