import logging
import json
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from .connection import (
    ConnectionRegistry, 
    SurrealEngineAsyncConnection,
    SurrealEngineSyncConnection,
    _current_transaction_connection,
)
from .surrealql import escape_literal

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Callable[..., Any])


class AsyncTransactionClientProxy:
    """
    A Write-Behind Proxy for the async SurrealDB client.
    
    Instead of executing mutations immediately over the network (which SurrealDB 
    processes statelessly, breaking transaction atomicity), this proxy intercepts
    mutation methods and buffers them as raw SurrealQL strings.
    
    Upon manual or context-manager exit, the buffer can be compiled and dispatched
    as a single `BEGIN; ... COMMIT;` string payload.
    """
    def __init__(self, original_client):
        self._original = original_client
        self.queries: List[str] = []
        
        # We don't buffer reads, we just pass them through because they don't break ACID.
        # But we DO need to warn the user if they try to read uncommitted data using this proxy!
        
    def __getattr__(self, name):
        """Pass through unrelated attributes to the original client."""
        return getattr(self._original, name)
        
    def _buffer(self, query: str):
        self.queries.append(query)
        
    def compile(self) -> str:
        """Compile the buffered mutations into a single transaction string."""
        if not self.queries:
            return ""
            
        statements = "\n".join(self.queries)
        return f"BEGIN TRANSACTION;\n{statements}\nCOMMIT TRANSACTION;"
        
    async def query(self, sql: str, vars: Optional[Dict] = None) -> Any:
        """
        Intercept generic queries. If it's a mutation, buffer it. 
        If it's a SELECT, pass it through BUT emit a warning that it won't see uncommitted data.
        """
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT") or sql_upper.startswith("INFO"):
             # Pass through reads to the real database
             return await self._original.query(sql, vars)
             
        # Buffer mutations natively
        if vars:
            # Very basic variable substitution for buffered queries (complex bindings aren't trivial here yet)
            # In a full ORM, we'd rely on the already-constructed SQL strings from schemaless/query.
            for k, v in vars.items():
                val_str = escape_literal(v)
                sql = sql.replace(f"${k}", val_str)
                
        # Ensure it ends with a semicolon for batching
        if not sql.strip().endswith(";"):
            sql = f"{sql};"
            
        self._buffer(sql)
        # Mock a successful execution result structure so the ORM doesn't crash anticipating an ID list
        return [{"result": [], "status": "OK", "time": "0ms"}]
        
    async def create(self, table: str, data: Any) -> Any:
        """Intercept record creation."""
        data_str = escape_literal(data)
        query = f"CREATE {table} CONTENT {data_str};"
        self._buffer(query)
        # Return a mocked dictionary with the ID if possible, otherwise empty dict so it unwraps safely
        mock_id = data.get('id') if isinstance(data, dict) else None
        return [{"result": [{"id": mock_id}] if mock_id else [{"id": f"{table}:pending"}], "status": "OK", "time": "0ms"}]
        
    async def insert(self, table: str, data: Any) -> Any:
        """Intercept record insertions."""
        data_str = escape_literal(data)
        query = f"INSERT INTO {table} {data_str};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]

    async def merge(self, table: str, data: Any) -> Any:
        """Intercept record merges (updates)."""
        data_str = escape_literal(data)
        query = f"UPDATE {table} MERGE {data_str};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]
        
    async def update(self, table: str, data: Any) -> Any:
        """Intercept full record updates."""
        data_str = escape_literal(data)
        query = f"UPDATE {table} CONTENT {data_str};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]
        
    async def delete(self, table: str) -> Any:
        """Intercept record deletions."""
        query = f"DELETE {table};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]


class TransactionSyncClientProxy:
    """Synchronous version of the Write-Behind proxy."""
    def __init__(self, original_client):
        self._original = original_client
        self.queries: List[str] = []
        
    def __getattr__(self, name):
        return getattr(self._original, name)
        
    def _buffer(self, query: str):
        self.queries.append(query)
        
    def compile(self) -> str:
        if not self.queries:
            return ""
        statements = "\n".join(self.queries)
        return f"BEGIN TRANSACTION;\n{statements}\nCOMMIT TRANSACTION;"
        
    def query(self, sql: str, vars: Optional[Dict] = None) -> Any:
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT") or sql_upper.startswith("INFO"):
             return self._original.query(sql, vars)
             
        if vars:
            for k, v in vars.items():
                val_str = escape_literal(v)
                sql = sql.replace(f"${k}", val_str)
                
        if not sql.strip().endswith(";"):
            sql = f"{sql};"
            
        self._buffer(sql)
        return [{"result": [], "status": "OK", "time": "0ms"}]
        
    def create(self, table: str, data: Any) -> Any:
        data_str = escape_literal(data)
        query = f"CREATE {table} CONTENT {data_str};"
        self._buffer(query)
        mock_id = data.get('id') if isinstance(data, dict) else None
        return [{"result": [{"id": mock_id}] if mock_id else [{"id": f"{table}:pending"}], "status": "OK", "time": "0ms"}]
        
    def insert(self, table: str, data: Any) -> Any:
        data_str = escape_literal(data)
        query = f"INSERT INTO {table} {data_str};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]

    def merge(self, table: str, data: Any) -> Any:
        data_str = escape_literal(data)
        query = f"UPDATE {table} MERGE {data_str};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]
        
    def update(self, table: str, data: Any) -> Any:
        data_str = escape_literal(data)
        query = f"UPDATE {table} CONTENT {data_str};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]
        
    def delete(self, table: str) -> Any:
        query = f"DELETE {table};"
        self._buffer(query)
        return [{"result": [], "status": "OK", "time": "0ms"}]


@asynccontextmanager
async def transaction(connection: Optional[Union[SurrealEngineAsyncConnection, str]] = None):
    """
    Asynchronous context manager for SurrealDB transactions.
    Buffers mutations via a Write-Behind proxy and compiles them to a single string execution.
    """
    if isinstance(connection, str):
        conn = ConnectionRegistry.get_async_connection(connection)
    else:
        conn = connection or ConnectionRegistry.get_default_async_connection()
        
    pinned_connection = None
    token = None
    original_client = conn.client
    
    if conn.use_pool:
        pinned_connection = await conn.pool.get_connection()
        token = _current_transaction_connection.set(pinned_connection)
        
    # Inject the proxy interceptor!
    proxy = AsyncTransactionClientProxy(original_client)
    conn.client = proxy

    try:
        yield conn
        
        # Compile and execute buffer on successful exit
        batch_query = proxy.compile()
        if batch_query:
            try:
                # Need to use original client to send the real request over the wire
                await original_client.query(batch_query)
            except Exception as e:
                logger.error(f"Transaction execution failed: {e}", exc_info=True)
                raise e
    finally:
        # Restore the original client
        conn.client = original_client
        
        if token:
            _current_transaction_connection.reset(token)
        if pinned_connection:
            await conn.pool.return_connection(pinned_connection)


@contextmanager
def transaction_sync(connection: Optional[Union[SurrealEngineSyncConnection, str]] = None):
    """
    Synchronous context manager for SurrealDB transactions.
    Buffers mutations via a Write-Behind proxy and compiles them to a single string execution.
    """
    if isinstance(connection, str):
        conn = ConnectionRegistry.get_sync_connection(connection)
    else:
        conn = connection or ConnectionRegistry.get_default_sync_connection()

    original_client = conn.client
    proxy = TransactionSyncClientProxy(original_client)
    conn.client = proxy

    try:
        yield conn
        
        batch_query = proxy.compile()
        if batch_query:
            try:
                original_client.query(batch_query)
            except Exception as e:
                logger.error(f"Sync transaction execution failed: {e}", exc_info=True)
                raise e
    finally:
        conn.client = original_client


def transactional(connection_name: Optional[Union[str, Callable]] = None):
    """
    Decorator for wrapping an async function within a database transaction.
    """
    def decorator(func: Any) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            conn = ConnectionRegistry.get_async_connection(connection_name) if isinstance(connection_name, str) else None
            async with transaction(conn):
                return await func(*args, **kwargs)
        return wrapper
        
    if callable(connection_name):
        func = connection_name
        connection_name = None
        return decorator(func)
        
    return decorator


def transactional_sync(connection_name: Optional[Union[str, Callable]] = None):
    """
    Decorator for wrapping a synchronous function within a database transaction.
    """
    def decorator(func: Any) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            conn = ConnectionRegistry.get_sync_connection(connection_name) if isinstance(connection_name, str) else None
            with transaction_sync(conn):
                return func(*args, **kwargs)
        return wrapper
        
    if callable(connection_name):
        func = connection_name
        connection_name = None
        return decorator(func)
        
    return decorator
