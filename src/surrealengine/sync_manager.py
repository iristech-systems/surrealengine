from __future__ import annotations

import asyncio
import datetime
import json
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional, Type

from .surrealql import escape_literal


class SyncMode(str, Enum):
    cache_readthrough = "cache_readthrough"
    mirror_realtime = "mirror_realtime"


class FreshnessMode(str, Enum):
    stale_ok = "stale_ok"
    realtime = "realtime"
    auto = "auto"


class SyncPolicy(str, Enum):
    ignored = "ignored"
    read_through = "read_through"
    mirrored = "mirrored"
    vector_hot = "vector_hot"


class BackpressurePolicy(str, Enum):
    drop_oldest = "drop_oldest"
    drop_latest = "drop_latest"
    block = "block"


@dataclass
class SyncConfig:
    mode: SyncMode = SyncMode.cache_readthrough
    auto_max_lag_ms: int = 750
    checkpoint_table: str = "_se_sync_checkpoint"
    stats_table: str = "_se_sync_stats"
    outbox_table: str = "_se_sync_outbox"


@dataclass
class SyncStatus:
    healthy: bool
    lag_ms: int
    route_counts: Dict[str, int]
    circuit_open: bool
    model_count: int


@dataclass
class LiveSubscription:
    key: str
    table: str
    where: Optional[str] = None
    actions: Optional[list[str]] = None
    queue_maxsize: int = 1000
    backpressure_policy: BackpressurePolicy = BackpressurePolicy.drop_oldest
    status: str = "registered"
    uuid: Optional[str] = None
    reconnect_attempts: int = 0
    last_error: Optional[str] = None
    last_event_at: Optional[datetime.datetime] = None


class SyncManager:
    """Route remote/local reads using freshness and model policy."""

    def __init__(self, remote: Any, local: Any, config: Optional[SyncConfig] = None):
        self.remote = remote
        self.local = local
        self.config = config or SyncConfig()
        self._model_policies: Dict[Type, SyncPolicy] = {}
        self._route_counts: Dict[str, int] = {"local": 0, "remote": 0}
        self._lag_ms: int = 0
        self._circuit_open: bool = False
        self._subscriptions: Dict[str, LiveSubscription] = {}
        self._sync_loop_task: Optional[asyncio.Task[None]] = None
        self._sync_loop_interval: float = 5.0  # seconds

    def start_sync_loop(self, interval: float = 5.0) -> None:
        """Start the background sync loop that drains the outbox periodically."""
        self._sync_loop_interval = max(1.0, interval)
        if self._sync_loop_task is not None and not self._sync_loop_task.done():
            return
        self._sync_loop_task = asyncio.create_task(self._sync_loop())

    async def stop_sync_loop(self) -> None:
        """Stop the background sync loop."""
        if self._sync_loop_task is None:
            return
        self._sync_loop_task.cancel()
        try:
            await self._sync_loop_task
        except asyncio.CancelledError:
            pass
        self._sync_loop_task = None

    async def _sync_loop(self) -> None:
        """Background loop: periodically drain the outbox."""
        while True:
            try:
                await asyncio.sleep(self._sync_loop_interval)
                applied = await self.drain_outbox()
                if applied:
                    self._lag_ms = 0
            except asyncio.CancelledError:
                break
            except Exception:
                continue

    def register_model(
        self, model_cls: Type, policy: SyncPolicy = SyncPolicy.read_through
    ) -> None:
        self._model_policies[model_cls] = policy

    def get_policy(self, model_cls: Optional[Type]) -> SyncPolicy:
        if model_cls is None:
            return SyncPolicy.read_through
        return self._model_policies.get(model_cls, SyncPolicy.read_through)

    def set_lag_ms(self, lag_ms: int) -> None:
        self._lag_ms = max(0, int(lag_ms))

    def set_circuit_open(self, open_state: bool) -> None:
        self._circuit_open = bool(open_state)

    def choose_route(self, model_cls: Optional[Type], freshness: str) -> str:
        mode = FreshnessMode(freshness)
        policy = self.get_policy(model_cls)

        if mode is FreshnessMode.realtime:
            return "remote"

        if policy is SyncPolicy.ignored:
            return "remote"

        if self.local is None:
            return "remote"

        if mode is FreshnessMode.stale_ok:
            return "local"

        # auto
        if self._circuit_open:
            return "remote"
        if self._lag_ms > int(self.config.auto_max_lag_ms):
            return "remote"
        return "local"

    def get_connection(self, route: str) -> Any:
        return self.local if route == "local" else self.remote

    def record_route(self, route: str) -> None:
        self._route_counts[route] = self._route_counts.get(route, 0) + 1

    async def status(self) -> SyncStatus:
        return self.status_sync()

    def status_sync(self) -> SyncStatus:
        return SyncStatus(
            healthy=not self._circuit_open,
            lag_ms=self._lag_ms,
            route_counts=dict(self._route_counts),
            circuit_open=self._circuit_open,
            model_count=len(self._model_policies),
        )

    def register_live_subscription(
        self,
        key: str,
        table: str,
        *,
        where: Optional[str] = None,
        actions: Optional[list[str]] = None,
        queue_maxsize: int = 1000,
        backpressure_policy: BackpressurePolicy = BackpressurePolicy.drop_oldest,
    ) -> LiveSubscription:
        sub = LiveSubscription(
            key=key,
            table=table,
            where=where,
            actions=actions,
            queue_maxsize=max(1, int(queue_maxsize)),
            backpressure_policy=BackpressurePolicy(backpressure_policy),
        )
        self._subscriptions[key] = sub
        return sub

    def unregister_live_subscription(self, key: str) -> None:
        self._subscriptions.pop(key, None)

    def get_live_subscription(self, key: str) -> Optional[LiveSubscription]:
        return self._subscriptions.get(key)

    def list_live_subscriptions(self) -> list[LiveSubscription]:
        return list(self._subscriptions.values())

    def mark_live_connected(self, key: str, uuid: str) -> None:
        sub = self._subscriptions.get(key)
        if sub is None:
            return
        sub.uuid = str(uuid)
        sub.status = "connected"
        sub.last_error = None
        sub.reconnect_attempts = 0

    def mark_live_event(self, key: str) -> None:
        sub = self._subscriptions.get(key)
        if sub is None:
            return
        sub.last_event_at = datetime.datetime.now(datetime.timezone.utc)

    def mark_live_error(self, key: str, error: Exception) -> None:
        sub = self._subscriptions.get(key)
        if sub is None:
            return
        sub.status = "error"
        sub.last_error = str(error)
        sub.reconnect_attempts += 1

    async def orchestrate_resubscribe(
        self,
        resubscribe_fn: Callable[[LiveSubscription], Awaitable[str]],
        *,
        max_attempts: int = 10,
        initial_delay: float = 0.5,
        backoff: float = 2.0,
        jitter: float = 0.1,
    ) -> Dict[str, str]:
        """Reconnect/resubscribe registered LIVE subscriptions.

        `resubscribe_fn` receives each subscription and must return a new UUID.
        """
        results: Dict[str, str] = {}
        for key, sub in list(self._subscriptions.items()):
            attempt = 0
            delay = max(0.05, float(initial_delay))
            while True:
                try:
                    new_uuid = await resubscribe_fn(sub)
                    self.mark_live_connected(key, new_uuid)
                    results[key] = new_uuid
                    break
                except Exception as exc:
                    self.mark_live_error(key, exc)
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    j = random.uniform(0.0, max(0.0, jitter))
                    await asyncio.sleep(delay + j)
                    delay = delay * max(1.0, float(backoff))
        return results

    async def ensure_metadata_tables(self) -> None:
        """Ensure checkpoint/stats tables exist on local store."""
        if self.local is None:
            return
        c = self.local.client
        is_async = self.local.is_async()
        try:
            from surrealdb.errors import AlreadyExistsError
        except ImportError:
            AlreadyExistsError = None
        ddl_statements = [
            f"DEFINE TABLE {self.config.checkpoint_table} SCHEMAFULL;",
            f"DEFINE FIELD table ON TABLE {self.config.checkpoint_table} TYPE string;",
            f"DEFINE FIELD cursor_type ON TABLE {self.config.checkpoint_table} TYPE string;",
            f"DEFINE FIELD cursor_value ON TABLE {self.config.checkpoint_table} TYPE string;",
            f"DEFINE FIELD updated_at ON TABLE {self.config.checkpoint_table} TYPE datetime;",
            f"DEFINE TABLE {self.config.stats_table} SCHEMAFULL;",
            f"DEFINE FIELD table ON TABLE {self.config.stats_table} TYPE string;",
            f"DEFINE FIELD lag_ms ON TABLE {self.config.stats_table} TYPE int;",
            f"DEFINE FIELD last_error ON TABLE {self.config.stats_table} TYPE option<string>;",
            f"DEFINE FIELD updated_at ON TABLE {self.config.stats_table} TYPE datetime;",
            f"DEFINE TABLE {self.config.outbox_table} SCHEMAFULL;",
            f"DEFINE FIELD model ON TABLE {self.config.outbox_table} TYPE string;",
            f"DEFINE FIELD action ON TABLE {self.config.outbox_table} TYPE string;",
            f"DEFINE FIELD record_id ON TABLE {self.config.outbox_table} TYPE string;",
            f"DEFINE FIELD data ON TABLE {self.config.outbox_table} TYPE string;",
            f"DEFINE FIELD created_at ON TABLE {self.config.outbox_table} TYPE datetime;",
            f"DEFINE FIELD synced_at ON TABLE {self.config.outbox_table} TYPE option<datetime>;",
        ]
        for stmt in ddl_statements:
            try:
                if is_async:
                    await c.query(stmt)
                else:
                    c.query(stmt)
            except Exception as e:
                if AlreadyExistsError is not None and isinstance(e, AlreadyExistsError):
                    continue
                if "already exists" in str(e).lower():
                    continue
                raise

    async def save_checkpoint(
        self,
        table: str,
        cursor_type: str,
        cursor_value: str,
        *,
        lag_ms: int = 0,
        last_error: Optional[str] = None,
    ) -> None:
        """Persist checkpoint and stats rows in local metadata tables."""
        if self.local is None:
            return
        q1 = (
            f"UPSERT {self.config.checkpoint_table}:{table} "
            "SET table = $table, cursor_type = $cursor_type, cursor_value = $cursor_value, updated_at = time::now();"
        )
        q2 = (
            f"UPSERT {self.config.stats_table}:{table} "
            "SET table = $table, lag_ms = $lag_ms, last_error = $last_error, updated_at = time::now();"
        )
        await self.local.client.query(
            q1,
            {
                "table": table,
                "cursor_type": str(cursor_type),
                "cursor_value": str(cursor_value),
            },
        )
        await self.local.client.query(
            q2,
            {
                "table": table,
                "lag_ms": int(lag_ms),
                "last_error": last_error,
            },
        )

        # Some runtimes (notably embedded variants) can ignore vars-based UPSERT.
        # Verify persistence and retry with inline literals when needed.
        persisted = await self.load_checkpoint(table)
        if persisted is None:
            checkpoint_rid = f"{self.config.checkpoint_table}:{table}"
            stats_rid = f"{self.config.stats_table}:{table}"
            q1_inline = (
                f"UPSERT {checkpoint_rid} "
                f"SET table = {escape_literal(table)}, "
                f"cursor_type = {escape_literal(str(cursor_type))}, "
                f"cursor_value = {escape_literal(str(cursor_value))}, "
                "updated_at = time::now();"
            )
            q2_inline = (
                f"UPSERT {stats_rid} "
                f"SET table = {escape_literal(table)}, "
                f"lag_ms = {int(lag_ms)}, "
                f"last_error = {escape_literal(last_error)}, "
                "updated_at = time::now();"
            )
            await self.local.client.query(q1_inline)
            await self.local.client.query(q2_inline)

    async def load_checkpoint(self, table: str) -> Optional[dict[str, Any]]:
        """Load a table checkpoint row from local metadata table."""
        if self.local is None:
            return None
        rid = f"{self.config.checkpoint_table}:{table}"
        query_candidates = [
            f"SELECT * FROM ONLY {rid};",
            f"SELECT * FROM {rid};",
            (
                f"SELECT * FROM {self.config.checkpoint_table} "
                f"WHERE id = {escape_literal(rid)} LIMIT 1;"
            ),
        ]
        for query in query_candidates:
            try:
                raw_rows = await self.local.client.query(query)
            except Exception:
                continue
            rows = self._normalize_query_rows(raw_rows)
            for row in rows:
                if isinstance(row, dict) and (
                    "cursor_value" in row or "cursor_type" in row or "table" in row
                ):
                    return row
        return None

    async def replay_table_changes(self, table: str, *, limit: int = 500) -> int:
        """Replay remote changefeed to local from stored checkpoint.

        Returns the number of applied events.
        """
        if self.remote is None or self.local is None:
            return 0
        checkpoint = await self.load_checkpoint(table)
        since_value: Any = 0
        if checkpoint and checkpoint.get("cursor_value") is not None:
            since_value = checkpoint.get("cursor_value")

        raw_events = await self.remote.show_changes(table, since=since_value, limit=limit)
        events = self._normalize_query_rows(raw_events)
        applied = 0
        last_cursor: Optional[str] = None

        for evt in events:
            if not isinstance(evt, dict):
                continue
            for action, record, cursor in self._extract_change_entries(evt):
                if not isinstance(record, dict):
                    continue
                rid = record.get("id")
                if not rid:
                    continue
                if action == "DELETE":
                    await self.local.client.query(f"DELETE {rid};")
                else:
                    await self.local.client.query(
                        f"UPSERT {rid} CONTENT $doc;", {"doc": record}
                    )
                applied += 1
                if cursor is not None:
                    last_cursor = cursor

        if last_cursor is not None:
            try:
                next_cursor = str(int(str(last_cursor)) + 1)
            except (ValueError, TypeError):
                next_cursor = str(last_cursor)
            await self.save_checkpoint(table, "versionstamp", next_cursor)
        return applied

    async def _query_local(self, q: str, vars: Optional[dict] = None) -> Any:
        """Execute a query on the local connection (handles async vs sync)."""
        if self.local is None:
            return None
        if self.local.is_async():
            return await self.local.client.query(q, *(vars,) if vars else ())
        return self.local.client.query(q, *(vars,) if vars else ())

    async def _query_remote(self, q: str, vars: Optional[dict] = None) -> Any:
        """Execute a query on the remote connection (handles async vs sync)."""
        if self.remote is None:
            return None
        if self.remote.is_async():
            return await self.remote.client.query(q, *(vars,) if vars else ())
        return self.remote.client.query(q, *(vars,) if vars else ())

    @staticmethod
    def _sql_literal(s: str) -> str:
        """Quote a string for inline use in SurrealQL."""
        escaped = s.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    def _enqueue_outbox_sync(
        self,
        model: str,
        action: str,
        record_id: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Synchronous implementation of enqueue_outbox."""
        if self.local is None:
            return
        import json as _json

        data_str = _json.dumps(data) if data else ""
        sql = self._sql_literal
        q = (
            f"CREATE {self.config.outbox_table} "
            f"SET model = {sql(model)}, "
            f"action = {sql(action)}, "
            f"record_id = {sql(record_id)}, "
            f"data = {sql(data_str)}, "
            f"created_at = time::now(), synced_at = NONE;"
        )
        try:
            self.local.client.query(q)
        except Exception:
            ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
            safe_rid = record_id.replace(".", "_").replace(":", "_")
            safe_model = model.replace(".", "_").replace(":", "_")
            rid = f"{self.config.outbox_table}:{safe_model}_{safe_rid}_{action}_{int(ts * 1000)}"
            self.local.client.query(
                f"UPSERT {rid} "
                f"SET model = {sql(model)}, "
                f"action = {sql(action)}, "
                f"record_id = {sql(record_id)}, "
                f"data = {sql(data_str)}, "
                "created_at = time::now(), synced_at = NONE;"
            )

    async def enqueue_outbox(
        self,
        model: str,
        action: str,
        record_id: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a local change in the outbox for later sync to remote."""
        if self.local is None:
            return
        if not self.local.is_async():
            self._enqueue_outbox_sync(model, action, record_id, data)
            return
        import json as _json

        sql = self._sql_literal
        data_str = _json.dumps(data) if data else ""
        q = (
            f"CREATE {self.config.outbox_table} "
            f"SET model = {sql(model)}, "
            f"action = {sql(action)}, "
            f"record_id = {sql(record_id)}, "
            f"data = {sql(data_str)}, "
            f"created_at = time::now(), synced_at = NONE;"
        )
        try:
            await self._query_local(q)
        except Exception:
            ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
            safe_rid = record_id.replace(".", "_").replace(":", "_")
            safe_model = model.replace(".", "_").replace(":", "_")
            rid = f"{self.config.outbox_table}:{safe_model}_{safe_rid}_{action}_{int(ts * 1000)}"
            await self._query_local(
                f"UPSERT {rid} "
                f"SET model = {sql(model)}, "
                f"action = {sql(action)}, "
                f"record_id = {sql(record_id)}, "
                f"data = {sql(data_str)}, "
                "created_at = time::now(), synced_at = NONE;"
            )

    async def drain_outbox(
        self,
        *,
        batch_size: int = 100,
        models: Optional[list[str]] = None,
    ) -> int:
        """Replay pending outbox entries to the remote and mark them synced.

        Returns the number of entries applied.
        """
        if self.local is None or self.remote is None:
            return 0

        where = "synced_at IS NONE"
        if models:
            clauses = [f"model = {escape_literal(m)}" for m in models]
            where += " AND (" + " OR ".join(clauses) + ")"
        q = (
            f"SELECT * FROM {self.config.outbox_table} "
            f"WHERE {where} ORDER BY created_at ASC LIMIT {int(batch_size)};"
        )
        raw = await self._query_local(q)
        rows = self._normalize_query_rows(raw)
        # Flatten one level: the sync connection wrapper already nests
        # flat results into list-of-lists to match the remote API shape.
        if rows and isinstance(rows[0], list):
            rows = rows[0]
        if not rows:
            return 0

        applied = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            rid = (row.get("record_id") or "").strip()
            action = (row.get("action") or "").upper()
            entry_id = row.get("id")
            if not rid or not entry_id:
                continue

            try:
                if action == "DELETE":
                    await self._query_remote(f"DELETE {rid};")
                elif action in ("CREATE", "UPDATE"):
                    doc_data = row.get("data")
                    # data is stored as a JSON string in the outbox
                    if isinstance(doc_data, str) and doc_data not in ("NONE", "None", ""):
                        try:
                            import json as _json
                            parsed = _json.loads(doc_data)
                        except Exception:
                            parsed = None
                    else:
                        parsed = doc_data if isinstance(doc_data, dict) else None

                    if isinstance(parsed, dict):
                        content = {k: v for k, v in parsed.items() if k != "id"}
                        await self._query_remote(
                            f"UPSERT {rid} CONTENT $doc;", {"doc": content}
                        )
                    else:
                        # data-less entry — just touch the record
                        await self._query_remote(f"UPSERT {rid} SET _synced_at = time::now();")
                else:
                    continue

                # Mark entry as synced
                mark_q = f"UPDATE {entry_id} SET synced_at = time::now();"
                await self._query_local(mark_q)
                applied += 1
            except Exception:
                # Log and continue with next entry
                continue

        return applied

    @staticmethod
    def _normalize_query_rows(value: Any) -> list[Any]:
        """Normalize common SDK query result envelopes to a row list."""
        cur = value
        for _ in range(8):
            if cur is None:
                return []
            if isinstance(cur, tuple):
                cur = list(cur)
                continue
            if isinstance(cur, str):
                try:
                    cur = json.loads(cur)
                    continue
                except Exception:
                    return []
            if isinstance(cur, dict):
                if "result" in cur and cur["result"] is not None:
                    cur = cur["result"]
                    continue
                if "data" in cur and cur["data"] is not None:
                    cur = cur["data"]
                    continue
                return [cur]
            if isinstance(cur, list):
                if not cur:
                    return []
                # Common SDK envelope: [{status: "OK", result: [...]}]
                if all(
                    isinstance(item, dict) and "result" in item and "status" in item
                    for item in cur
                ):
                    for item in reversed(cur):
                        result = item.get("result")
                        if result is not None:
                            cur = result
                            break
                    continue
                return cur
            return []
        if isinstance(cur, list):
            return cur
        if isinstance(cur, dict):
            return [cur]
        return []

    @staticmethod
    def _extract_change_entries(
        evt: dict[str, Any],
    ) -> list[tuple[str, Optional[dict[str, Any]], Optional[str]]]:
        """Extract one or more (action, record, versionstamp) tuples.

        Handles envelopes where `changes` can be a dict or a list.
        """
        action = str(evt.get("action") or "").upper()
        cursor = str(evt["versionstamp"]) if "versionstamp" in evt else None

        payload = evt.get("changes")
        if payload is None:
            payload = evt.get("change")

        entries: list[dict[str, Any]]
        if isinstance(payload, list):
            entries = [p for p in payload if isinstance(p, dict)]
        elif isinstance(payload, dict):
            entries = [payload]
        else:
            entries = [evt]

        out: list[tuple[str, Optional[dict[str, Any]], Optional[str]]] = []
        for entry in entries:
            entry_action = str(action or entry.get("action") or "").upper()
            current = entry.get("current")
            before = entry.get("before")

            # Handle native changefeed row format:
            # {"update": {...}} / {"delete": {...}} / {"create": {...}}
            if not isinstance(current, dict) and not isinstance(before, dict):
                for key, mapped in (
                    ("update", "UPDATE"),
                    ("delete", "DELETE"),
                    ("create", "CREATE"),
                ):
                    payload = entry.get(key)
                    if isinstance(payload, dict):
                        current = payload
                        if not entry_action:
                            entry_action = mapped
                        break

            if not entry_action:
                if isinstance(before, dict) and not isinstance(current, dict):
                    entry_action = "DELETE"
                else:
                    entry_action = "UPDATE"

            record = current or before
            if record is None and isinstance(entry.get("id"), (str, int)):
                record = entry
            out.append((entry_action, record if isinstance(record, dict) else None, cursor))

        return out


def create_sync_manager(
    remote: Any, local: Any, config: Optional[SyncConfig] = None, make_default: bool = True
) -> SyncManager:
    manager = SyncManager(remote=remote, local=local, config=config)
    if make_default:
        from .connection import ConnectionRegistry

        ConnectionRegistry.set_default_sync_manager(manager)
    return manager
