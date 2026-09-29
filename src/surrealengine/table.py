"""
Standalone Table Management API.

Provides DDL operations (CREATE, DROP, DEFINE FIELD, DEFINE INDEX, etc.)
without requiring a Document subclass. All public methods follow the
polyglot pattern: async versions return coroutines, sync versions have
a ``_sync`` suffix.

Usage::

    from surrealengine import Table, FieldDef, IndexDef

    # Async
    await Table.create("person", fields=[
        FieldDef("name", "string", required=True),
        FieldDef("age", "int"),
    ])

    # Sync
    Table.create_sync("person", fields=[...])

    # Check existence
    assert await Table.exists("person")

    # List all tables
    tables = await Table.list()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .connection import ConnectionRegistry
from .context import get_active_connection
from .exceptions import OperationError

logger = logging.getLogger(__name__)


@dataclass
class FieldDef:
    """Describes a table field for standalone DDL operations.

    Args:
        name: Field name in the database.
        type: SurrealQL type string (e.g. ``"string"``, ``"int"``,
              ``"option<record<user>>"``, ``"array<float>"``).
        required: If True, emits ``ASSERT $value != NONE``.
        default: A Python literal used as DEFAULT. Mutually exclusive
                 with *default_literal*.
        default_literal: Raw SurrealQL expression for DEFAULT. Mutually
                         exclusive with *default*.
        min_length: For string fields, asserts ``string::len($value) >= N``.
        max_length: For string fields, asserts ``string::len($value) <= N``.
        regex_pattern: For string fields, asserts ``string::matches(...)``.
        choices: For string fields, asserts ``$value IN [...]``.
        min_value: For numeric fields, asserts ``$value >= N``.
        max_value: For numeric fields, asserts ``$value <= N``.
        assert_expr: Additional raw SurrealQL assertion expression.
        computed: SurrealQL expression for a computed field.
        comment: Field comment.
        is_set: If True, emits ``VALUE $value.distinct()``.
        reference: Raw reference clause (e.g. ``REFERENCE ON DELETE CASCADE``).
        flexible: If True, the field is defined as ``FLEXIBLE`` (for object types).
        embedded_fields: Recursive sub-field definitions for embedded documents.
    """
    name: str
    type: str
    required: bool = True
    default: Any = None
    default_literal: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    regex_pattern: Optional[str] = None
    choices: Optional[List[Union[str, int, float, bool]]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    assert_expr: Optional[str] = None
    computed: Optional[str] = None
    comment: Optional[str] = None
    is_set: bool = False
    reference: Optional[str] = None
    flexible: bool = False
    embedded_fields: Optional[List[FieldDef]] = None


@dataclass
class IndexDef:
    """Describes a table index for standalone DDL operations.

    Args:
        name: Index name.
        fields: List of field names the index covers.
        unique: Emit ``UNIQUE``.
        search: Emit ``FULLTEXT`` (mutually exclusive with *unique*).
        analyzer: Analyzer name for fulltext indexes.
        bm25: Append ``BM25`` to fulltext index.
        highlights: Append ``HIGHLIGHTS`` to fulltext index.
        vector: Dict with keys ``dimension`` (int) and optionally
                ``distance`` (str, e.g. ``"cosine"``) for HNSW indexes.
        comment: Index comment.
    """
    name: str
    fields: List[str]
    unique: bool = False
    search: bool = False
    analyzer: Optional[str] = None
    bm25: bool = False
    highlights: bool = False
    vector: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None


class Table:
    """Standalone Table Management API.

    All methods are classmethods. Async methods accept an optional
    *connection* keyword; if omitted they auto-resolve via
    ``get_active_connection(async_mode=True)``. Sync methods behave
    equivalently with ``async_mode=False``.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_field_sql(table_name: str, field: FieldDef) -> str:
        """Build a single ``DEFINE FIELD`` statement from a FieldDef."""
        # Determine the type string (FLEXIBLE wrapping for object types)
        type_str = field.type
        if field.flexible and not type_str.endswith("FLEXIBLE"):
            if type_str in ("object",):
                type_str = "object FLEXIBLE"
            elif not type_str.startswith("object"):
                type_str = f"object FLEXIBLE"

        stmt = f"DEFINE FIELD {field.name} ON {table_name} TYPE {type_str}"

        # Build ASSERT expressions
        exprs: List[str] = []
        if field.required:
            exprs.append("$value != NONE")
        if field.min_length is not None:
            exprs.append(f"string::len($value) >= {int(field.min_length)}")
        if field.max_length is not None:
            exprs.append(f"string::len($value) <= {int(field.max_length)}")
        if field.regex_pattern is not None:
            from .surrealql import escape_literal
            exprs.append(f"string::matches($value, {escape_literal(field.regex_pattern)})")
        if field.choices is not None:
            vals: List[str] = []
            for v in field.choices:
                if isinstance(v, str):
                    s = v.replace("\\", r"\\").replace('"', r"\"")
                    vals.append(f'"{s}"')
                else:
                    vals.append(str(v).lower() if isinstance(v, bool) else str(v))
            exprs.append(f"$value IN [{', '.join(vals)}]")
        if field.min_value is not None:
            exprs.append(f"$value >= {field.min_value}")
        if field.max_value is not None:
            exprs.append(f"$value <= {field.max_value}")
        if field.assert_expr is not None:
            exprs.append(field.assert_expr)

        if exprs:
            stmt += " ASSERT " + " AND ".join(exprs)

        # Computed, VALUE, DEFAULT, REFERENCE (mutually exclusive-ish)
        if field.computed is not None:
            stmt += f" COMPUTED {field.computed}"
        elif field.is_set and not (type_str == "set" or "set<" in type_str):
            # Native set<...> types are already deduplicated in SurrealDB 3.x,
            # and $value.distinct() was removed for the set type — only emit
            # the VALUE clause when the column isn't a native set. Note the
            # type may be a union like 'none | set<none | string>'.
            stmt += " VALUE $value.distinct()"
        elif field.reference is not None:
            stmt += f" {field.reference}"
        elif field.default_literal is not None:
            stmt += f" DEFAULT {field.default_literal}"
        elif field.default is not None:
            from .surrealql import escape_literal
            stmt += f" DEFAULT {escape_literal(field.default)}"

        # Comment
        if field.comment is not None:
            c = field.comment.replace("\\", r"\\").replace('"', r"\"")
            stmt += f' COMMENT "{c}"'

        return stmt

    @staticmethod
    def _build_field_sql_recursive(
        table_name: str, field: FieldDef
    ) -> List[str]:
        """Build DEFINE FIELD statements for a field and its embedded children."""
        stmts = [Table._build_field_sql(table_name, field)]
        if field.embedded_fields:
            for sub in field.embedded_fields:
                full_name = f"{field.name}.{sub.name}"
                sub_fd = FieldDef(
                    name=full_name,
                    type=sub.type,
                    required=sub.required,
                    min_length=sub.min_length,
                    max_length=sub.max_length,
                    regex_pattern=sub.regex_pattern,
                    choices=sub.choices,
                    min_value=sub.min_value,
                    max_value=sub.max_value,
                    assert_expr=sub.assert_expr,
                    comment=sub.comment,
                    embedded_fields=sub.embedded_fields,
                )
                stmts.extend(Table._build_field_sql_recursive(table_name, sub_fd))
        return stmts

    @staticmethod
    def _build_index_sql(table_name: str, index: IndexDef) -> str:
        """Build a ``DEFINE INDEX`` statement from an IndexDef."""
        fields_str = ", ".join(index.fields)
        stmt = f"DEFINE INDEX {index.name} ON {table_name} FIELDS {fields_str}"

        if index.unique:
            stmt += " UNIQUE"
        elif index.search:
            stmt += " FULLTEXT"
            if index.analyzer:
                stmt += f" ANALYZER {index.analyzer}"
            if index.bm25:
                stmt += " BM25"
            if index.highlights:
                stmt += " HIGHLIGHTS"
        elif index.vector:
            dim = index.vector.get("dimension") or index.vector.get("dim")
            if dim is not None:
                dist = index.vector.get("distance") or index.vector.get("metric", "cosine")
                stmt += f" HNSW DIMENSION {dim} DIST {dist}"

        if index.comment:
            c = index.comment.replace("\\", r"\\").replace('"', r"\"")
            stmt += f' COMMENT "{c}"'

        return stmt

    @staticmethod
    def _build_table_ddl(
        name: str,
        *,
        schemafull: bool = True,
        relation: bool = False,
        time_series: Optional[str] = None,
        comment: Optional[str] = None,
        drop: bool = False,
        as_select: Optional[str] = None,
        overwrite: bool = False,
        if_not_exists: bool = False,
    ) -> str:
        """Build a ``DEFINE TABLE`` statement.

        When *as_select* is provided, generates a view definition
        (``DEFINE TABLE … AS (SELECT …)``). In this case the
        *schemafull*, *relation*, *time_series*, and *drop* parameters
        are ignored because the schema is derived from the query.
        """
        if as_select:
            modifier = ""
            if overwrite:
                modifier = "OVERWRITE "
            elif if_not_exists:
                modifier = "IF NOT EXISTS "
            return f"DEFINE TABLE {modifier}{name} AS {as_select}"

        schema_type = "SCHEMAFULL" if schemafull else "SCHEMALESS"
        stmt = f"DEFINE TABLE {name} "
        if relation:
            stmt += "TYPE RELATION "
        stmt += schema_type
        if drop:
            stmt += " DROP"
        if time_series is not None:
            stmt += f" TYPE TIMESTAMP TIMEFIELD {time_series}"
        if comment is not None:
            escaped = comment.replace("\\", r"\\").replace('"', r"\"")
            stmt += f' COMMENT "{escaped}"'
        return stmt

    @staticmethod
    def _build_sequence_ddl(
        name: str, *, batch: int = 1, start: int = 1
    ) -> str:
        """Build a ``DEFINE SEQUENCE`` statement."""
        return f"DEFINE SEQUENCE IF NOT EXISTS {name} BATCH {batch} START {start}"

    # ------------------------------------------------------------------
    # Connection resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_connection(
        connection: Any = None, *, async_mode: bool = True
    ) -> Any:
        if connection is not None:
            return connection
        return get_active_connection(async_mode=async_mode)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        name: str,
        *,
        schemafull: bool = True,
        fields: Optional[Sequence[FieldDef]] = None,
        indexes: Optional[Sequence[IndexDef]] = None,
        events: Optional[Sequence[Any]] = None,
        relation: bool = False,
        time_series: Optional[str] = None,
        sequence: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
        drop: bool = False,
        as_select: Optional[str] = None,
        overwrite: bool = False,
        if_not_exists: bool = False,
        connection: Any = None,
    ) -> None:
        """Create a table (or view) with optional fields, indexes, and events.

        When *as_select* is provided, creates a view instead of a regular
        table (``DEFINE TABLE … AS (SELECT …)``). In this mode, fields,
        indexes, and events are skipped because the schema derives from
        the query.

        Args:
            name: Table name.
            schemafull: If True, ``SCHEMAFULL``; otherwise ``SCHEMALESS``.
            fields: List of ``FieldDef`` objects defining columns.
            indexes: List of ``IndexDef`` objects.
            events: List of ``Event`` objects.
            relation: If True, emits ``TYPE RELATION``.
            time_series: ``TIMESTAMP TIMEFIELD`` field name.
            sequence: Dict with ``"name"``, optionally ``"batch"``, ``"start"``.
            comment: Table comment.
            drop: If True, appends ``DROP`` to the table definition.
            as_select: SurrealQL SELECT query for view definition.
            overwrite: If True, emits ``DEFINE TABLE OVERWRITE``.
            if_not_exists: If True, emits ``DEFINE TABLE IF NOT EXISTS``.
            connection: An async connection (auto-resolved if omitted).
        """
        conn = cls._resolve_connection(connection, async_mode=True)

        # 1. DEFINE TABLE / VIEW
        ddl = cls._build_table_ddl(
            name,
            schemafull=schemafull,
            relation=relation,
            time_series=time_series,
            comment=comment,
            drop=drop,
            as_select=as_select,
            overwrite=overwrite,
            if_not_exists=if_not_exists,
        )
        await conn.client.query(ddl)

        if as_select:
            return  # Schema is derived from the query

        # 2. DEFINE SEQUENCE (if requested)
        if sequence:
            seq_ddl = cls._build_sequence_ddl(
                sequence.get("name", f"{name}_sequence"),
                batch=sequence.get("batch", 1),
                start=sequence.get("start", 1),
            )
            await conn.client.query(seq_ddl)

        # 3. DEFINE FIELD for each column
        if fields:
            for field_def in fields:
                stmts = cls._build_field_sql_recursive(name, field_def)
                for stmt in stmts:
                    await conn.client.query(stmt)

        # 4. DEFINE INDEX for each index
        if indexes:
            for idx_def in indexes:
                stmt = cls._build_index_sql(name, idx_def)
                await conn.client.query(stmt)

        # 5. DEFINE EVENT for each event
        if events:
            for event in events:
                if hasattr(event, "to_sql"):
                    await conn.client.query(event.to_sql(name))

    @classmethod
    def create_sync(
        cls,
        name: str,
        *,
        schemafull: bool = True,
        fields: Optional[Sequence[FieldDef]] = None,
        indexes: Optional[Sequence[IndexDef]] = None,
        events: Optional[Sequence[Any]] = None,
        relation: bool = False,
        time_series: Optional[str] = None,
        sequence: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
        drop: bool = False,
        as_select: Optional[str] = None,
        overwrite: bool = False,
        if_not_exists: bool = False,
        connection: Any = None,
    ) -> None:
        """Synchronous version of :meth:`create`."""
        conn = cls._resolve_connection(connection, async_mode=False)

        ddl = cls._build_table_ddl(
            name,
            schemafull=schemafull,
            relation=relation,
            time_series=time_series,
            comment=comment,
            drop=drop,
            as_select=as_select,
            overwrite=overwrite,
            if_not_exists=if_not_exists,
        )
        conn.client.query(ddl)

        if as_select:
            return

        if sequence:
            seq_ddl = cls._build_sequence_ddl(
                sequence.get("name", f"{name}_sequence"),
                batch=sequence.get("batch", 1),
                start=sequence.get("start", 1),
            )
            conn.client.query(seq_ddl)

        if fields:
            for field_def in fields:
                stmts = cls._build_field_sql_recursive(name, field_def)
                for stmt in stmts:
                    conn.client.query(stmt)

        if indexes:
            for idx_def in indexes:
                stmt = cls._build_index_sql(name, idx_def)
                conn.client.query(stmt)

        if events:
            for event in events:
                if hasattr(event, "to_sql"):
                    conn.client.query(event.to_sql(name))

    # ------------------------------------------------------------------
    # DROP
    # ------------------------------------------------------------------

    @classmethod
    async def drop(
        cls,
        name: str,
        *,
        if_exists: bool = False,
        connection: Any = None,
    ) -> bool:
        """Drop a table.

        Returns True if the table was dropped, False if it didn't exist
        (only when *if_exists* is True).
        """
        conn = cls._resolve_connection(connection, async_mode=True)
        if if_exists and not await cls.exists(name, connection=conn):
            return False
        await conn.client.query(f"REMOVE TABLE {name}")
        return True

    @classmethod
    def drop_sync(
        cls,
        name: str,
        *,
        if_exists: bool = False,
        connection: Any = None,
    ) -> bool:
        """Synchronous version of :meth:`drop`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        if if_exists and not cls.exists_sync(name, connection=conn):
            return False
        conn.client.query(f"REMOVE TABLE {name}")
        return True

    # ------------------------------------------------------------------
    # EXISTS
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tables(result: Any) -> List[str]:
        """Extract table names from an ``INFO FOR DB`` result.

        Handles both list-wrapped (remote) and flat dict (embedded) formats.
        """
        tables_dict: Dict[str, Any] = {}
        if isinstance(result, dict):
            tables_dict = result.get("tables", {}) or {}
        elif isinstance(result, list) and len(result) > 0:
            row = result[0]
            if isinstance(row, dict):
                tables_dict = row.get("tables", {}) or {}
        return sorted(str(k) for k in tables_dict)

    @classmethod
    async def list(
        cls,
        *,
        connection: Any = None,
    ) -> List[str]:
        """Return a list of all table names in the current namespace/database.

        Uses ``INFO FOR DB`` under the hood (compatible with both embedded and
        remote engines).
        """
        conn = cls._resolve_connection(connection, async_mode=True)
        result = await conn.client.query("INFO FOR DB")
        return cls._extract_tables(result)

    @classmethod
    def list_sync(
        cls,
        *,
        connection: Any = None,
    ) -> List[str]:
        """Synchronous version of :meth:`list`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        result = conn.client.query("INFO FOR DB")
        return cls._extract_tables(result)

    # ------------------------------------------------------------------
    # EXISTS
    # ------------------------------------------------------------------

    @classmethod
    async def exists(
        cls,
        name: str,
        *,
        connection: Any = None,
    ) -> bool:
        """Check if a table exists.

        Uses ``INFO FOR DB`` to check for the table name.
        """
        tables = await cls.list(connection=connection)
        return name in tables

    @classmethod
    def exists_sync(
        cls,
        name: str,
        *,
        connection: Any = None,
    ) -> bool:
        """Synchronous version of :meth:`exists`."""
        tables = cls.list_sync(connection=connection)
        return name in tables

    # ------------------------------------------------------------------
    # ADD FIELD
    # ------------------------------------------------------------------

    @classmethod
    async def add_field(
        cls,
        table_name: str,
        field: FieldDef,
        *,
        connection: Any = None,
    ) -> None:
        """Add a field (column) to an existing table."""
        conn = cls._resolve_connection(connection, async_mode=True)
        stmts = cls._build_field_sql_recursive(table_name, field)
        for stmt in stmts:
            await conn.client.query(stmt)

    @classmethod
    def add_field_sync(
        cls,
        table_name: str,
        field: FieldDef,
        *,
        connection: Any = None,
    ) -> None:
        """Synchronous version of :meth:`add_field`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        stmts = cls._build_field_sql_recursive(table_name, field)
        for stmt in stmts:
            conn.client.query(stmt)

    # ------------------------------------------------------------------
    # REMOVE FIELD
    # ------------------------------------------------------------------

    @classmethod
    async def remove_field(
        cls,
        table_name: str,
        field_name: str,
        *,
        connection: Any = None,
    ) -> None:
        """Remove a field from a table."""
        conn = cls._resolve_connection(connection, async_mode=True)
        await conn.client.query(f"REMOVE FIELD {field_name} ON {table_name}")

    @classmethod
    def remove_field_sync(
        cls,
        table_name: str,
        field_name: str,
        *,
        connection: Any = None,
    ) -> None:
        """Synchronous version of :meth:`remove_field`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        conn.client.query(f"REMOVE FIELD {field_name} ON {table_name}")

    # ------------------------------------------------------------------
    # CREATE INDEX
    # ------------------------------------------------------------------

    @classmethod
    async def create_index(
        cls,
        table_name: str,
        index: IndexDef,
        *,
        connection: Any = None,
    ) -> None:
        """Add an index to a table."""
        conn = cls._resolve_connection(connection, async_mode=True)
        stmt = cls._build_index_sql(table_name, index)
        await conn.client.query(stmt)

    @classmethod
    def create_index_sync(
        cls,
        table_name: str,
        index: IndexDef,
        *,
        connection: Any = None,
    ) -> None:
        """Synchronous version of :meth:`create_index`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        stmt = cls._build_index_sql(table_name, index)
        conn.client.query(stmt)

    # ------------------------------------------------------------------
    # DROP INDEX
    # ------------------------------------------------------------------

    @classmethod
    async def drop_index(
        cls,
        table_name: str,
        index_name: str,
        *,
        if_exists: bool = False,
        connection: Any = None,
    ) -> bool:
        """Remove an index from a table.

        Returns True if the index was dropped, False if it didn't exist
        (only when *if_exists* is True).
        """
        conn = cls._resolve_connection(connection, async_mode=True)
        stmt = f"REMOVE INDEX {index_name} ON {table_name}"
        try:
            await conn.client.query(stmt)
            return True
        except Exception:
            if if_exists:
                return False
            raise

    @classmethod
    def drop_index_sync(
        cls,
        table_name: str,
        index_name: str,
        *,
        if_exists: bool = False,
        connection: Any = None,
    ) -> bool:
        """Synchronous version of :meth:`drop_index`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        stmt = f"REMOVE INDEX {index_name} ON {table_name}"
        try:
            conn.client.query(stmt)
            return True
        except Exception:
            if if_exists:
                return False
            raise

    # ------------------------------------------------------------------
    # INFO
    # ------------------------------------------------------------------

    @classmethod
    async def info(
        cls,
        name: str,
        *,
        connection: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """Return metadata about a table from ``INFO FOR TABLE``.

        Returns a dict with keys such as ``tb`` (table definition),
        ``fd`` (fields), ``ix`` (indexes), ``ev`` (events),
        ``ft`` (fulltext indexes), or ``None`` if the table does not exist.
        """
        conn = cls._resolve_connection(connection, async_mode=True)
        if not await cls.exists(name, connection=conn):
            return None
        try:
            result = await conn.client.query(f"INFO FOR TABLE {name}")
        except Exception:
            return None
        if isinstance(result, dict) and len(result) > 0:
            return result
        if isinstance(result, list) and len(result) > 0:
            row = result[0]
            if isinstance(row, dict) and len(row) > 0:
                return row
        return None

    @classmethod
    def info_sync(
        cls,
        name: str,
        *,
        connection: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """Synchronous version of :meth:`info`."""
        conn = cls._resolve_connection(connection, async_mode=False)
        if not cls.exists_sync(name, connection=conn):
            return None
        try:
            result = conn.client.query(f"INFO FOR TABLE {name}")
        except Exception:
            return None
        if isinstance(result, dict) and len(result) > 0:
            return result
        if isinstance(result, list) and len(result) > 0:
            row = result[0]
            if isinstance(row, dict) and len(row) > 0:
                return row
        return None
