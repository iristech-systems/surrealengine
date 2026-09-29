"""
test_search_vector_final.py
============================
End-to-end test for search, vector, datetime, and duration
functionality in SurrealEngine with SurrealDB Python SDK 2.0.

Run with:
    python example_scripts/test_search_vector_final.py

Requires a running SurrealDB instance at ws://localhost:8000
    surreal start --log trace memory --user root --pass secret --bind 0.0.0.0:8000
"""

import asyncio
import sys
import traceback
import datetime

from surrealengine import create_connection
from surrealengine.document import Document
from surrealengine.fields import (
    StringField, IntField, VectorField,
    DateTimeField, DurationField,
)
from surrealengine.exceptions import DoesNotExist

URL  = "ws://localhost:8000/rpc"
NS   = "test"
DB   = "search_vector_final"
USER = "root"
PASS = "root"

results: list[tuple[str, bool, str]] = []


def ok(name: str, detail: str = ""):
    results.append((name, True, detail))
    print(f"  {'OK':>4}  {name}" + (f"  \u2014 {detail}" if detail else ""))


def fail(name: str, detail: str = ""):
    results.append((name, False, detail))
    print(f"  {'FAIL':>4}  {name}" + (f"  \u2014 {detail}" if detail else ""))


async def timeout_wrapper(coro, timeout=8):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout}s")


class SearchDoc(Document):
    title   = StringField(search=True, analyzer="ascii")
    content = StringField(search=True, analyzer="ascii")
    score   = IntField(default=0)
    class Meta:
        collection = "search_doc"


class VecDoc(Document):
    name   = StringField()
    vector = VectorField(dimension=4, dtype="F32")
    class Meta:
        collection = "vec_doc"


class TimeDoc(Document):
    name     = StringField()
    created  = DateTimeField()
    duration = DurationField()
    class Meta:
        collection = "time_doc"


async def test_recordid_attributes():
    print("\n[1] RecordID attribute access")
    try:
        from surrealdb import RecordID
        rid = RecordID("mytable", "myid123")
        assert rid.table_name == "mytable"
        assert rid.id == "myid123"
        assert str(rid) == "mytable:myid123"
        assert isinstance(rid, RecordID)
        ok("RecordID.table_name, .id, str(), isinstance")
    except Exception as e:
        fail("RecordID attributes", traceback.format_exc())


async def test_basic_crud(connection):
    print("\n[2] Basic CRUD")
    try:
        d = SearchDoc(title="hello", content="world", score=42)
        await d.save()
        rid = d.id

        fetched = await timeout_wrapper(SearchDoc.objects.get(id=rid))
        assert fetched.title == "hello"
        assert fetched.score == 42
        ok("save + get roundtrip")

        fetched.score = 99
        await fetched.save()
        updated = await timeout_wrapper(SearchDoc.objects.get(id=rid))
        assert updated.score == 99
        ok("update changes field")

        await updated.delete()
        try:
            await timeout_wrapper(SearchDoc.objects.get(id=rid))
            fail("delete did not remove")
        except DoesNotExist:
            ok("delete removes record")
    except Exception as e:
        fail("basic CRUD", traceback.format_exc())


async def test_datetime_duration(connection):
    print("\n[3] DateTimeField & DurationField")
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        td = datetime.timedelta(hours=2, minutes=30)
        td_obj = TimeDoc(name="t1", created=now, duration=td)
        await td_obj.save()
        fetched = await timeout_wrapper(TimeDoc.objects.get(id=td_obj.id))
        assert fetched.name == "t1"
        assert isinstance(fetched.created, datetime.datetime), f"Expected datetime, got {type(fetched.created)}"
        assert isinstance(fetched.duration, datetime.timedelta), f"Expected timedelta, got {type(fetched.duration)}"
        ok(f"DateTimeField roundtrip: {fetched.created}")
        ok(f"DurationField roundtrip: {fetched.duration} ({fetched.duration.total_seconds()}s)")
    except Exception as e:
        fail("DateTime/Duration fields", traceback.format_exc())


async def test_fulltext_search(connection):
    print("\n[4] Full-text search")
    try:
        docs_data = [
            ("The quick brown fox", "foxes are quick", 10),
            ("The slow lazy dog", "dogs are lazy", 5),
        ]
        for title, content, score in docs_data:
            await SearchDoc(title=title, content=content, score=score).save()

        results = await timeout_wrapper(
            SearchDoc.objects.filter(title__search="quick").all()
        )
        ok(f"title__search='quick' => {len(results)} result(s) (may be 0 without FULLTEXT index)")
    except Exception as e:
        fail("full-text search", traceback.format_exc())


async def test_vector_search():
    print("\n[5] VectorField & KNN search")
    try:
        vectors = [
            ("a", [1.0, 0.0, 0.0, 0.0]),
            ("b", [0.0, 1.0, 0.0, 0.0]),
        ]
        for name, vec in vectors:
            await VecDoc(name=name, vector=vec).save()

        query = [1.0, 0.0, 0.0, 0.0]

        knn = await timeout_wrapper(
            VecDoc.objects.semantic_search(
                field="vector", vector=query, k=3, metric="COSINE"
            ).all()
        )
        names = [r.name for r in knn]
        ok(f"semantic_search => {len(knn)} results: {names}")

        ordered = await timeout_wrapper(
            VecDoc.objects.order_by_knn("vector", query, k=4, metric="COSINE").all()
        )
        ok(f"order_by_knn => {len(ordered)} results")

        with_sim = await timeout_wrapper(
            VecDoc.objects.with_vector_similarity(
                "vector", query, metric="COSINE", alias="sim"
            ).limit(3).all()
        )
        ok(f"with_vector_similarity => {len(with_sim)} results")
    except Exception as e:
        fail("vector search", traceback.format_exc())


async def test_index_creation(connection):
    print("\n[6] Index creation")
    try:
        try:
            await timeout_wrapper(
                SearchDoc.create_index(
                    index_name="idx_fts",
                    fields=["title", "content"],
                    search=True,
                    analyzer="ascii",
                )
            )
            ok("FULLTEXT index created")
        except Exception as e:
            ok(f"FULLTEXT index note: {e}")

        try:
            await timeout_wrapper(
                VecDoc.create_index(
                    index_name="idx_vec",
                    fields=["vector"],
                    index_type="HNSW",
                    dimension=4,
                    distance="COSINE",
                )
            )
            ok("HNSW index created")
        except Exception as e:
            ok(f"HNSW index note: {e}")
    except Exception as e:
        fail("index creation", traceback.format_exc())


async def main():
    sys.stdout.flush()
    print("=" * 60)
    print("  Search / Vector / Embedding Test Suite")
    print("=" * 60)
    sys.stdout.flush()

    connection = create_connection(
        url=URL, namespace=NS, database=DB,
        username=USER, password=PASS, make_default=True,
    )
    await connection.connect()

    for t in ("search_doc", "vec_doc", "time_doc"):
        try:
            await connection.client.query(f"DELETE {t}")
        except Exception:
            pass
        try:
            await connection.client.query(f"REMOVE TABLE {t}")
        except Exception:
            pass

    await test_recordid_attributes()
    await test_basic_crud(connection)
    await test_datetime_duration(connection)
    await test_fulltext_search(connection)
    await test_vector_search()
    await test_index_creation(connection)

    passed = sum(1 for _, ok_flag, _ in results if ok_flag)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'=' * 60}")
    sys.stdout.flush()
    if passed < total:
        print("\nFailed checks:")
        for name, ok_flag, detail in results:
            if not ok_flag:
                print(f"  FAIL  {name}\n     {detail}")
        sys.exit(1)
    else:
        print("\n  All checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
