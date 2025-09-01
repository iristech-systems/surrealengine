"""
Demonstrates new connection features:
- ContextVar-backed per-task default connections
- Connection pools with health checking and idle pruning
- OperationQueue backpressure policies and metrics
- Optional OpenTelemetry spans (if opentelemetry is installed)

Prerequisites:
- SurrealDB running locally: surreal start --user root --pass root
- Python deps installed (uv pip install -e .[otel] to get opentelemetry extras)

Run:
uv run python example_scripts/connection_and_observability_example.py
"""
import asyncio
import os
from surrealengine.connection import (
    create_connection,
    set_default_connection,
    get_default_connection,
    OperationQueue,
)

DB_URL = os.environ.get("SURREAL_URL", "ws://db:8000/rpc")
NS = os.environ.get("SURREAL_NS", "test")
DB = os.environ.get("SURREAL_DB", "test")
USER = os.environ.get("SURREAL_USER", "root")
PASS = os.environ.get("SURREAL_PASS", "root")

async def demo_async_contextvar_and_pool():
    print("-- async: ContextVar default + pool health check/pruning --")
    # Create an async connection that uses the pool
    conn = create_connection(
        url=DB_URL,
        namespace=NS,
        database=DB,
        username=USER,
        password=PASS,
        async_mode=True,
        use_pool=True,
        pool_size=2,
        max_idle_time=2,  # keep short to showcase pruning
        validate_on_borrow=True,
        make_default=False,
    )
    await conn.connect()

    # Set per-task default via ContextVar
    set_default_connection(conn)
    # Fetch via helper to show it resolves to ContextVar first
    resolved = get_default_connection(async_mode=True)
    assert resolved is conn
    print("Default connection resolved via ContextVar:", resolved is conn)

    # Use the dynamic schemaless API
    await conn.client.query("INFO FOR DB;")
    await conn.client.query("DEFINE TABLE ctx_demo SCHEMALESS;")
    await conn.client.query("INSERT INTO ctx_demo { name: 'alpha' };")
    rows = await conn.client.query("SELECT * FROM ctx_demo;")
    print("Rows:", rows and rows[0])

    # Let the idle pruner kick in (health thread runs every 30s in pool, but idle pruning uses max_idle_time
    # We simulate by returning connections to pool and sleeping a bit, then performing a query again.)
    await asyncio.sleep(3)
    rows = await conn.client.query("SELECT count() FROM ctx_demo;")
    print("Count after idle interval:", rows and rows[0])

    await conn.disconnect()

async def demo_operation_queue_backpressure():
    print("-- async: OperationQueue backpressure and metrics --")
    q = OperationQueue(maxsize=3, drop_policy="drop_oldest")
    q.start_reconnection()

    async def op(n):
        print("executed op", n)

    # Enqueue beyond capacity to trigger drop policy
    for i in range(6):
        q.queue_async_operation(op, args=[i])
    print("metrics after queueing:", q.metrics)

    q.end_reconnection()
    await q.execute_queued_async_operations()
    print("metrics after drain:", q.metrics)

async def maybe_demo_otel_span():
    print("-- async: Optional OpenTelemetry spans (if installed) --")
    try:
        from opentelemetry import trace as _trace  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter  # type: ignore
    except Exception:
        print("OpenTelemetry not installed; skipping OTEL demo")
        return

    _trace.set_tracer_provider(TracerProvider())
    provider = _trace.get_tracer_provider()
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    # Create a small pooled connection and run a few queries to emit spans
    conn = create_connection(
        url=DB_URL,
        namespace=NS,
        database=DB,
        username=USER,
        password=PASS,
        async_mode=True,
        use_pool=False,
    )
    await conn.connect()
    await conn.client.query("DEFINE TABLE otel_demo SCHEMALESS;")
    await conn.client.query("INSERT INTO otel_demo { name: 'span test' };")
    await conn.client.query("SELECT * FROM otel_demo;")
    await conn.disconnect()
    print("If OTEL is enabled, spans should have been printed above.")

async def main():
    await demo_async_contextvar_and_pool()
    await demo_operation_queue_backpressure()
    await maybe_demo_otel_span()

if __name__ == "__main__":
    asyncio.run(main())
