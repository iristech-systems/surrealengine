"""Context management for SurrealEngine connections.

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
_current_sync_manager: ContextVar[Optional[Any]] = ContextVar(
    "current_sync_manager", default=None
)


def get_active_connection(async_mode: Optional[bool] = True) -> Any:
    """Get the currently active connection.

    Precedence:
    1. Connection implicitly set by `using_connection` context manager.
    2. Default global connection from Registry.

    Args:
        async_mode: Preferred mode. 
                    If True: default async. 
                    If False: default sync.
                    If None: try async, fallback to sync.

    Returns:
        The active connection object.

    """
    # 1. Check ContextVar
    conn = _current_connection.get()
    if conn is not None:
        return conn

    # 2. Fallback to Registry
    if async_mode is None:
        # Check if we are in an async loop - if so, prefer async connection
        import asyncio
        try:
            asyncio.get_running_loop()
            in_async_loop = True
        except RuntimeError:
            in_async_loop = False
            
        if in_async_loop:
            try:
                return ConnectionRegistry.get_default_connection(async_mode=True)
            except RuntimeError:
                # Fallback to sync if no async default
                pass

        # Try sync first if not in async loop, or as fallback from async
        try:
            return ConnectionRegistry.get_default_connection(async_mode=False)
        except RuntimeError:
            # Last resort: try async if sync not available
            return ConnectionRegistry.get_default_connection(async_mode=True)
            
    return ConnectionRegistry.get_default_connection(async_mode=async_mode)


def get_active_sync_manager() -> Optional[Any]:
    """Get the currently active SyncManager.

    Precedence:
    1. SyncManager set via `using_sync_manager` context manager.
    2. Default global SyncManager from `ConnectionRegistry`.
    """
    mgr = _current_sync_manager.get()
    if mgr is not None:
        return mgr
    return ConnectionRegistry.get_default_sync_manager()


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


@contextmanager
def using_sync_manager(sync_manager: Any) -> Iterator[None]:
    """Context manager to set active SyncManager for a block of code."""
    token: Token = _current_sync_manager.set(sync_manager)
    try:
        yield
    finally:
        _current_sync_manager.reset(token)

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


def set_active_context_sync_manager(sync_manager: Any) -> Token:
    """Set active SyncManager in context variable (internal helper)."""
    return _current_sync_manager.set(sync_manager)


def reset_active_context_sync_manager(token: Token) -> None:
    """Reset active SyncManager context variable (internal helper)."""
    _current_sync_manager.reset(token)
