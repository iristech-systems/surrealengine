"""
test_embedded_smoke.py
======================
Smoke test all SurrealEngine changes against the embedded engine (mem://).

Tests:
  1. Connection to embedded engine
  2. Document async CRUD (create/get/update/delete via save)
  3. DateTimeField & DurationField serialization
  4. VectorField + semantic_search (KNN)
  5. order_by_knn (projection-based fix)
  6. QuerySetDescriptor _sync methods (via sync connection)
  7. SyncManager metadata tables (idempotent DDL)
  8. Bulk_create_sync
"""

import asyncio
import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from surrealengine import create_connection
from surrealengine.document import Document
from surrealengine.fields import (
    StringField, IntField, VectorField,
    DateTimeField, DurationField,
)
from surrealengine.exceptions import DoesNotExist
from surrealengine.sync_manager import SyncManager, SyncConfig

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    PASS += 1
    print(f"  V {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  X {msg}")


async def main():
    # ── Create connections ───────────────────────────────────────────
    # Async connection (default for embedded)
    conn = create_connection("mem://", "test", "embedded_smoke", async_mode=True, make_default=True)
    await conn.connect()
    v = await conn.client.version()
    print(f"Embedded engine: {v}")
    print()

    # Sync connection (needed for _sync methods)
    conn_sync = create_connection("mem://", "test", "embedded_smoke_sync", async_mode=False, make_default=False)
    conn_sync.connect()
    print()

    # ── 1. Basic Document ──────────────────────────────────────────────
    print("-" * 50)
    print("1. Basic Document CRUD (async)")
    print("-" * 50)

    class User(Document):
        __schemafull__ = False
        name = StringField()
        age = IntField()

    u = User(name="Alice", age=30)
    await u.save()
    assert u.id is not None
    uid = u.id
    ok("User created via save()")

    u2 = await User.objects.using(conn).get(id=uid)
    assert u2.name == "Alice"
    ok("User.objects.get() works")

    u2.age = 31
    await u2.save()
    u3 = await User.objects.using(conn).get(id=uid)
    assert u3.age == 31
    ok("User.save() update works")

    await u2.refresh()
    assert u2.age == 31
    ok("Document.refresh() works")

    await u2.delete()
    try:
        await User.objects.using(conn).get(id=uid)
        fail("Record should have been deleted")
    except DoesNotExist:
        ok("Delete works (DoesNotExist raised)")

    # ── 2. DateTimeField & DurationField ──────────────────────────────
    print()
    print("-" * 50)
    print("2. DateTimeField & DurationField")
    print("-" * 50)

    class Event(Document):
        __schemafull__ = False
        label = StringField()
        when = DateTimeField()
        span = DurationField()

    now = datetime.datetime.now(datetime.timezone.utc)
    e = Event(label="test", when=now, span=datetime.timedelta(hours=2))
    await e.save()
    ok("Event created with DateTimeField and DurationField")

    e2 = await Event.objects.using(conn).get(id=e.id)
    assert isinstance(e2.when, datetime.datetime), f"Expected datetime, got {type(e2.when)}"
    assert isinstance(e2.span, datetime.timedelta), f"Expected timedelta, got {type(e2.span)}"
    ok("DateTimeField/DurationField roundtrip preserves types")

    # ── 3. VectorField + semantic_search ───────────────────────────────
    print()
    print("-" * 50)
    print("3. VectorField + semantic_search")
    print("-" * 50)

    class Item(Document):
        __schemafull__ = False
        name = StringField()
        embedding = VectorField(dimension=4, dtype="F32")

    items_data = [
        ("apple", [1.0, 0.0, 0.0, 0.0]),
        ("banana", [0.0, 1.0, 0.0, 0.0]),
        ("cherry", [0.0, 0.0, 1.0, 0.0]),
        ("date", [0.9, 0.1, 0.0, 0.0]),
    ]
    for name, vec in items_data:
        await Item(name=name, embedding=vec).save()
    ok("4 vector items created")

    results = await (
        Item.objects.using(conn)
        .semantic_search("embedding", [1.0, 0.0, 0.0, 0.0], k=2, metric="COSINE")
        .all()
    )
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    ok("semantic_search returns correct number of results")

    # ── 4. order_by_knn ────────────────────────────────────────────────
    print()
    print("-" * 50)
    print("4. order_by_knn")
    print("-" * 50)

    results2 = await (
        Item.objects.using(conn)
        .order_by_knn("embedding", [1.0, 0.0, 0.0, 0.0], k=3)
        .all()
    )
    assert len(results2) == 3, f"Expected 3 results, got {len(results2)}"
    assert results2[0].name == "apple", f"Expected apple first, got {results2[0].name}"
    ok("order_by_knn returns correct sorted results")

    # ── 5. Sync methods (via sync connection) ───────────────────────────
    print()
    print("-" * 50)
    print("5. QuerySetDescriptor _sync methods")
    print("-" * 50)

    # Create data via sync connection (separate mem:// db)
    Item(name="sync_apple", embedding=[1.0, 0.0, 0.0, 0.0]).save_sync(conn_sync)
    Item(name="sync_banana", embedding=[0.0, 1.0, 0.0, 0.0]).save_sync(conn_sync)
    Item(name="sync_cherry", embedding=[0.0, 0.0, 1.0, 0.0]).save_sync(conn_sync)
    Item(name="sync_date", embedding=[0.9, 0.1, 0.0, 0.0]).save_sync(conn_sync)

    User(name="Bob", age=25).save_sync(conn_sync)

    def q():
        return Item.objects.using(conn_sync)

    # all_sync on QuerySet
    all_items = q().all_sync()
    assert len(all_items) == 4
    ok("all_sync works")

    # get_sync on QuerySet
    u2_s = User.objects.using(conn_sync).get_sync(name="Bob")
    assert u2_s.name == "Bob"
    ok("get_sync works")

    # count_sync on QuerySet
    count = q().count_sync()
    assert count > 0
    ok("count_sync works")

    # Config methods are non-sync (no I/O), use with all_sync for execution
    limited = q().limit(2).all_sync()
    assert len(limited) == 2
    ok("limit + all_sync works")

    ordered = q().order_by("name").all_sync()
    ok("order_by + all_sync works")

    started = q().start(1).all_sync()
    ok("start + all_sync works")

    grouped = q().group_by("name").all_sync()
    ok("group_by + all_sync works")

    splitted = q().split("name").all_sync()
    ok("split + all_sync works")

    fetched = q().fetch("nonexistent").all_sync()
    ok("fetch + all_sync works")

    q().with_index("nonexistent").all_sync()
    ok("with_index + all_sync works")
    q().no_index().all_sync()
    ok("no_index + all_sync works")

    # upsert_sync on QuerySet
    result = q().upsert_sync(id="sync_item", name="sync_item", embedding=[0.1, 0.2, 0.3, 0.4])
    ok("upsert_sync works")

    # bulk_create_sync on QuerySet
    extra = [
        Item(name="bulk1", embedding=[0.5, 0.6, 0.7, 0.8]),
        Item(name="bulk2", embedding=[0.9, 1.0, 1.1, 1.2]),
    ]
    created = q().bulk_create_sync(extra)
    assert len(created) == 2
    ok("bulk_create_sync works")

    # order_by_knn (clones internally) + all_sync
    knn = q().order_by_knn("embedding", [1.0, 0.0, 0.0, 0.0], k=2).all_sync()
    assert len(knn) == 2
    ok("order_by_knn + all_sync works")

    # delete_sync on QuerySet
    deleted = q().filter(name="sync_item").delete_sync()
    assert deleted >= 1
    ok("delete_sync works")

    # update_sync on QuerySet
    updated = q().filter(name="Bob").update_sync(name="Bob Updated")
    ok("update_sync works")

    User.objects.using(conn_sync).filter(name="Bob Updated").delete_sync()

    # ── 6. Save_sync / Refresh_sync on Document ─────────────────────────
    print()
    print("-" * 50)
    print("6. Document save_sync / refresh_sync")
    print("-" * 50)

    doc = User(name="Charlie", age=40)
    doc.save_sync(conn_sync)
    assert doc.id is not None
    ok("save_sync works")

    doc.name = "Charlie Updated"
    doc.save_sync(conn_sync)
    cid = doc.id
    doc2 = User.objects.using(conn_sync).get_sync(id=cid)
    assert doc2.name == "Charlie Updated"
    ok("save_sync update works")

    doc2.refresh_sync(conn_sync)
    assert doc2.name == "Charlie Updated"
    ok("refresh_sync works")

    # ── 7. SyncManager metadata tables ──────────────────────────────────
    print()
    print("-" * 50)
    print("7. SyncManager metadata tables (idempotent DDL)")
    print("-" * 50)

    sm = SyncManager(remote=conn, local=conn_sync)
    try:
        await sm.ensure_metadata_tables()
        ok("ensure_metadata_tables works")
        await sm.ensure_metadata_tables()
        ok("ensure_metadata_tables is idempotent")
    except Exception as e:
        fail(f"ensure_metadata_tables failed: {e}")

    # ── Summary ────────────────────────────────────────────────────────
    print()
    print("=" * 50)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
