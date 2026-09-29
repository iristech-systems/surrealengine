"""Transaction support for SurrealEngine.

SurrealDB 3.x offers two very different transaction capabilities, and this
module exposes both behind one API:

**Native (interactive) transactions — WebSocket only.**
``begin()`` returns a transaction id which is then passed as ``txn_id`` on every
subsequent operation. Statements execute immediately inside the transaction, so
you get real record ids back and reads observe your own uncommitted writes.
This is the full-fidelity path.

**Buffered transactions — embedded and HTTP.**
``BEGIN TRANSACTION`` does not persist across separate RPC calls on these
transports, so statements are buffered as SurrealQL and dispatched as a single
``BEGIN ... COMMIT`` batch on exit. Atomicity and rollback are real, but nothing
has executed while the block is running. Consequences:

* record ids for new documents are generated client-side so they are still
  real and usable in later statements within the same block;
* reads cannot see writes from the same block, so they raise
  :class:`~surrealengine.exceptions.TransactionError` instead of silently
  returning stale data.
"""

import logging
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from uuid import uuid4

from surrealdb import RecordID

from .connection import (
    ConnectionRegistry,
    SurrealEngineAsyncConnection,
    SurrealEngineSyncConnection,
    _current_transaction_connection,
)
from .exceptions import TransactionError
from .surrealql import escape_literal

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable[..., Any])

#: Transports that support native interactive transactions.
_WS_SCHEMES = ("ws://", "wss://")

#: Statement prefixes that read data. These cannot be buffered, because the
#: caller needs the result immediately and the batch has not run yet.
_READ_PREFIXES = ("SELECT", "INFO", "RETURN", "SHOW")


def supports_native_transactions(url: Optional[str]) -> bool:
    """True if ``url`` can run native interactive transactions.

    SurrealDB 3.x restricts client-side transactions to WebSocket connections;
    embedded and HTTP transports raise ``UnsupportedFeatureError``.
    """
    return bool(url) and url.lower().startswith(_WS_SCHEMES)


def _is_read_statement(sql: str) -> bool:
    """True if ``sql`` returns data to the caller rather than only mutating."""
    return sql.strip().upper().startswith(_READ_PREFIXES)


def _substitute_vars(sql: str, variables: Optional[Dict[str, Any]]) -> str:
    """Inline ``$name`` bindings, since a buffered batch carries no bindings."""
    if not variables:
        return sql
    for key, value in variables.items():
        sql = sql.replace(f"${key}", escape_literal(value))
    return sql


def _terminate(sql: str) -> str:
    """Ensure ``sql`` ends with a semicolon so statements can be concatenated."""
    sql = sql.strip()
    return sql if sql.endswith(";") else f"{sql};"


def _new_record_id(table: str) -> RecordID:
    """Generate a record id client-side.

    Buffered transactions have not executed yet, so the server cannot hand back
    a generated id. Producing one here keeps ``save()`` truthful and lets later
    statements in the same block reference the new record.
    """
    return RecordID(table, uuid4().hex)


# ---------------------------------------------------------------------------
# Native (WebSocket) transactions
# ---------------------------------------------------------------------------


class _NativeTxnClient:
    """Routes every operation through a native transaction.

    Each SDK 3.x method accepts an optional ``txn_id``; this proxy injects the
    active transaction id so ODM calls participate in the transaction without
    the ODM having to know about it.
    """

    def __init__(self, client: Any, raw_client: Any, txn_id: Any) -> None:
        self._client = client
        self._raw_client = raw_client
        self._txn_id = txn_id

    def _accepts_txn_id(self, name: str) -> bool:
        import inspect

        try:
            target = getattr(self._raw_client, name)
        except AttributeError:
            return False
        try:
            return "txn_id" in inspect.signature(target).parameters
        except (TypeError, ValueError):
            return False

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if not callable(attr) or not self._accepts_txn_id(name):
            return attr

        def _call(*args: Any, **kwargs: Any) -> Any:
            kwargs.setdefault("txn_id", self._txn_id)
            return attr(*args, **kwargs)

        return _call


# ---------------------------------------------------------------------------
# Buffered (embedded / HTTP) transactions
# ---------------------------------------------------------------------------


class _BufferedTxnBase:
    """Shared SurrealQL buffering for embedded/HTTP transactions.

    Mutations are recorded as SurrealQL strings and compiled into a single
    ``BEGIN ... COMMIT`` batch. All methods here are pure string building — no
    I/O happens until :meth:`compile` output is dispatched.
    """

    def __init__(self, original_client: Any) -> None:
        self._original = original_client
        self.queries: List[str] = []

    def __getattr__(self, name: str) -> Any:
        """Pass through anything we don't intercept."""
        return getattr(self._original, name)

    def _buffer(self, sql: str) -> None:
        self.queries.append(_terminate(sql))

    def compile(self) -> str:
        """Compile buffered mutations into one atomic batch."""
        if not self.queries:
            return ""
        statements = "\n".join(self.queries)
        return f"BEGIN TRANSACTION;\n{statements}\nCOMMIT TRANSACTION;"

    # -- statement builders -------------------------------------------------

    def _plan_query(self, sql: str, variables: Optional[Dict[str, Any]]) -> Any:
        if _is_read_statement(sql):
            raise TransactionError(
                "Reads are not supported inside a transaction on this connection "
                f"({self._describe_transport()}). The transaction is buffered and "
                "dispatched on exit, so this statement cannot see writes made in "
                "the same block:\n\n"
                f"    {sql.strip()[:120]}\n\n"
                "Use a ws:// or wss:// connection for interactive transactions, "
                "or move the read outside the transaction block."
            )
        self._buffer(_substitute_vars(sql, variables))
        return [[]]

    def _plan_create(self, table: Any, data: Any) -> Dict[str, Any]:
        record = data.get("id") if isinstance(data, dict) else None
        if record is None:
            record = _new_record_id(str(table))

        if not isinstance(data, dict):
            self._buffer(f"CREATE {escape_literal(record)} CONTENT {escape_literal(data)}")
            return {"id": record}

        # SurrealDB rejects `id` inside a CONTENT clause when the record is
        # already addressed explicitly, so send the body without it...
        body = {k: v for k, v in data.items() if k != "id"}
        self._buffer(f"CREATE {escape_literal(record)} CONTENT {escape_literal(body)}")
        # ...but hand the caller the full record, mirroring the SDK.
        return {**body, "id": record}

    def _plan_upsert(self, record: Any, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            self._buffer(f"UPSERT {escape_literal(record)} CONTENT {escape_literal(data)}")
            return {"id": record}

        body = {k: v for k, v in data.items() if k != "id"}
        self._buffer(f"UPSERT {escape_literal(record)} CONTENT {escape_literal(body)}")
        return {**body, "id": record}

    def _plan_insert(self, table: Any, data: Any) -> List[Any]:
        self._buffer(f"INSERT INTO {table} {escape_literal(data)}")
        return data if isinstance(data, list) else [data]

    def _plan_merge(self, record: Any, data: Any) -> Dict[str, Any]:
        body = (
            {k: v for k, v in data.items() if k != "id"}
            if isinstance(data, dict)
            else data
        )
        self._buffer(f"UPDATE {escape_literal(record)} MERGE {escape_literal(body)}")
        merged = dict(body) if isinstance(body, dict) else {}
        merged["id"] = record
        return merged

    def _plan_content(self, record: Any, data: Any) -> Dict[str, Any]:
        body = (
            {k: v for k, v in data.items() if k != "id"}
            if isinstance(data, dict)
            else data
        )
        self._buffer(f"UPDATE {escape_literal(record)} CONTENT {escape_literal(body)}")
        content = dict(body) if isinstance(body, dict) else {}
        content["id"] = record
        return content

    def _plan_patch(self, record: Any, data: Any) -> Dict[str, Any]:
        self._buffer(f"UPDATE {escape_literal(record)} PATCH {escape_literal(data)}")
        return {"id": record}

    def _plan_delete(self, record: Any) -> Dict[str, Any]:
        self._buffer(f"DELETE {escape_literal(record)}")
        return {"id": record}

    def _describe_transport(self) -> str:
        return "buffered transaction"


class _AsyncBufferedCrudBuilder:
    """Async stand-in for the SDK CRUD builder inside a buffered transaction."""

    def __init__(self, txn: "_AsyncBufferedTxnClient", record: Any) -> None:
        self._txn = txn
        self._record = record

    async def merge(self, data: Any) -> Any:
        return self._txn._plan_merge(self._record, data)

    async def content(self, data: Any) -> Any:
        return self._txn._plan_content(self._record, data)

    async def patch(self, data: Any) -> Any:
        return self._txn._plan_patch(self._record, data)

    async def replace(self, data: Any) -> Any:
        return self._txn._plan_content(self._record, data)


class _SyncBufferedCrudBuilder:
    """Sync stand-in for the SDK CRUD builder inside a buffered transaction."""

    def __init__(self, txn: "_SyncBufferedTxnClient", record: Any) -> None:
        self._txn = txn
        self._record = record

    def merge(self, data: Any) -> Any:
        return self._txn._plan_merge(self._record, data)

    def content(self, data: Any) -> Any:
        return self._txn._plan_content(self._record, data)

    def patch(self, data: Any) -> Any:
        return self._txn._plan_patch(self._record, data)

    def replace(self, data: Any) -> Any:
        return self._txn._plan_content(self._record, data)


class _AsyncBufferedTxnClient(_BufferedTxnBase):
    """Async write-behind client used for embedded/HTTP transactions."""

    async def query(self, sql: str, vars: Optional[Dict] = None) -> Any:
        return self._plan_query(sql, vars)

    async def create(self, table: Any, data: Any = None) -> Any:
        return self._plan_create(table, data)

    async def upsert(self, record: Any, data: Any = None) -> Any:
        return self._plan_upsert(record, data)

    async def insert(self, table: Any, data: Any = None) -> Any:
        return self._plan_insert(table, data)

    async def delete(self, record: Any) -> Any:
        return self._plan_delete(record)

    def update(self, record: Any, data: Any = None) -> Any:
        """Return a chainable builder, mirroring SDK 3.x ``update(id).merge()``."""
        if data is not None:
            return self._plan_content(record, data)
        return _AsyncBufferedCrudBuilder(self, record)


class _SyncBufferedTxnClient(_BufferedTxnBase):
    """Sync write-behind client used for embedded/HTTP transactions."""

    def query(self, sql: str, vars: Optional[Dict] = None) -> Any:
        return self._plan_query(sql, vars)

    def create(self, table: Any, data: Any = None) -> Any:
        return self._plan_create(table, data)

    def upsert(self, record: Any, data: Any = None) -> Any:
        return self._plan_upsert(record, data)

    def insert(self, table: Any, data: Any = None) -> Any:
        return self._plan_insert(table, data)

    def delete(self, record: Any) -> Any:
        return self._plan_delete(record)

    def update(self, record: Any, data: Any = None) -> Any:
        """Return a chainable builder, mirroring SDK 3.x ``update(id).merge()``."""
        if data is not None:
            return self._plan_content(record, data)
        return _SyncBufferedCrudBuilder(self, record)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@asynccontextmanager
async def transaction(
    connection: Optional[Union[SurrealEngineAsyncConnection, str]] = None
):
    """Asynchronous transaction context manager.

    Uses native interactive transactions on WebSocket connections, and a
    buffered ``BEGIN ... COMMIT`` batch on embedded/HTTP connections.
    """
    if isinstance(connection, str):
        conn = ConnectionRegistry.get_async_connection(connection)
    else:
        conn = connection or ConnectionRegistry.get_default_async_connection()

    if supports_native_transactions(getattr(conn, "url", None)):
        async with _native_transaction_async(conn) as active:
            yield active
        return

    async with _buffered_transaction_async(conn) as active:
        yield active


@asynccontextmanager
async def _native_transaction_async(conn: Any):
    """Native interactive transaction over WebSocket."""
    original_client = conn.client
    raw_client = getattr(conn, "_actual_client", original_client)

    txn_id = await original_client.begin()
    conn.client = _NativeTxnClient(original_client, raw_client, txn_id)
    try:
        yield conn
    except BaseException:
        conn.client = original_client
        try:
            await original_client.cancel(txn_id)
        except Exception as cancel_exc:
            logger.error("Transaction cancel failed: %s", cancel_exc, exc_info=True)
        raise
    else:
        conn.client = original_client
        await original_client.commit(txn_id)
    finally:
        conn.client = original_client


@asynccontextmanager
async def _buffered_transaction_async(conn: Any):
    """Buffered transaction for embedded/HTTP connections."""
    pinned_connection = None
    token = None
    original_client = conn.client

    if getattr(conn, "use_pool", False):
        pinned_connection = await conn.pool.get_connection()
        token = _current_transaction_connection.set(pinned_connection)

    proxy = _AsyncBufferedTxnClient(original_client)
    conn.client = proxy

    try:
        yield conn

        batch_query = proxy.compile()
        if batch_query:
            # Restore first so the batch goes out on the real client.
            conn.client = original_client
            await original_client.query(batch_query)
    finally:
        conn.client = original_client
        if token:
            _current_transaction_connection.reset(token)
        if pinned_connection:
            await conn.pool.return_connection(pinned_connection)


@contextmanager
def transaction_sync(
    connection: Optional[Union[SurrealEngineSyncConnection, str]] = None
):
    """Synchronous transaction context manager.

    Uses native interactive transactions on WebSocket connections, and a
    buffered ``BEGIN ... COMMIT`` batch on embedded/HTTP connections.
    """
    if isinstance(connection, str):
        conn = ConnectionRegistry.get_sync_connection(connection)
    else:
        conn = connection or ConnectionRegistry.get_default_sync_connection()

    if supports_native_transactions(getattr(conn, "url", None)):
        with _native_transaction_sync(conn) as active:
            yield active
        return

    with _buffered_transaction_sync(conn) as active:
        yield active


@contextmanager
def _native_transaction_sync(conn: Any):
    """Native interactive transaction over WebSocket (sync)."""
    original_client = conn.client
    raw_client = getattr(conn, "_actual_client", original_client)

    txn_id = original_client.begin()
    conn.client = _NativeTxnClient(original_client, raw_client, txn_id)
    try:
        yield conn
    except BaseException:
        conn.client = original_client
        try:
            original_client.cancel(txn_id)
        except Exception as cancel_exc:
            logger.error("Transaction cancel failed: %s", cancel_exc, exc_info=True)
        raise
    else:
        conn.client = original_client
        original_client.commit(txn_id)
    finally:
        conn.client = original_client


@contextmanager
def _buffered_transaction_sync(conn: Any):
    """Buffered transaction for embedded/HTTP connections (sync)."""
    original_client = conn.client
    proxy = _SyncBufferedTxnClient(original_client)
    conn.client = proxy

    try:
        yield conn

        batch_query = proxy.compile()
        if batch_query:
            conn.client = original_client
            original_client.query(batch_query)
    finally:
        conn.client = original_client


def transactional(connection_name: Optional[Union[str, Callable]] = None):
    """Decorator wrapping an async function in a transaction."""

    def decorator(func: Any) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            conn = (
                ConnectionRegistry.get_async_connection(connection_name)
                if isinstance(connection_name, str)
                else None
            )
            async with transaction(conn):
                return await func(*args, **kwargs)

        return wrapper

    if callable(connection_name):
        func = connection_name
        connection_name = None
        return decorator(func)

    return decorator


def transactional_sync(connection_name: Optional[Union[str, Callable]] = None):
    """Decorator wrapping a synchronous function in a transaction."""

    def decorator(func: Any) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            conn = (
                ConnectionRegistry.get_sync_connection(connection_name)
                if isinstance(connection_name, str)
                else None
            )
            with transaction_sync(conn):
                return func(*args, **kwargs)

        return wrapper

    if callable(connection_name):
        func = connection_name
        connection_name = None
        return decorator(func)

    return decorator
