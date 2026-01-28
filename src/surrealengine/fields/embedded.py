from typing import Any, Optional, Type, Dict

from .base import Field
from ..embedded import EmbeddedDocument

class EmbeddedField(Field):
    """Field for storing embedded documents."""

    def __init__(self, document_type: Type[EmbeddedDocument], **kwargs: Any) -> None:
        """Initialize a new EmbeddedField.

        Args:
            document_type: The EmbeddedDocument class for this field
            **kwargs: Additional arguments
        """
        self.document_type = document_type
        super().__init__(**kwargs)
        self.py_type = document_type

    def validate(self, value: Any) -> Optional[EmbeddedDocument]:
        """Validate the embedded document."""
        if value is None:
            if self.required:
                raise ValueError(f"Field '{self.name}' is required")
            return None

        if isinstance(value, self.document_type):
            value.validate()
            return value
        
        if isinstance(value, dict):
            # Try to convert dict to embedded document
            try:
                doc = self.document_type.from_db(value)
                doc.validate()
                return doc
            except Exception as e:
                raise ValueError(f"Invalid value for EmbeddedField '{self.name}': {e}")

        raise TypeError(f"Expected {self.document_type.__name__} or dict for field '{self.name}', got {type(value)}")

    def to_db(self, value: Optional[EmbeddedDocument]) -> Optional[Dict[str, Any]]:
        """Convert embedded document to database representation."""
        if value is not None:
            if isinstance(value, self.document_type):
                return value.to_db()
            if isinstance(value, dict):
                # If it's already a dict (e.g. from raw data), ensure format is correct?
                # Ideally we want to validate it first.
                # Assuming valid if passed here, or best effort.
                return value
        return value

    def from_db(self, value: Any) -> Optional[EmbeddedDocument]:
        """Convert database representation to embedded document."""
        if value is None:
            return None
            
        if isinstance(value, self.document_type):
            return value
            
        if isinstance(value, dict):
            return self.document_type.from_db(value)
            
        return value
