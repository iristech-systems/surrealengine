"""
OperationQueue metrics and backpressure test (no DB required).
Run:
uv run python example_scripts/test_operation_queue_metrics.py
"""
import asyncio
from surrealengine.connection import OperationQueue

async def main():
    q = OperationQueue(maxsize=3, drop_policy="drop_oldest")
    q.start_reconnection()

    async def op(n):
        # dummy
        await asyncio.sleep(0)

    for i in range(6):
        q.queue_async_operation(op, args=[i])
    # Expect 6 queued attempts, with 3 dropped under drop_oldest
    print("metrics after queue:", q.metrics)

    q.end_reconnection()
    await q.execute_queued_async_operations()
    print("metrics after drain:", q.metrics)

if __name__ == "__main__":
    asyncio.run(main())
