"""Utilities for handling SurrealDB RecordID formats.

This module provides comprehensive support for different RecordID formats
including string, URL-encoded, and complex ID types.
"""
import re
import urllib.parse
from typing import Any, Union, Optional, Tuple
from surrealdb import RecordID


class RecordIdUtils:
    """Utilities for working with SurrealDB RecordIDs in various formats."""
    
    # Regex pattern for valid RecordID format: table:id
    RECORD_ID_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*:[^:]+$')
    
    # Common URL-encoded characters in RecordIDs
    URL_ENCODED_MAPPINGS = {
        '%3A': ':',  # colon
        '%2F': '/',  # forward slash
        '%2B': '+',  # plus
        '%20': ' ',  # space
        '%22': '"',  # double quote
        '%27': "'",  # single quote
        '%5B': '[',  # left bracket
        '%5D': ']',  # right bracket
        '%7B': '{',  # left brace
        '%7D': '}',  # right brace
    }
    
    @classmethod
    def normalize_record_id(cls, record_id: Any, table_name: Optional[str] = None) -> Optional[str]:
        """Normalize a RecordID to standard string format.
        
        This method handles various RecordID formats:
        - RecordID objects from surrealdb
        - String format: "table:id"
        - URL-encoded format: "table%3Aid"
        - Short ID format: "id" (requires table_name)
        - Complex ID formats with special characters
        
        Args:
            record_id: The record ID in any supported format
            table_name: Optional table name for short ID format
            
        Returns:
            Normalized RecordID string in "table:id" format, or None if invalid
            
        Examples:
            >>> RecordIdUtils.normalize_record_id("user:123")
            "user:123"
            
            >>> RecordIdUtils.normalize_record_id("user%3A123")
            "user:123"
            
            >>> RecordIdUtils.normalize_record_id("123", "user")
            "user:123"
            
            >>> RecordIdUtils.normalize_record_id("user:⟨complex-id⟩")
            "user:⟨complex-id⟩"
        """
        if record_id is None:
            return None
            
        # Handle RecordID objects
        if isinstance(record_id, RecordID):
            return str(record_id)
            
        # Convert to string
        if not isinstance(record_id, str):
            record_id = str(record_id)
            
        # Handle URL-encoded RecordIDs
        if '%' in record_id:
            record_id = cls.url_decode_record_id(record_id)
            
        # Handle short ID format (just the ID part)
        if ':' not in record_id and table_name:
            return f"{table_name}:{record_id}"
            
        # Validate full RecordID format
        if cls.is_valid_record_id(record_id):
            return record_id
            
        # If it looks like a partial ID, try to fix it
        if table_name and not record_id.startswith(f"{table_name}:"):
            return f"{table_name}:{record_id}"
            
        return record_id  # Return as-is if we can't normalize it
    
    @classmethod
    def url_decode_record_id(cls, encoded_id: str) -> str:
        """Decode a URL-encoded RecordID.
        
        Args:
            encoded_id: URL-encoded RecordID string
            
        Returns:
            Decoded RecordID string
            
        Examples:
            >>> RecordIdUtils.url_decode_record_id("user%3A123")
            "user:123"
            
            >>> RecordIdUtils.url_decode_record_id("user%3A%7Bcomplex%7D")
            "user:{complex}"
        """
        try:
            # Use urllib.parse.unquote for comprehensive URL decoding
            return urllib.parse.unquote(encoded_id)
        except Exception:
            # Fall back to manual replacement if urllib fails
            decoded = encoded_id
            for encoded, decoded_char in cls.URL_ENCODED_MAPPINGS.items():
                decoded = decoded.replace(encoded, decoded_char)
            return decoded
    
    @classmethod
    def url_encode_record_id(cls, record_id: str) -> str:
        """URL-encode a RecordID for safe transmission.
        
        Args:
            record_id: RecordID string to encode
            
        Returns:
            URL-encoded RecordID string
            
        Examples:
            >>> RecordIdUtils.url_encode_record_id("user:123")
            "user%3A123"
            
            >>> RecordIdUtils.url_encode_record_id("user:{complex}")
            "user%3A%7Bcomplex%7D"
        """
        return urllib.parse.quote(record_id, safe='')
    
    @classmethod
    def is_valid_record_id(cls, record_id: str) -> bool:
        """Check if a string is a valid RecordID format.
        
        Args:
            record_id: String to validate
            
        Returns:
            True if valid RecordID format, False otherwise
            
        Notes / caveats:
        - Reject URL-like strings (those containing '://').
        - Reject cases where the id part starts with '/' (e.g., 'http:/path').
        - Disallow any whitespace in the token.
        - Be conservative: require exactly one ':' and a valid table identifier.
        """
        if not isinstance(record_id, str) or not record_id:
            return False
        # Fast rejects
        if '://' in record_id:
            return False
        if any(ch.isspace() for ch in record_id):
            return False
        # Must contain exactly one colon
        if record_id.count(':') != 1:
            return False
        table, id_part = record_id.split(':', 1)
        # Table name must be a valid identifier
        if not table or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            return False
        # ID part must exist and must not begin with '/'
        if not id_part or id_part.startswith('/'):
            return False
        return True
    
    @classmethod
    def extract_table_and_id(cls, record_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract table name and ID from a RecordID.
        
        Args:
            record_id: RecordID string to parse
            
        Returns:
            Tuple of (table_name, id) or (None, None) if invalid
            
        Examples:
            >>> RecordIdUtils.extract_table_and_id("user:123")
            ("user", "123")
            
            >>> RecordIdUtils.extract_table_and_id("user%3A123")
            ("user", "123")
            
            >>> RecordIdUtils.extract_table_and_id("invalid")
            (None, None)
        """
        normalized = cls.normalize_record_id(record_id)
        if not normalized or not cls.is_valid_record_id(normalized):
            return None, None
            
        return normalized.split(':', 1)
    
    @classmethod
    def build_record_id(cls, table: str, id_value: Any) -> str:
        """Build a RecordID from table name and ID value.
        
        Args:
            table: Table name
            id_value: ID value (any type that can be converted to string)
            
        Returns:
            RecordID string in "table:id" format
            
        Examples:
            >>> RecordIdUtils.build_record_id("user", 123)
            "user:123"
            
            >>> RecordIdUtils.build_record_id("user", "complex-id")
            "user:complex-id"
        """
        if not table:
            raise ValueError("Table name cannot be empty")
            
        return f"{table}:{id_value}"
    
    @classmethod
    def is_short_id(cls, value: str) -> bool:
        """Check if a value is a short ID (no table prefix).
        
        Args:
            value: String to check
            
        Returns:
            True if it's a short ID, False if it's a full RecordID
            
        Examples:
            >>> RecordIdUtils.is_short_id("123")
            True
            
            >>> RecordIdUtils.is_short_id("user:123")
            False
        """
        return isinstance(value, str) and ':' not in value and value
    
    @classmethod
    def format_for_query(cls, record_id: str, quote: bool = False) -> str:
        """Format a RecordID for use in SurrealQL queries.
        
        Args:
            record_id: RecordID to format
            quote: Whether to add quotes around the RecordID
            
        Returns:
            Formatted RecordID for query use
            
        Examples:
            >>> RecordIdUtils.format_for_query("user:123")
            "user:123"
            
            >>> RecordIdUtils.format_for_query("user:complex-id", quote=True)
            "'user:complex-id'"
        """
        normalized = cls.normalize_record_id(record_id)
        if not normalized:
            return str(record_id)
            
        if quote:
            return f"'{normalized}'"
        return normalized
    
    @classmethod
    def batch_normalize(cls, record_ids: list, table_name: Optional[str] = None) -> list:
        """Normalize a batch of RecordIDs.
        
        Args:
            record_ids: List of RecordIDs in various formats
            table_name: Optional table name for short ID formats
            
        Returns:
            List of normalized RecordID strings (only valid ones)
            
        Examples:
            >>> RecordIdUtils.batch_normalize(["123", "user:456", "user%3A789"], "user")
            ["user:123", "user:456", "user:789"]
        """
        result = []
        for rid in record_ids:
            normalized = cls.normalize_record_id(rid, table_name)
            # Only include if normalized AND valid
            if normalized is not None and cls.is_valid_record_id(normalized):
                result.append(normalized)
        return result
    
    @classmethod
    def validate_and_normalize(cls, record_id: Any, table_name: Optional[str] = None, 
                             strict: bool = False) -> str:
        """Validate and normalize a RecordID with error handling.
        
        Args:
            record_id: RecordID to validate and normalize
            table_name: Optional table name for short IDs
            strict: If True, raise exceptions for invalid IDs
            
        Returns:
            Normalized RecordID string
            
        Raises:
            ValueError: If strict=True and RecordID is invalid
            
        Examples:
            >>> RecordIdUtils.validate_and_normalize("user:123")
            "user:123"
            
            >>> RecordIdUtils.validate_and_normalize("123", "user")
            "user:123"
            
            >>> RecordIdUtils.validate_and_normalize("invalid", strict=True)
            ValueError: Invalid RecordID format: invalid
        """
        normalized = cls.normalize_record_id(record_id, table_name)
        
        if normalized is None:
            if strict:
                raise ValueError(f"Invalid RecordID format: {record_id}")
            return str(record_id)
            
        if strict and not cls.is_valid_record_id(normalized):
            raise ValueError(f"Invalid RecordID format: {normalized}")
            
        return normalized