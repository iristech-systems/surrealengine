import re
import uuid
import decimal
import base64
import socket
import urllib.parse
import io
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Pattern, Type, Union, BinaryIO

from .base import Field
from .scalar import StringField, NumberField
from ..exceptions import ValidationError

class BytesFieldWrapper:
    """File-like wrapper for BytesField data.
    
    Provides standard Python file operations for binary data stored in BytesField,
    making it easy to work with files, images, documents, and other binary content.
    
    Features:
    - Standard file operations: read(), write(), seek(), tell()
    - Context manager support (with statement)
    - Multiple read modes: read all, read chunks, readline for text
    - Write operations with automatic size tracking
    - File metadata support (filename, content_type, size)
    - Stream operations for large files
    """
    
    def __init__(self, data: bytes = b'', filename: Optional[str] = None, 
                 content_type: Optional[str] = None, metadata: Optional[dict] = None):
        """Initialize the file-like wrapper.
        
        Args:
            data: Initial binary data
            filename: Original filename (if any)
            content_type: MIME content type
            metadata: Additional file metadata
        """
        self._buffer = io.BytesIO(data)
        self.filename = filename
        self.content_type = content_type
        self.metadata = metadata or {}
        self._closed = False
        
    @property
    def closed(self) -> bool:
        """Check if the file is closed."""
        return self._closed
    
    @property
    def size(self) -> int:
        """Get the size of the data in bytes."""
        current_pos = self._buffer.tell()
        self._buffer.seek(0, io.SEEK_END)
        size = self._buffer.tell()
        self._buffer.seek(current_pos)
        return size
    
    def read(self, size: int = -1) -> bytes:
        """Read and return up to size bytes.
        
        Args:
            size: Number of bytes to read. If -1, read all remaining data.
            
        Returns:
            Bytes data
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._buffer.read(size)
    
    def read_text(self, encoding: str = 'utf-8', errors: str = 'strict') -> str:
        """Read the entire content as text.
        
        Args:
            encoding: Text encoding to use
            errors: How to handle encoding errors
            
        Returns:
            Text content
        """
        data = self.read()
        return data.decode(encoding, errors)
    
    def readline(self, size: int = -1) -> bytes:
        """Read and return one line as bytes.
        
        Args:
            size: Maximum number of bytes to read
            
        Returns:
            Line data as bytes
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._buffer.readline(size)
    
    def readlines(self, hint: int = -1) -> List[bytes]:
        """Read and return a list of lines.
        
        Args:
            hint: Hint for number of bytes to read
            
        Returns:
            List of line bytes
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._buffer.readlines(hint)
    
    def write(self, data: Union[bytes, str]) -> int:
        """Write data to the buffer.
        
        Args:
            data: Data to write (bytes or string)
            
        Returns:
            Number of bytes written
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        return self._buffer.write(data)
    
    def writelines(self, lines: List[Union[bytes, str]]) -> None:
        """Write a list of lines to the buffer.
        
        Args:
            lines: List of lines to write
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        for line in lines:
            self.write(line)
    
    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Change stream position.
        
        Args:
            offset: Stream position
            whence: How to interpret offset (SEEK_SET, SEEK_CUR, SEEK_END)
            
        Returns:
            New absolute position
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._buffer.seek(offset, whence)
    
    def tell(self) -> int:
        """Get current stream position.
        
        Returns:
            Current position
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._buffer.tell()
    
    def flush(self) -> None:
        """Flush write buffers (no-op for BytesIO)."""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        self._buffer.flush()
    
    def truncate(self, size: Optional[int] = None) -> int:
        """Truncate file to at most size bytes.
        
        Args:
            size: Size to truncate to. If None, use current position.
            
        Returns:
            New size
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._buffer.truncate(size)
    
    def close(self) -> None:
        """Close the file."""
        if not self._closed:
            self._buffer.close()
            self._closed = True
    
    def getvalue(self) -> bytes:
        """Get the entire contents as bytes.
        
        Returns:
            All data as bytes
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")
        current_pos = self._buffer.tell()
        self._buffer.seek(0)
        data = self._buffer.read()
        self._buffer.seek(current_pos)
        return data
    
    def save_to_file(self, filepath: str, chunk_size: int = 8192) -> None:
        """Save content to a file on disk.
        
        Args:
            filepath: Path to save the file
            chunk_size: Size of chunks to write
        """
        with open(filepath, 'wb') as f:
            self.seek(0)
            while True:
                chunk = self.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
    
    def load_from_file(self, filepath: str, chunk_size: int = 8192) -> None:
        """Load content from a file on disk.
        
        Args:
            filepath: Path to load from
            chunk_size: Size of chunks to read
        """
        self._buffer = io.BytesIO()
        self.filename = os.path.basename(filepath)
        
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                self._buffer.write(chunk)
        self._buffer.seek(0)
    
    def copy_to_stream(self, stream: BinaryIO, chunk_size: int = 8192) -> int:
        """Copy content to another stream.
        
        Args:
            stream: Target stream to copy to
            chunk_size: Size of chunks to copy
            
        Returns:
            Number of bytes copied
        """
        total_bytes = 0
        self.seek(0)
        while True:
            chunk = self.read(chunk_size)
            if not chunk:
                break
            stream.write(chunk)
            total_bytes += len(chunk)
        return total_bytes
    
    def copy_from_stream(self, stream: BinaryIO, chunk_size: int = 8192) -> int:
        """Copy content from another stream.
        
        Args:
            stream: Source stream to copy from
            chunk_size: Size of chunks to copy
            
        Returns:
            Number of bytes copied
        """
        self._buffer = io.BytesIO()
        total_bytes = 0
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            self._buffer.write(chunk)
            total_bytes += len(chunk)
        self._buffer.seek(0)
        return total_bytes
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __len__(self) -> int:
        """Get the size of the data."""
        return self.size
    
    def __bool__(self) -> bool:
        """Check if there's any data."""
        return self.size > 0
    
    def __repr__(self) -> str:
        """String representation."""
        status = "closed" if self._closed else "open"
        return f"BytesFieldWrapper(size={self.size}, filename='{self.filename}', {status})"


class BytesField(Field):
    """Enhanced Bytes field type with file-like interface.

    This field type stores binary data as byte arrays and provides validation,
    conversion between Python bytes objects and SurrealDB bytes format, plus
    a file-like interface for easy manipulation of binary data.
    
    Features:
    - Standard Python bytes validation and conversion
    - File-like interface with read(), write(), seek(), tell() operations
    - Context manager support for safe resource handling
    - File metadata support (filename, content_type, custom metadata)
    - Stream operations for large files
    - Direct file loading/saving capabilities
    
    Example:
        ```python
        class Document(SurrealDocument):
            file_data = BytesField(max_size=1024*1024)  # 1MB limit
            
        # Usage examples:
        doc = Document()
        
        # File-like operations
        with doc.file_data.open() as f:
            f.write(b"Hello, World!")
            f.seek(0)
            content = f.read()
        
        # Load from file
        doc.file_data.load_from_file("/path/to/image.jpg")
        print(f"Loaded {len(doc.file_data)} bytes")
        
        # Access file properties
        print(f"Filename: {doc.file_data.filename}")
        print(f"Size: {doc.file_data.size} bytes")
        
        # Save to file
        doc.file_data.save_to_file("/path/to/output.jpg")
        
        # Text operations (for text files)
        doc.file_data.write_text("Hello, World!")
        text_content = doc.file_data.read_text()
        ```
    """

    def __init__(self, max_size: Optional[int] = None, 
                 allowed_types: Optional[List[str]] = None, **kwargs: Any) -> None:
        """Initialize a new BytesField.

        Args:
            max_size: Maximum size in bytes (None for unlimited)
            allowed_types: List of allowed content types/extensions
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.py_type = bytes
        self.max_size = max_size
        self.allowed_types = allowed_types or []
        self._wrapper = None

    def validate(self, value: Any) -> Optional[bytes]:
        """Validate the bytes value.

        This method checks if the value is a valid bytes object or can be
        converted to bytes, and enforces size and type restrictions.

        Args:
            value: The value to validate

        Returns:
            The validated bytes value

        Raises:
            TypeError: If the value cannot be converted to bytes
            ValueError: If the value exceeds size limits or type restrictions
        """
        value = super().validate(value)
        if value is not None:
            # Handle BytesFieldWrapper
            if isinstance(value, BytesFieldWrapper):
                value = value.getvalue()
            
            if isinstance(value, bytes):
                # Check size limit
                if self.max_size and len(value) > self.max_size:
                    raise ValueError(
                        f"Data size {len(value)} bytes exceeds maximum {self.max_size} bytes "
                        f"for field '{self.name}'"
                    )
                return value
            
            if isinstance(value, str):
                try:
                    data = value.encode('utf-8')
                    if self.max_size and len(data) > self.max_size:
                        raise ValueError(
                            f"Data size {len(data)} bytes exceeds maximum {self.max_size} bytes "
                            f"for field '{self.name}'"
                        )
                    return data
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

        # Handle BytesFieldWrapper
        if isinstance(value, BytesFieldWrapper):
            value = value.getvalue()

        if isinstance(value, bytes):
            # Convert bytes to SurrealDB bytes format
            # SurrealDB uses <bytes>"base64_encoded_string" format
            encoded = base64.b64encode(value).decode('ascii')
            return f'<bytes>"{encoded}"'

        if isinstance(value, str) and value.startswith('<bytes>"') and value.endswith('"'):
            # If it's already in SurrealDB bytes format, return as is
            return value

        raise TypeError(f"Cannot convert {type(value)} to bytes")

    def from_db(self, value: Any) -> Optional[BytesFieldWrapper]:
        """Convert database value to Python BytesFieldWrapper.

        This method converts a SurrealDB bytes format from the database to a
        BytesFieldWrapper object with file-like capabilities.

        Args:
            value: The database value to convert

        Returns:
            The BytesFieldWrapper object
        """
        if value is not None:
            data = None
            
            if isinstance(value, bytes):
                data = value
            elif isinstance(value, str) and value.startswith('<bytes>"') and value.endswith('"'):
                # Extract the base64-encoded string from <bytes>"..." format
                encoded = value[8:-1]  # Remove <bytes>" and "
                data = base64.b64decode(encoded)
            
            if data is not None:
                return BytesFieldWrapper(data)
        
        return value

    def open(self, data: Optional[bytes] = None, **kwargs) -> BytesFieldWrapper:
        """Open a file-like interface for the bytes data.
        
        Args:
            data: Initial data (if None, uses empty bytes)
            **kwargs: Additional arguments for BytesFieldWrapper
            
        Returns:
            BytesFieldWrapper instance
        """
        return BytesFieldWrapper(data or b'', **kwargs)

    def load_from_file(self, filepath: str, **metadata) -> BytesFieldWrapper:
        """Load data from a file and return a BytesFieldWrapper.
        
        Args:
            filepath: Path to the file to load
            **metadata: Additional metadata for the wrapper
            
        Returns:
            BytesFieldWrapper with loaded data
        """
        # Extract specific metadata fields for constructor
        filename = metadata.get('filename')
        content_type = metadata.get('content_type')
        remaining_metadata = {k: v for k, v in metadata.items() if k not in ['filename', 'content_type']}
        
        wrapper = BytesFieldWrapper(
            filename=filename,
            content_type=content_type,
            metadata=remaining_metadata
        )
        wrapper.load_from_file(filepath)
        return wrapper

    def from_stream(self, stream: BinaryIO, **metadata) -> BytesFieldWrapper:
        """Create a BytesFieldWrapper from a stream.
        
        Args:
            stream: Source stream to read from
            **metadata: Additional metadata for the wrapper
            
        Returns:
            BytesFieldWrapper with stream data
        """
        # Extract specific metadata fields for constructor
        filename = metadata.get('filename')
        content_type = metadata.get('content_type')
        remaining_metadata = {k: v for k, v in metadata.items() if k not in ['filename', 'content_type']}
        
        wrapper = BytesFieldWrapper(
            filename=filename,
            content_type=content_type,
            metadata=remaining_metadata
        )
        wrapper.copy_from_stream(stream)
        return wrapper

    # Convenience methods for the field instance
    @property
    def size(self) -> int:
        """Get the current size of stored data."""
        if self._wrapper:
            return self._wrapper.size
        return 0

    @property
    def filename(self) -> Optional[str]:
        """Get the filename of stored data."""
        if self._wrapper:
            return self._wrapper.filename
        return None

    @property
    def content_type(self) -> Optional[str]:
        """Get the content type of stored data."""
        if self._wrapper:
            return self._wrapper.content_type
        return None

    def read(self, size: int = -1) -> bytes:
        """Read data from the field (convenience method)."""
        if self._wrapper:
            return self._wrapper.read(size)
        return b''

    def write(self, data: Union[bytes, str]) -> int:
        """Write data to the field (convenience method)."""
        if not self._wrapper:
            self._wrapper = BytesFieldWrapper()
        return self._wrapper.write(data)

    def write_text(self, text: str, encoding: str = 'utf-8') -> int:
        """Write text data to the field.
        
        Args:
            text: Text to write
            encoding: Text encoding to use
            
        Returns:
            Number of bytes written
        """
        return self.write(text.encode(encoding))

    def read_text(self, encoding: str = 'utf-8', errors: str = 'strict') -> str:
        """Read data as text.
        
        Args:
            encoding: Text encoding to use
            errors: How to handle encoding errors
            
        Returns:
            Text content
        """
        if self._wrapper:
            # Reset position to read all data
            current_pos = self._wrapper.tell()
            self._wrapper.seek(0)
            data = self._wrapper.read()
            self._wrapper.seek(current_pos)
            return data.decode(encoding, errors)
        return ""

    def save_to_file(self, filepath: str) -> None:
        """Save current data to a file."""
        if self._wrapper:
            self._wrapper.save_to_file(filepath)

    def __len__(self) -> int:
        """Get the size of stored data."""
        return self.size

    def __bool__(self) -> bool:
        """Check if there's any stored data."""
        return self.size > 0


class RegexField(Field):
    """Regular expression field type.

    This field type stores regular expressions and provides validation and
    conversion between Python regex objects and SurrealDB regex format.
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
            TypeError: If the value cannot be converted to a regex pattern
            ValueError: If the regex pattern is invalid
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, Pattern):
                return value
            if isinstance(value, str):
                try:
                    return re.compile(value)
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern for field '{self.name}': {str(e)}")
            raise TypeError(f"Expected regex pattern for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python regex to database representation.

        This method converts a Python regex pattern to a SurrealDB regex format
        for storage in the database.

        Args:
            value: The Python regex pattern to convert

        Returns:
            The SurrealDB regex format for the database
        """
        if value is None:
            return None

        if isinstance(value, Pattern):
            # Convert regex pattern to SurrealDB regex format
            # SurrealDB uses /pattern/flags format
            pattern = value.pattern
            flags = ""
            if value.flags & re.IGNORECASE:
                flags += "i"
            if value.flags & re.MULTILINE:
                flags += "m"
            if value.flags & re.DOTALL:
                flags += "s"
            return f"/{pattern}/{flags}"

        if isinstance(value, str):
            # If it's already a string, assume it's in the correct format
            return value

        raise TypeError(f"Cannot convert {type(value)} to regex")

    def from_db(self, value: Any) -> Optional[Pattern]:
        """Convert database value to Python regex.

        This method converts a SurrealDB regex format from the database to a
        Python regex pattern.

        Args:
            value: The database value to convert

        Returns:
            The Python regex pattern
        """
        if value is not None:
            if isinstance(value, Pattern):
                return value
            if isinstance(value, str) and value.startswith('/') and '/' in value[1:]:
                # Parse /pattern/flags format
                last_slash = value.rindex('/')
                pattern = value[1:last_slash]
                flags_str = value[last_slash + 1:]
                flags = 0
                if 'i' in flags_str:
                    flags |= re.IGNORECASE
                if 'm' in flags_str:
                    flags |= re.MULTILINE
                if 's' in flags_str:
                    flags |= re.DOTALL
                return re.compile(pattern, flags)
        return value


class DecimalField(NumberField):
    """Decimal field type.

    This field type stores decimal values with arbitrary precision using Python's
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
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except (TypeError, ValueError, decimal.InvalidOperation):
                raise TypeError(f"Expected decimal for field '{self.name}', got {type(value)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python decimal to database representation.

        This method converts a Python Decimal object to a string for storage in the database
        to preserve precision.

        Args:
            value: The Python Decimal to convert

        Returns:
            The string representation for the database
        """
        if value is not None:
            if isinstance(value, Decimal):
                return str(value)
            try:
                return str(Decimal(str(value)))
            except (TypeError, ValueError, decimal.InvalidOperation):
                pass
        return value

    def from_db(self, value: Any) -> Optional[Decimal]:
        """Convert database value to Python Decimal.

        This method converts a value from the database to a Python Decimal object.

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


class UUIDField(Field):
    """UUID field type.

    This field type stores UUID values and provides validation and
    conversion between Python UUID objects and SurrealDB string format.

    Example:
        ```python
        class User(Document):
            id = UUIDField(default=uuid.uuid4)
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
            ValueError: If the UUID format is invalid
        """
        value = super().validate(value)
        if value is not None:
            if isinstance(value, uuid.UUID):
                return value
            try:
                return uuid.UUID(str(value))
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid UUID format for field '{self.name}': {str(e)}")
        return value

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python UUID to database representation.

        This method converts a Python UUID object to a string for storage in the database.

        Args:
            value: The Python UUID to convert

        Returns:
            The string representation for the database
        """
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            try:
                return str(uuid.UUID(str(value)))
            except (TypeError, ValueError):
                pass
        return value

    def from_db(self, value: Any) -> Optional[uuid.UUID]:
        """Convert database value to Python UUID.

        This method converts a value from the database to a Python UUID object.

        Args:
            value: The database value to convert

        Returns:
            The Python UUID object
        """
        if value is not None:
            try:
                return uuid.UUID(str(value))
            except (TypeError, ValueError):
                pass
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
                error_msg += f" or a valid {field_types}"
        else:
            field_types = ", ".join(f.__class__.__name__ for f in self.allowed_fields)
            error_msg = f"Value for field '{self.name}' must be a valid {field_types}"

        raise ValidationError(error_msg)

    def to_db(self, value: Any) -> Any:
        """Convert Python value to database representation.

        This method converts a Python value to a database representation by
        using the appropriate field type if the value is not a literal.

        Args:
            value: The Python value to convert

        Returns:
            The database representation of the value
        """
        if value is None:
            return None

        # If it's a literal, return as is
        if value in self.allowed_literals:
            return value

        # Try to convert with each allowed field type
        for field in self.allowed_fields:
            try:
                field.validate(value)  # Validate first to ensure it's the right type
                return field.to_db(value)
            except (TypeError, ValueError):
                continue

        return value

    def from_db(self, value: Any) -> Any:
        """Convert database value to Python representation.

        This method converts a database value to a Python representation by
        using the appropriate field type if the value is not a literal.

        Args:
            value: The database value to convert

        Returns:
            The Python representation of the value
        """
        if value is None:
            return None

        # If it's a literal, return as is
        if value in self.allowed_literals:
            return value

        # Try to convert with each allowed field type
        for field in self.allowed_fields:
            try:
                return field.from_db(value)
            except (TypeError, ValueError):
                continue

        return value


class EmailField(StringField):
    """Email field type.

    This field type stores email addresses and provides validation to ensure
    the value is a valid email address.

    Example:
        ```python
        class User(Document):
            email = EmailField(required=True)
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new EmailField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        # Add a more comprehensive regex pattern to validate email addresses
        # This pattern allows more valid email characters and formats
        kwargs['regex'] = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate the email address.

        This method checks if the value is a valid email address.

        Args:
            value: The value to validate

        Returns:
            The validated email address

        Raises:
            ValueError: If the email address is invalid
        """
        value = super().validate(value)
        if value is not None:
            # Additional validation specific to email addresses
            if '@' not in value:
                raise ValueError(f"Invalid email address for field '{self.name}': missing @ symbol")
            if value.count('@') > 1:
                raise ValueError(f"Invalid email address for field '{self.name}': multiple @ symbols")
            local, domain = value.split('@')
            if not local:
                raise ValueError(f"Invalid email address for field '{self.name}': empty local part")
            if not domain:
                raise ValueError(f"Invalid email address for field '{self.name}': empty domain part")
            if '.' not in domain:
                raise ValueError(f"Invalid email address for field '{self.name}': invalid domain")
        return value


class URLField(StringField):
    """Enhanced URL field type with urllib integration.

    This field type stores URLs and provides validation using urllib.parse.
    It also provides convenient access to URL components and allows flexible
    URL formats including host-only URLs.

    Features:
    - Access URL components via properties (.scheme, .host, .path, .query, etc.)
    - Allow host-only URLs (automatically adds scheme)
    - Robust URL validation using urllib.parse
    - Flexible scheme handling (http/https/ftp/etc.)

    Example:
        ```python
        class Website(Document):
            url = URLField(default_scheme='https', allow_host_only=True)

        # Usage examples:
        site = Website()
        site.url = "example.com"  # Auto-converts to "https://example.com"
        print(site.url.host)      # "example.com"
        print(site.url.scheme)    # "https"
        print(site.url.port)      # None
        
        site.url = "https://api.example.com:8080/v1/users?active=true"
        print(site.url.host)      # "api.example.com"
        print(site.url.port)      # 8080
        print(site.url.path)      # "/v1/users"
        print(site.url.query)     # "active=true"
        ```
    """

    def __init__(self, 
                 default_scheme: str = 'https',
                 allow_host_only: bool = True,
                 allowed_schemes: Optional[List[str]] = None,
                 **kwargs: Any) -> None:
        """Initialize a new enhanced URLField.

        Args:
            default_scheme: Default scheme to use for host-only URLs
            allow_host_only: Whether to allow host-only URLs (will add default_scheme)
            allowed_schemes: List of allowed schemes (None = allow all)
            **kwargs: Additional arguments to pass to the parent class
        """
        self.default_scheme = default_scheme
        self.allow_host_only = allow_host_only
        self.allowed_schemes = allowed_schemes or ['http', 'https', 'ftp', 'ftps']
        
        # Remove the basic regex validation from parent
        if 'regex' in kwargs:
            del kwargs['regex']
        
        super().__init__(**kwargs)
        self._parsed_url = None

    def validate(self, value: Any) -> Optional[str]:
        """Validate and normalize the URL.

        This method uses urllib.parse for robust URL validation and
        automatically adds schemes to host-only URLs if allowed.

        Args:
            value: The value to validate

        Returns:
            The validated and normalized URL

        Raises:
            ValueError: If the URL is invalid
        """
        # First run parent validation (handles None, basic string checks)
        value = super(StringField, self).validate(value)  # Skip StringField's regex
        
        if value is not None:
            original_value = value
            
            # Handle host-only URLs
            if self.allow_host_only and '://' not in value:
                # Check if it looks like a valid hostname/domain
                if self._is_valid_hostname(value):
                    value = f"{self.default_scheme}://{value}"
                else:
                    raise ValueError(f"Invalid hostname for field '{self.name}': {original_value}")
            
            # Parse and validate the URL
            try:
                parsed = urllib.parse.urlparse(value)
                self._parsed_url = parsed
                
                # Validate scheme
                if parsed.scheme not in self.allowed_schemes:
                    allowed_str = ', '.join(self.allowed_schemes)
                    raise ValueError(f"Invalid URL scheme for field '{self.name}': '{parsed.scheme}'. Allowed: {allowed_str}")
                
                # Validate that we have at least a netloc (host)
                if not parsed.netloc:
                    raise ValueError(f"Invalid URL for field '{self.name}': missing host")
                
                # Reconstruct the URL to ensure it's properly formatted
                return urllib.parse.urlunparse(parsed)
                
            except Exception as e:
                raise ValueError(f"Invalid URL for field '{self.name}': {str(e)}")
        
        return value

    def _is_valid_hostname(self, hostname: str) -> bool:
        """Check if a string is a valid hostname/domain.
        
        Args:
            hostname: The hostname to validate
            
        Returns:
            True if valid hostname, False otherwise
        """
        # Basic hostname validation
        hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        # Allow localhost and IP addresses
        if hostname in ['localhost', '127.0.0.1'] or hostname.startswith('192.168.') or hostname.startswith('10.'):
            return True
            
        return bool(re.match(hostname_pattern, hostname)) and len(hostname) <= 253

    # URL Component Properties
    @property
    def scheme(self) -> Optional[str]:
        """Get the URL scheme (protocol)."""
        if self._parsed_url:
            return self._parsed_url.scheme
        return None

    @property
    def host(self) -> Optional[str]:
        """Get the URL host/domain."""
        if self._parsed_url:
            return self._parsed_url.hostname
        return None

    @property
    def hostname(self) -> Optional[str]:
        """Alias for host property."""
        return self.host

    @property
    def port(self) -> Optional[int]:
        """Get the URL port."""
        if self._parsed_url:
            return self._parsed_url.port
        return None

    @property
    def path(self) -> str:
        """Get the URL path."""
        if self._parsed_url:
            return self._parsed_url.path
        return ""

    @property
    def query(self) -> str:
        """Get the URL query string."""
        if self._parsed_url:
            return self._parsed_url.query
        return ""

    @property
    def fragment(self) -> str:
        """Get the URL fragment (hash)."""
        if self._parsed_url:
            return self._parsed_url.fragment
        return ""

    @property
    def netloc(self) -> str:
        """Get the network location (host:port)."""
        if self._parsed_url:
            return self._parsed_url.netloc
        return ""

    @property
    def params(self) -> str:
        """Get the URL parameters."""
        if self._parsed_url:
            return self._parsed_url.params
        return ""

    def get_query_params(self) -> Dict[str, str]:
        """Parse query string into a dictionary.
        
        Returns:
            Dictionary of query parameters
        """
        if self._parsed_url and self._parsed_url.query:
            return dict(urllib.parse.parse_qsl(self._parsed_url.query))
        return {}

    def get_query_param(self, param_name: str, default: Any = None) -> Any:
        """Get a specific query parameter value.
        
        Args:
            param_name: Name of the parameter to get
            default: Default value if parameter not found
            
        Returns:
            Parameter value or default
        """
        params = self.get_query_params()
        return params.get(param_name, default)

    def is_secure(self) -> bool:
        """Check if the URL uses a secure scheme (https/ftps)."""
        if self._parsed_url:
            return self._parsed_url.scheme in ['https', 'ftps']
        return False

    def get_base_url(self) -> str:
        """Get the base URL (scheme + netloc).
        
        Returns:
            Base URL string
        """
        if self._parsed_url:
            return f"{self._parsed_url.scheme}://{self._parsed_url.netloc}"
        return ""

    def to_db(self, value: Any) -> Optional[str]:
        """Convert Python URL to database representation.

        Args:
            value: The Python URL to convert

        Returns:
            The string representation for the database
        """
        # The validated value is already a proper URL string
        return value

    def from_db(self, value: Any) -> Optional[str]:
        """Convert database value to Python URL.

        Args:
            value: The database value to convert

        Returns:
            The Python URL string with parsed components available
        """
        if value is not None:
            # Re-validate and parse the URL from database
            try:
                return self.validate(value)
            except ValueError:
                pass
        return value

    def __str__(self) -> str:
        """String representation of the URL."""
        if self._parsed_url:
            return urllib.parse.urlunparse(self._parsed_url)
        return super().__str__()

    def __repr__(self) -> str:
        """Detailed representation of the URL."""
        return f"URLField('{self.__str__()}')"


class IPAddressField(StringField):
    """IP address field type.

    This field type stores IP addresses and provides validation to ensure
    the value is a valid IPv4 or IPv6 address.

    Example:
        ```python
        class Server(Document):
            ip_address = IPAddressField(required=True)
            ip_v4 = IPAddressField(ipv4_only=True)
            ip_v6 = IPAddressField(ipv6_only=True)
        ```
    """

    def __init__(self, ipv4_only: bool = False, ipv6_only: bool = False, version: str = None, **kwargs: Any) -> None:
        """Initialize a new IPAddressField.

        Args:
            ipv4_only: Whether to only allow IPv4 addresses
            ipv6_only: Whether to only allow IPv6 addresses
            version: IP version to validate ('ipv4', 'ipv6', or 'both')
            **kwargs: Additional arguments to pass to the parent class
        """
        # Handle version parameter for backward compatibility
        if version is not None:
            version = version.lower()
            if version not in ('ipv4', 'ipv6', 'both'):
                raise ValueError("version must be 'ipv4', 'ipv6', or 'both'")
            ipv4_only = (version == 'ipv4')
            ipv6_only = (version == 'ipv6')

        self.ipv4_only = ipv4_only
        self.ipv6_only = ipv6_only
        if ipv4_only and ipv6_only:
            raise ValueError("Cannot set both ipv4_only and ipv6_only to True")

        # Remove version from kwargs to avoid passing it to the parent class
        # This prevents it from being included in the schema definition
        if 'version' in kwargs:
            del kwargs['version']

        super().__init__(**kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate the IP address.

        This method checks if the value is a valid IP address.

        Args:
            value: The value to validate

        Returns:
            The validated IP address

        Raises:
            ValueError: If the IP address is invalid
        """
        value = super().validate(value)
        if value is not None:
            # Validate IPv4 address
            if self.ipv4_only or not self.ipv6_only:
                ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                if re.match(ipv4_pattern, value):
                    # Check that each octet is in the valid range
                    octets = value.split('.')
                    try:
                        if all(0 <= int(octet) <= 255 for octet in octets):
                            return value
                        if self.ipv4_only:
                            raise ValueError(f"Invalid IPv4 address for field '{self.name}': octets must be between 0 and 255")
                    except ValueError:
                        if self.ipv4_only:
                            raise ValueError(f"Invalid IPv4 address for field '{self.name}': octets must be numeric")

            # Validate IPv6 address
            if self.ipv6_only or not self.ipv4_only:
                try:
                    # Use socket.inet_pton to validate IPv6 address
                    socket.inet_pton(socket.AF_INET6, value)
                    return value
                except (socket.error, ValueError):
                    if self.ipv6_only:
                        raise ValueError(f"Invalid IPv6 address for field '{self.name}'")

            # If we get here, the value is not a valid IP address
            if self.ipv4_only:
                raise ValueError(f"Invalid IPv4 address for field '{self.name}'")
            elif self.ipv6_only:
                raise ValueError(f"Invalid IPv6 address for field '{self.name}'")
            else:
                raise ValueError(f"Invalid IP address for field '{self.name}'")
        return value


class SlugField(StringField):
    """Slug field type.

    This field type stores slugs (URL-friendly strings) and provides validation
    to ensure the value is a valid slug.

    Example:
        ```python
        class Article(Document):
            slug = SlugField(required=True)
        ```
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a new SlugField.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        # Add a regex pattern to validate slugs
        kwargs['regex'] = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        super().__init__(**kwargs)

    def validate(self, value: Any) -> Optional[str]:
        """Validate the slug.

        This method checks if the value is a valid slug.

        Args:
            value: The value to validate

        Returns:
            The validated slug

        Raises:
            ValueError: If the slug is invalid
        """
        value = super().validate(value)
        if value is not None:
            # Additional validation specific to slugs
            if not value:
                raise ValueError(f"Slug for field '{self.name}' cannot be empty")
            if value.startswith('-') or value.endswith('-'):
                raise ValueError(f"Slug for field '{self.name}' cannot start or end with a hyphen")
            if '--' in value:
                raise ValueError(f"Slug for field '{self.name}' cannot contain consecutive hyphens")
        return value


class ChoiceField(Field):
    """Choice field type.

    This field type stores values from a predefined set of choices and provides
    validation to ensure the value is one of the allowed choices.

    Example:
        ```python
        class Product(Document):
            status = ChoiceField(choices=['active', 'inactive', 'discontinued'])
        ```
    """

    def __init__(self, choices: List[Union[str, tuple]], **kwargs: Any) -> None:
        """Initialize a new ChoiceField.

        Args:
            choices: List of allowed choices. Each choice can be a string or a tuple
                    of (value, display_name).
            **kwargs: Additional arguments to pass to the parent class
        """
        self.choices = choices
        self.values = [c[0] if isinstance(c, tuple) else c for c in choices]
        super().__init__(**kwargs)
        self.py_type = str

    def validate(self, value: Any) -> Optional[str]:
        """Validate the choice value.

        This method checks if the value is one of the allowed choices.

        Args:
            value: The value to validate

        Returns:
            The validated choice value

        Raises:
            ValueError: If the value is not one of the allowed choices
        """
        value = super().validate(value)
        if value is not None and value not in self.values:
            choices_str = ", ".join(repr(v) for v in self.values)
            raise ValueError(f"Value for field '{self.name}' must be one of: {choices_str}")
        return value
