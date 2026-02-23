"""
test_live_queries.py
====================
End-to-end test script for SurrealEngine live query features.

Tests:
  1. Document.objects.live()            – basic CREATE/UPDATE/DELETE stream
  2. action= filter                     – only CREATE events pass through
  3. start_live() + subscribe_to_live() – fan-out: two independent consumers
  4. where= predicate filter            – only matching records yielded

Requires a running SurrealDB instance accessible at ws://localhost:8000
(standard local dev setup).

Run with:
    python example_scripts/test_live_queries.py
"""

import asyncio
import sys
import traceback

# ── connection ────────────────────────────────────────────────────────────────
from surrealengine import create_connection
from surrealengine.document import Document
from surrealengine.fields import StringField, IntField
from surrealengine.query.base import QuerySet

URL  = "ws://localhost:8000"
NS   = "test"
DB   = "live_test"
USER = "root"
PASS = "secret"


PASS_ICON = "✓"
FAIL_ICON = "✗"

results: list[tuple[str, bool, str]] = []

def ok(name: str, detail: str = ""):
    results.append((name, True, detail))
    print(f"  {PASS_ICON}  {name}" + (f"  — {detail}" if detail else ""))

def fail(name: str, detail: str = ""):
    results.append((name, False, detail))
    print(f"  {FAIL_ICON}  {name}" + (f"  — {detail}" if detail else ""))


# ── model ─────────────────────────────────────────────────────────────────────
class Metric(Document):
    name  = StringField(required=True)
    value = IntField(default=0)

    class Meta:
        collection = "metric"


# ── helper ────────────────────────────────────────────────────────────────────
async def drain(agen, n: int, timeout: float = 5.0) -> list:
    """Collect up to *n* events from an async generator within *timeout* seconds."""
    collected = []
    async def _collect():
        async for evt in agen:
            collected.append(evt)
            if len(collected) >= n:
                break
    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    return collected


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 – basic live() stream: CREATE + UPDATE + DELETE
# ══════════════════════════════════════════════════════════════════════════════
async def test_basic_live(connection):
    print("\n[1] Basic live() — CREATE / UPDATE / DELETE")
    try:
        gen = Metric.objects.live()
        events = []

        async def collect_3():
            async for evt in gen:
                events.append(evt)
                if len(events) >= 3:
                    break

        collect_task = asyncio.create_task(collect_3())
        await asyncio.sleep(0.3)          # give subscription time to register

        # Drive 3 mutations
        m = Metric(name="cpu", value=10)
        await m.save()
        m.value = 20
        await m.save()
        await m.delete()

        try:
            await asyncio.wait_for(collect_task, timeout=6)
        except asyncio.TimeoutError:
            collect_task.cancel()

        if len(events) == 3:
            ok("Received all 3 events (CREATE + UPDATE + DELETE)")
        else:
            fail(f"Expected 3 events, got {len(events)}")

        actions = [e.action for e in events]
        if "CREATE" in actions:
            ok("CREATE event present")
        else:
            fail("CREATE event missing", f"got {actions}")

        if "UPDATE" in actions:
            ok("UPDATE event present")
        else:
            fail("UPDATE event missing", f"got {actions}")

        if "DELETE" in actions:
            ok("DELETE event present")
        else:
            fail("DELETE event missing", f"got {actions}")

        # Check LiveEvent attributes
        create_evt = next((e for e in events if e.action == "CREATE"), None)
        if create_evt:
            if create_evt.data and "name" in create_evt.data:
                ok("CREATE event data contains 'name' field", f"name={create_evt.data['name']}")
            else:
                fail("CREATE event data missing 'name'", str(create_evt.data))
            if create_evt.id is not None:
                ok("CREATE event has RecordID", str(create_evt.id))
            else:
                fail("CREATE event missing RecordID")

    except NotImplementedError as e:
        fail("live() raised NotImplementedError (WS connection required)", str(e))
    except Exception:
        fail("test_basic_live crashed", traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 – action= filter: only CREATE events
# ══════════════════════════════════════════════════════════════════════════════
async def test_action_filter(connection):
    print("\n[2] live(action='CREATE') — update + delete must not appear")
    try:
        gen = Metric.objects.live(action="CREATE")
        events = []

        async def collect_1():
            async for evt in gen:
                events.append(evt)
                if len(events) >= 1:
                    break

        collect_task = asyncio.create_task(collect_1())
        await asyncio.sleep(0.3)

        m = Metric(name="mem", value=50)
        await m.save()
        m.value = 60
        await m.save()          # UPDATE — should be filtered
        await m.delete()        # DELETE — should be filtered

        try:
            await asyncio.wait_for(collect_task, timeout=5)
        except asyncio.TimeoutError:
            collect_task.cancel()

        if len(events) == 1 and events[0].action == "CREATE":
            ok("Received exactly 1 CREATE, UPDATE+DELETE filtered out")
        elif len(events) == 0:
            fail("Got 0 events — CREATE was filtered too (unexpected)")
        else:
            actions = [e.action for e in events]
            if all(a == "CREATE" for a in actions):
                ok(f"All {len(events)} received events are CREATE")
            else:
                fail(f"Non-CREATE events slipped through: {actions}")

    except NotImplementedError as e:
        fail("live(action=) raised NotImplementedError", str(e))
    except Exception:
        fail("test_action_filter crashed", traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 – fan-out: start_live() + two independent subscribe_to_live() consumers
# ══════════════════════════════════════════════════════════════════════════════
async def test_fanout(connection):
    print("\n[3] start_live() + subscribe_to_live() fan-out")
    try:
        uuid = await Metric.objects.start_live(connection=connection)
        if not uuid:
            fail("start_live() returned empty UUID")
            return
        ok("start_live() returned UUID", uuid)

        events_a: list = []
        events_b: list = []

        async def consumer_a():
            async for evt in Metric.objects.subscribe_to_live(uuid, connection=connection):
                events_a.append(evt)
                if len(events_a) >= 2:
                    break

        async def consumer_b():
            async for evt in Metric.objects.subscribe_to_live(uuid, connection=connection):
                events_b.append(evt)
                if len(events_b) >= 2:
                    break

        task_a = asyncio.create_task(consumer_a())
        task_b = asyncio.create_task(consumer_b())
        await asyncio.sleep(0.3)

        m = Metric(name="disk", value=80)
        await m.save(connection=connection)
        m.value = 90
        await m.save(connection=connection)

        try:
            await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=6)
        except asyncio.TimeoutError:
            task_a.cancel(); task_b.cancel()

        if len(events_a) >= 1:
            ok(f"Consumer A received {len(events_a)} event(s)")
        else:
            fail("Consumer A received 0 events")

        if len(events_b) >= 1:
            ok(f"Consumer B received {len(events_b)} event(s)")
        else:
            fail("Consumer B received 0 events")

        if len(events_a) >= 1 and len(events_b) >= 1:
            ok("Both consumers independently received events (fan-out confirmed)")

    except NotImplementedError as e:
        fail("start_live() / subscribe_to_live() raised NotImplementedError", str(e))
    except Exception:
        fail("test_fanout crashed", traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 – where= predicate: only value > 100 passes
# ══════════════════════════════════════════════════════════════════════════════
async def test_where_filter(connection):
    print("\n[4] live(where=dict) — exact-match filter: only name='net_high' passes")
    try:
        # Use explicit QuerySet with the known WS connection so live() doesn't
        # pick up a cloned connection from the registry that lacks live_queues.
        qs = QuerySet(Metric, connection)
        gen = qs.live(where={"name": "net_high"})

        events = []

        async def collect():
            async for evt in gen:
                events.append(evt)
                if len(events) >= 1:
                    break

        collect_task = asyncio.create_task(collect())
        await asyncio.sleep(0.3)

        # This should NOT pass the filter
        m_low = Metric(name="net_low", value=5)
        await m_low.save(connection=connection)
        await asyncio.sleep(0.4)   # give it time to arrive and be rejected

        # This SHOULD pass the filter
        m_high = Metric(name="net_high", value=200)
        await m_high.save(connection=connection)

        try:
            await asyncio.wait_for(collect_task, timeout=5)
        except asyncio.TimeoutError:
            collect_task.cancel()

        if len(events) == 1:
            name = events[0].data.get('name') if isinstance(events[0].data, dict) else None
            if name == 'net_high':
                ok("where= filter works: net_low filtered out, net_high received")
            else:
                fail(f"Unexpected event with name={name}")
        elif len(events) == 0:
            fail("Got 0 events — net_high also filtered (unexpected)")
        else:
            names = [e.data.get('name') if isinstance(e.data, dict) else '?' for e in events]
            if all(n == 'net_high' for n in names):
                ok(f"All {len(events)} received events matched filter (name=net_high)")
            else:
                fail(f"Got {len(events)} events (expected 1): names={names}")

    except NotImplementedError as e:
        fail("live(where=) raised NotImplementedError", str(e))
    except Exception:
        fail("test_where_filter crashed", traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    print("=" * 60)
    print("  SurrealEngine Live Query Test Suite")
    print("=" * 60)
    print(f"  Connecting to {URL}  ns={NS}  db={DB}")

    connection = create_connection(
        url=URL,
        namespace=NS,
        database=DB,
        username=USER,
        password=PASS,
        make_default=True,
    )
    await connection.connect()

    # Register schema and wipe any leftover data
    await Metric.create_table()
    await connection.client.query("DELETE metric")

    await test_basic_live(connection)
    await test_action_filter(connection)
    await test_fanout(connection)
    await test_where_filter(connection)

    # ── summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print(f"\n{'=' * 60}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'=' * 60}")

    if passed < total:
        print("\nFailed checks:")
        for name, ok_flag, detail in results:
            if not ok_flag:
                print(f"  {FAIL_ICON}  {name}" + (f"\n     {detail}" if detail else ""))
        sys.exit(1)
    else:
        print("\n  All live query checks passed! 🎉")

if __name__ == "__main__":
    asyncio.run(main())
