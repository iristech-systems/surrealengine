"""
Async connection pool pruning test (requires SurrealDB running locally).
Run:
SURREAL_URL=ws://db:8000/rpc uv run python example_scripts/test_pool_pruning.py
"""
import asyncio
import os
from surrealengine.connection import create_connection

DB_URL = os.environ.get("SURREAL_URL", "ws://db:8000/rpc")
NS = os.environ.get("SURREAL_NS", "test")
DB = os.environ.get("SURREAL_DB", "test")
USER = os.environ.get("SURREAL_USER", "root")
PASS = os.environ.get("SURREAL_PASS", "root")

async def main():
    conn = create_connection(
        url=DB_URL,
        namespace=NS,
        database=DB,
        username=USER,
        password=PASS,
        async_mode=True,
        use_pool=True,
        pool_size=2,
        max_idle_time=1,
        health_check_interval=1,
    )
    await conn.connect()
    # Borrow and return a couple times to create pool entries
    for _ in range(3):
        await conn.client.query("SELECT 1;")
    # Let idle time elapse
    await asyncio.sleep(2)
    # Trigger health prune
    await conn.client.query("SELECT 1;")
    pool = conn.pool
    if pool:
        print("pool size (available)", len(pool.pool))
        print("created_connections", pool.created_connections, "discarded_connections", pool.discarded_connections)
    await conn.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
