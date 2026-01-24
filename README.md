
# SurrealEngine

# SurrealEngine

**The Python ORM & Real-Time Data Platform**

> **Vector Search, Graph Queries, Live Updates, and Zero-Copy Analytics — All in One.**

SurrealEngine is the comprehensive Python ORM for SurrealDB that evolves into a real-time data platform. It gives you the familiar object mapping you expect, plus capabilities that were previously impossible without complex distributed systems.

Whether you're building a **Real-Time Recommendation Engine**, an **AI-Powered Search Service**, or a **High-Frequency Data Pipeline**, SurrealEngine provides the unified API you need.

[![Documentation](https://img.shields.io/badge/docs-visualized-blue.svg)](https://iristech-systems.github.io/SurrealEngine-Docs/)
[![PyPI](https://img.shields.io/pypi/v/surrealengine.svg)](https://pypi.org/project/surrealengine/)
[![License](https://img.shields.io/github/license/iristech-systems/surrealengine.svg)](https://github.com/iristech-systems/surrealengine/blob/main/LICENSE)

---

## 🚀 The "Magic" Example

Why choose SurrealEngine? Because you can do **this** in a single query:

```python
# Real-time Vector Search + Graph Traversal
# Find users with similar interests (Vector), who are friends of friends (Graph),
# AND subscribe to real-time updates as they happen (Live Query).

similar_users = await User.objects \
    .filter(embedding__knn=(user_vector, 10)) \
    .out("friends") \
    .out(Person) \
    .live()

async for change in similar_users:
    print(f"New friend match found: {change.data['name']} (Score: {change.data['similarity']})")
```

---

## 📚 Documentation

**Full documentation is available at [https://iristech-systems.github.io/SurrealEngine-Docs/](https://iristech-systems.github.io/SurrealEngine-Docs/)**

👉 **Read the [State of SurrealEngine](https://github.com/iristech-systems/surrealengine/discussions/4) announcement!**

---

## ✨ Features



| Feature | Status | Notes |
|---------|--------|-------|
| **Polyglot API** | ✅ Supported | (New in v0.7.0) Write code once, run in both **Sync** (WSGI/Scripts) and **Async** (ASGI/FastAPI) contexts naturally. |
| **Aggregations** | ✅ Supported | MongoDB-style aggregation pipelines (`.aggregate().group(...).execute()`) for complex analytics. |
| **Materialized Views** | ✅ Supported | Define pre-computed views using `Document.create_materialized_view()` for high-performance analytics. |
| **Connection Pooling** | ✅ Supported | Full support for async pooling (auto-reconnect, health checks). Sync pooling available via `Queue`. |
| **Live Queries** | ⚠️ Partial | Supported on **WebSocket** connections (`ws://`, `wss://`). **NOT** supported on embedded (`mem://`, `file://`). |
| **Graph Traversal** | ✅ Supported | Fluent API with chaining (`.out("edge").out(Node)` -> `->edge->node`). Improved in v0.7.0 for deep traversals. |
| **Change Tracking** | ✅ Supported | Objects track dirty fields (`.is_dirty`, `.get_changes()`) to optimize UPDATE queries. |
| **Schema Generation** | ✅ Supported | Can generate `DEFINE TABLE/FIELD` statements from Python classes. |
| **Vector Search** | ✅ Supported | Support for HNSW indexes via `Meta.indexes` (dimension, dist, etc.). |
| **Full Text Search** | ✅ Supported | Support for BM25 and Highlights via `Meta.indexes`. |
| **Events** | ✅ Supported | Define triggers via `Meta.events` using the `Event` class. |
| **Data Science** | ✅ Supported | Zero-copy export to PyArrow (`.to_arrow()`) and Polars (`.to_polars()`). Requires `pip install surrealengine[data]`. |
| **Pydantic** | ✅ Compatible | `RecordID` objects (SDK v1.0.8+) are Pydantic-compatible. |

---

## 📦 Installation

We strongly recommend using `uv` for 10-100x faster package installation and resolution but `pip` and `poetry` work too.

### Using uv (Recommended)
```bash
uv add surrealengine
# Optional extras:
# uv add "surrealengine[signals]"  # For pre/post save hooks
# uv add "surrealengine[data]"     # For PyArrow/Polars support
# uv add "surrealengine[jupyter]"  # For Jupyter Notebook support
```

### Using pip
```bash
pip install surrealengine
# Optional: pip install "surrealengine[signals, data]"
```

---

## ⚡ Quick Start

### 1. Connect (Sync or Async)
SurrealEngine auto-detects your context. Use `async_mode=True` for async apps (FastAPI), or defaults to sync for scripts.

```python
from surrealengine import create_connection

# Async connection (e.g. FastAPI)
await create_connection(
    url="ws://localhost:8000/rpc",
    namespace="test", database="test",
    username="root", password="root",
    async_mode=True
).connect()

# OR Sync connection (e.g. Scripts)
create_connection(
    url="ws://localhost:8000/rpc",
    namespace="test", database="test",
    username="root", password="root",
    async_mode=False
)
```

### 2. Define Your Model
```python
from surrealengine import Document, StringField, IntField

class Person(Document):
    name = StringField(required=True)
    age = IntField()

    class Meta:
        collection = "person"
        indexes = [
            # HNSW Vector Index
            {"name": "idx_vector", "fields": ["embedding"], "dimension": 1536, "dist": "COSINE", "m": 16},
        ]
```

### 3. Polyglot Usage (Same API!)
```python
# Create
# In async function: await Person(name="Jane", age=30).save()
# In sync script:    Person(name="Jane", age=30).save()
jane = await Person(name="Jane", age=30).save()

# Query with Pythonic Syntax (Overloaded Operators)
# Or use Django-style: Person.objects.filter(age__gt=25)
people = await Person.objects.filter(Person.age > 25).all()

# Graph Relations & Traversal
await jane.relate_to("knows", other_person)

# Traversal - Two Ways:

# 1. Edge Only (Lazy/Dict Result) -> returns list of dicts {out: ..., in: ...}
# Equivalent to: SELECT ->knows->? FROM person:jane
relations = await Person.objects.filter(id=jane.id).out("knows").all()

# 2. Edge + Node (Hydrated Documents) -> returns list of Person objects
# Equivalent to: SELECT ->knows->person.* FROM person:jane
friends = await Person.objects.filter(id=jane.id).out("knows").out(Person).all()

# Chain traversals freely:
# Friends of friends (Hydrated)
fof = await Person.objects.filter(id=jane.id).out("knows").out("knows").out(Person).all()
```

### 4. Advanced Performance
```python
# Zero-Copy Data Export (10-50x faster)
# Export directly to Arrow/Polars without Python object overhead
df = await Person.objects.all().to_polars()
arrow_table = await Person.objects.all().to_arrow()

# Advanced Aggregation Pipeline
# "Find high-revenue categories with VIP activity"
from surrealengine import Sum, Mean, CountIf, DistinctCount

stats = await Transaction.objects.aggregate() \
    .match(status="success", created_at__gt="2024-01-01") \
    .group(
        by_fields=["category", "region"],
        total_revenue=Sum("amount"),
        avg_ticket=Mean("amount"),
        vip_transactions=CountIf("amount > 1000"),
        unique_customers=DistinctCount("user_id")
    ) \
    .having(total_revenue__gt=50000, vip_transactions__gte=10) \
    .sort(total_revenue="DESC") \
    .limit(5) \
    .execute()
```

---

## ⚠️ Sharp Edges & Limitations

SurrealEngine is designed to be a robust, high-level abstraction. However, be aware of these known limitations:

1.  **Embedded Connections & Live Queries**:
    Attempting to use `.live()` on a `mem://` or `file://` connection will raise a `NotImplementedError`. The underlying SDK's embedded connector does not currently support the event loop mechanism required for live subscriptions.

2.  **RecordID Fields**:
    The `RecordID` object from the SDK has `table_name` and `id` attributes.
    *Gotcha*: Do not assume it has a `.table` attribute (it does not). Always use `.table_name`.
    *Gotcha*: When parsing strings manually, prefer the SDK's `RecordID.parse("table:id")` over manual string splitting to handle escaped characters correctly.

3.  **Strict Mode**:
    By default, `Document` classes have `strict=True`. Initializing a document with unknown keyword arguments will raise an `AttributeError`. Set `strict=False` in `Meta` if you need to handle dynamic unstructured data.

4.  **Auto-Connect**:
    When using `create_connection(..., auto_connect=True)`, the connection is established immediately. For **async** connections, ensure this is called within a running event loop.

5.  **Transactions**:
    SurrealDB supports transactions (`BEGIN`, `COMMIT`, `CANCEL`), but `surrealengine` does not yet provide a high-level Python context manager (e.g. `async with db.transaction():`). You must manually execute these queries using `client.query()`.

---

<p align="center">
  Built with ❤️ by Iristech Systems
</p>
