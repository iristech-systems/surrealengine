"""
Context management for SurrealEngine connections.

This module provides utilities for managing active database connections
using ContextVars, allowing for "polyglot" code execution where the
same code can run in Sync or Async modes depending on the context.
"""
from contextvars import ContextVar, Token
from typing import Any, Optional, Iterator
from contextlib import contextmanager

from .connection import ConnectionRegistry

# The ContextVar that holds the currently active connection
_current_connection: ContextVar[Optional[Any]] = ContextVar("current_connection", default=None)


def get_active_connection(async_mode: bool = True) -> Any:
    """Get the currently active connection.

    Precedence:
    1. Connection implicitly set by `using_connection` context manager.
    2. Default global connection from Registry.

    Args:
        async_mode: Preferred mode if falling back to default (default: True).

    Returns:
        The active connection object.
    """
    # 1. Check ContextVar
    conn = _current_connection.get()
    if conn is not None:
        return conn

    # 2. Fallback to Registry
    return ConnectionRegistry.get_default_connection(async_mode=async_mode)


@contextmanager
def using_connection(connection: Any) -> Iterator[None]:
    """Context manager to set the active connection for a block of code.

    Args:
        connection: The connection to use within the block.

    Example:
        >>> with using_connection(sync_conn):
        ...     User.objects.all()  # Uses sync_conn
    """
    token: Token = _current_connection.set(connection)
    try:
        yield
    finally:
        _current_connection.reset(token)

# Helpers for connection classes to manage context
def set_active_context_connection(connection: Any) -> Token:
    """Set the active connection in the context variable.
    
    Internal use for connection classes.
    """
    return _current_connection.set(connection)

def reset_active_context_connection(token: Token) -> None:
    """Reset the active connection in the context variable.
    
    Internal use for connection classes.
    """
    _current_connection.reset(token)
