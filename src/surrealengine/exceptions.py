"""
Exceptions for SurrealEngine.

This module contains custom exceptions used throughout the SurrealEngine package.
"""

from typing import Dict, Optional, Any


class SurrealEngineError(Exception):
    """Base exception class for SurrealEngine.

    All other exceptions in the package inherit from this class.
    """
    pass


class ConnectionError(SurrealEngineError):
    """Raised when a connection to the database cannot be established.

    This exception is raised when there is an issue connecting to the SurrealDB server,
    such as network errors, authentication failures, or server unavailability.
    """
    pass


class ValidationError(SurrealEngineError):
    """Raised when document validation fails.

    This exception is raised when a document fails validation, such as when
    a required field is missing or a field value is of the wrong type.

    Attributes:
        errors: Dictionary of validation errors by field
        field_name: Name of the field that failed validation, if applicable
    """

    def __init__(self, message: str, errors: Optional[Dict[str, Any]] = None, field_name: Optional[str] = None) -> None:
        """Initialize a ValidationError.

        Args:
            message: The error message
            errors: Dictionary of validation errors by field
            field_name: Name of the field that failed validation, if applicable
        """
        super().__init__(message)
        self.errors: Dict[str, Any] = errors or {}
        self.field_name: Optional[str] = field_name


class DoesNotExist(SurrealEngineError):
    """Raised when a document does not exist in the database.

    This exception is raised when attempting to retrieve a document that
    does not exist in the database, such as when using the get() method
    with a query that matches no documents.
    """
    pass


class MultipleObjectsReturned(SurrealEngineError):
    """Raised when multiple documents are returned when only one was expected.

    This exception is raised when a query that is expected to return a single
    document returns multiple documents, such as when using the get() method
    with a query that matches multiple documents.
    """
    pass


class OperationError(SurrealEngineError):
    """Raised when a database operation fails.

    This exception is raised when a database operation fails, such as when
    attempting to create a document with an invalid schema or when a query
    fails due to a syntax error.
    """
    pass


class InvalidQueryError(SurrealEngineError):
    """Raised when a query is invalid.

    This exception is raised when a query is invalid, such as when using
    an unsupported operator or when a query is malformed.
    """
    pass
