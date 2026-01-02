from typing import Any, Dict, List, Type, TYPE_CHECKING, Optional
from .fields import Field
from .exceptions import ValidationError

if TYPE_CHECKING:
    from .fields import Field

class EmbeddedDocumentMetaclass(type):
    """Metaclass for EmbeddedDocument classes."""

    def __new__(mcs, name: str, bases: tuple, attrs: Dict[str, Any]) -> Type:
        # Skip processing for the base EmbeddedDocument class
        if name == 'EmbeddedDocument' and attrs.get('__module__') == __name__:
            return super().__new__(mcs, name, bases, attrs)

        # Process fields
        fields: Dict[str, Field] = {}
        fields_ordered: List[str] = []

        # Inherit fields from parent classes
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)
                fields_ordered.extend(base._fields_ordered)

        # Add fields from current class
        for attr_name, attr_value in list(attrs.items()):
            if isinstance(attr_value, Field):
                fields[attr_name] = attr_value
                fields_ordered.append(attr_name)
                
                # Set field name
                attr_value.name = attr_name
                
                # Set db_field if not set
                if not attr_value.db_field:
                    attr_value.db_field = attr_name

        attrs['_fields'] = fields
        attrs['_fields_ordered'] = fields_ordered

        return super().__new__(mcs, name, bases, attrs)


class EmbeddedDocument(metaclass=EmbeddedDocumentMetaclass):
    """Base class for embedded documents."""
    
    _parent: Any = None
    _parent_field: Optional[str] = None

    def __init__(self, **values: Any) -> None:
        self._data: Dict[str, Any] = {}
        self._parent = None
        self._parent_field = None
        
        # Set default values
        for field_name, field in self._fields.items():
            value = field.default
            if callable(value):
                value = value()
            self._data[field_name] = value

        # Set values from kwargs
        for key, value in values.items():
            if key in self._fields:
                setattr(self, key, value)
            else:
                self._data[key] = value

    def _set_parent(self, parent: Any, field_name: str) -> None:
        self._parent = parent
        self._parent_field = field_name
        
    def _mark_changed(self) -> None:
        if self._parent and self._parent_field and hasattr(self._parent, '_mark_field_changed'):
            self._parent._mark_field_changed(self._parent_field)

    def __getattr__(self, name: str) -> Any:
        if name in self._fields:
            return self._data.get(name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            super().__setattr__(name, value)
        elif name in self._fields:
            field = self._fields[name]
            self._data[name] = field.validate(value)
            self._mark_changed()
        else:
            super().__setattr__(name, value)
            # If we allow dynamic fields:
            self._data[name] = value
            self._mark_changed()

    def validate(self) -> None:
        """Validate all fields."""
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            field.validate(value)

    def to_db(self) -> Dict[str, Any]:
        """Convert to database representation."""
        result = {}
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            if value is not None or field.required:
                db_field = field.db_field or field_name
                result[db_field] = field.to_db(value)
        
        # Include extra fields (if any)
        for k, v in self._data.items():
            if k not in self._fields:
                result[k] = v
                
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {}
        for k, v in self._data.items():
             # Handle nested embedded documents
            if hasattr(v, 'to_dict') and callable(v.to_dict):
                 result[k] = v.to_dict()
            else:
                result[k] = v
        return result

    @classmethod
    def from_db(cls, data: Dict[str, Any]) -> 'EmbeddedDocument':
        """Create from database data."""
        instance = cls()
        
        if not isinstance(data, dict):
            # If not a dict, return vanilla instance or handle error?
            return instance

        # Handle fields
        for field_name, field in instance._fields.items():
            db_field = field.db_field or field_name
            if db_field in data:
                instance._data[field_name] = field.from_db(data[db_field])
        
        # Handle extra fields
        for k, v in data.items():
             # Check if it was handled by a known field
            is_known = False
            for f in instance._fields.values():
                if f.db_field == k or (f.name == k and f.db_field is None):
                    is_known = True
                    break
            
            if not is_known:
                instance._data[k] = v

        return instance
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, EmbeddedDocument):
             return self.to_db() == other.to_db()
        return False
        
    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._data.items())
        return f"{self.__class__.__name__}({fields})"
