"""
Exceptions for SurrealEngine.
"""


class SurrealEngineError(Exception):
    """Base exception class for SurrealEngine."""
    pass


class ConnectionError(SurrealEngineError):
    """Raised when a connection to the database cannot be established."""
    pass


class ValidationError(SurrealEngineError):
    """Raised when document validation fails."""

    def __init__(self, message, errors=None, field_name=None):
        super().__init__(message)
        self.errors = errors or {}
        self.field_name = field_name


class DoesNotExist(SurrealEngineError):
    """Raised when a document does not exist in the database."""
    pass


class MultipleObjectsReturned(SurrealEngineError):
    """Raised when multiple documents are returned when only one was expected."""
    pass


class OperationError(SurrealEngineError):
    """Raised when a database operation fails."""
    pass


class InvalidQueryError(SurrealEngineError):
    """Raised when a query is invalid."""
    pass
