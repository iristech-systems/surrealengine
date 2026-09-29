"""Tests for DateTimeField auto_now_add / auto_now support.

Run:  uv run python example_scripts/test_auto_datetime.py

Covers:
  1. auto_now_add stamps on create only
  2. auto_now stamps on every save (create + update)
  3. Unchanged saves still bump auto_now
  4. Explicit constructor values are overwritten by the flags
  5. Sync parity for all of the above
  6. RelationDocument edges stamp via the relate() path
  7. TimestampMixin regression (delegates to field flags)
"""

import asyncio
import sys
import time

from surrealengine import Document, RelationDocument, StringField, create_connection
from surrealengine.fields import DateTimeField
from surrealengine.mixins import TimestampMixin

PASS = 0
FAIL = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  V {name}")


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    print(f"  X {name}  -- {detail}")


def check(name, cond, detail=""):
    if cond:
        ok(name)
    else:
        fail(name, detail)


class Note(Document):
    title = StringField()
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        collection = "auto_notes"


class SyncNote(Document):
    title = StringField()
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        collection = "auto_notes_sync"


class TaggedNote(Document):
    title = StringField(required=True)
    tagged_at = DateTimeField(auto_now_add=True)

    class Meta:
        collection = "tagged_notes"


class TagEdge(RelationDocument):
    """Edge: Note -> Note with an auto_now_add field."""
    label = StringField()
    tagged_at = DateTimeField(auto_now_add=True)

    class Meta:
        collection = "tag_edges"


class Audited(TimestampMixin):
    name = StringField()

    class Meta:
        collection = "audited_docs"


def approx(a, b, seconds=5):
    return a is not None and b is not None and abs((a - b).total_seconds()) < seconds


async def main():
    conn = create_connection(url="mem://", namespace="test", database="autodt")
    await conn.connect()
    conn_sync = create_connection(url="mem://", namespace="test", database="autodt", async_mode=False)
    conn_sync.connect()

    await Note.create_table(schemafull=False)
    await SyncNote.create_table(schemafull=False)
    await TaggedNote.create_table(schemafull=False)
    await TagEdge.create_table(schemafull=False)
    await Audited.create_table(schemafull=False)

    # ── 1/2/3. Async: create stamps both; update bumps auto_now only ──
    print("\n-- async create / update / no-op save --")
    before = time.time()
    n = Note(title="v1")
    await n.save()
    c1, u1 = n.created_at, n.updated_at
    check("created stamped on create", approx(c1, __import__("datetime").datetime.now(__import__("datetime").timezone.utc)), f"{c1}")
    check("updated stamped on create", approx(u1, __import__("datetime").datetime.now(__import__("datetime").timezone.utc)), f"{u1}")

    await asyncio.sleep(1.1)
    n.title = "v2"
    await n.save()
    c2, u2 = n.created_at, n.updated_at
    check("auto_now_add frozen on update", c2 == c1, f"{c1} -> {c2}")
    check("auto_now bumped on update", u2 > u1, f"{u1} -> {u2}")

    reloaded = await Note.objects.get(id=n.id)
    check("persisted created_at matches", reloaded.created_at == c2, f"{reloaded.created_at} != {c2}")
    check("persisted updated_at matches", reloaded.updated_at == u2, f"{reloaded.updated_at} != {u2}")

    await asyncio.sleep(1.1)
    await reloaded.save()  # no changes at all
    check("no-change save bumps auto_now", reloaded.updated_at > u2, f"{u2} -> {reloaded.updated_at}")
    _ = before

    # ── 4. Explicit value overwritten by flag ──
    print("\n-- explicit value overridden by flags --")
    import datetime as dt
    old = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
    n2 = Note(title="explicit", created_at=old, updated_at=old)
    await n2.save()
    check("auto_now_add overwrites explicit", n2.created_at != old, f"{n2.created_at}")
    check("auto_now overwrites explicit", n2.updated_at != old, f"{n2.updated_at}")

    # ── 5. Sync parity ──
    print("\n-- sync create / update / no-op save --")
    s = SyncNote(title="s1")
    s.save_sync()
    sc1, su1 = s.created_at, s.updated_at
    check("sync create stamps created", approx(sc1, dt.datetime.now(dt.timezone.utc)), f"{sc1}")
    check("sync create stamps updated", approx(su1, dt.datetime.now(dt.timezone.utc)), f"{su1}")

    time.sleep(1.1)
    s.title = "s2"
    s.save_sync()
    check("sync auto_now_add frozen", s.created_at == sc1, f"{sc1} -> {s.created_at}")
    check("sync auto_now bumped", s.updated_at > su1, f"{su1} -> {s.updated_at}")

    sr = SyncNote.objects.get_sync(id=s.id)
    time.sleep(1.1)
    sr.save_sync()
    check("sync no-change save bumps auto_now", sr.updated_at > s.updated_at,
          f"{s.updated_at} -> {sr.updated_at}")

    # ── 6. RelationDocument edge via relate() ──
    print("\n-- relation edge stamping --")
    a = await Note.objects.create(title="edge-a")
    b = await Note.objects.create(title="edge-b")
    edge = TagEdge(in_document=a, out_document=b, label="rel")
    await edge.save()
    check("edge auto_now_add stamped on relate",
          approx(edge.tagged_at, dt.datetime.now(dt.timezone.utc)), f"{edge.tagged_at}")
    e_loaded = (await TagEdge.objects.all())[0]
    check("edge persisted tag matches", e_loaded.tagged_at == edge.tagged_at,
          f"{e_loaded.tagged_at} != {edge.tagged_at}")

    # ── 7. TimestampMixin regression ──
    print("\n-- TimestampMixin delegation --")
    aud = Audited(name="first")
    await aud.save()
    check("mixin created_at stamped", aud.created_at is not None, f"{aud.created_at}")
    check("mixin updated_at stamped", aud.updated_at is not None, f"{aud.updated_at}")
    ac, au = aud.created_at, aud.updated_at
    await asyncio.sleep(1.1)
    aud.name = "second"
    await aud.save()
    check("mixin created frozen", aud.created_at == ac, f"{ac} -> {aud.created_at}")
    check("mixin updated bumped", aud.updated_at > au, f"{au} -> {aud.updated_at}")
    aud_s = Audited(name="sync-first")
    aud_s.save_sync()
    check("mixin sync stamps work", aud_s.created_at is not None and aud_s.updated_at is not None)

    print("\n" + "=" * 50)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
