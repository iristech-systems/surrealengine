
# SurrealEngine

**The Ultimate Object-Document Mapper for SurrealDB**

SurrealEngine is a robust, "batteries-included" ODM designed to bring the elegance of Python to the power of SurrealDB. Built with a focus on developer ergonomics, performance, and flexibility, it bridges the gap between Python objects and SurrealDB's multi-model capabilities.

Whether you're building a high-performance async API with FastAPI or a data analysis script in a Jupyter notebook, SurrealEngine adapts to your workflow with seamless **Dual Sync/Async** support.

[![Documentation](https://img.shields.io/badge/docs-visualized-blue.svg)](https://iristech-systems.github.io/SurrealEngine-Docs/)
[![PyPI](https://img.shields.io/pypi/v/surrealengine.svg)](https://pypi.org/project/surrealengine/)
[![License](https://img.shields.io/github/license/iristech-systems/surrealengine.svg)](https://github.com/iristech-systems/surrealengine/blob/main/LICENSE)

---

## 📚 Documentation

**Full documentation is available at [https://iristech-systems.github.io/SurrealEngine-Docs/](https://iristech-systems.github.io/SurrealEngine-Docs/)**

---

## ✨ Features

- **🚀 Dual Sync/Async Core**: Write code that works everywhere. Use `await User.save()` in async apps and `User.save_sync()` in scripts.
- **🔌 Advanced Connection Pooling**: Production-ready connection management with auto-reconnect, health checks, and backpressure handling.
- **🔍 Powerful Query Builder**: Django-inspired syntax `Person.objects.filter(age__gt=25)` with support for complex logic (`Q` objects) and raw SurrealQL fallback.
- **🧠 AI-Ready Vector Search**: Native support for **HNSW Vector Indexes** and **Full-Text Search (BM25)** directly in your Python models.
- **🕸️ Graph Traversal**: traverse complex relationships effortlessly with fluid `.out()`, `.in_()`, and `.traverse()` APIs.
- **⚡ Live Queries**: Build real-time apps with Pythonic `LiveEvent` streams and event listeners.
- **🛡️ Robust Schema Management**: Define tables, fields, indexes, and events in Python and auto-migrate them to SurrealDB.
- **🐼 Data Science Integration**: Zero-copy export to **Pandas**, **Polars**, and **PyArrow** for high-performance analytics.

---

## 📦 Installation
I strongly recommend using `uv` for 10-100x faster package installation and resolution but `pip` and `poetry` works too.

### Using uv (Recommended)
```bash
uv add surrealengine
# Optional: uv add "surrealengine[signals, jupyter]"
```

### Using pip
```bash
pip install surrealengine
# Optional: pip install "surrealengine[signals, jupyter]"
```

### Using Poetry
```bash
poetry add surrealengine
# Optional: poetry add "surrealengine[signals, jupyter]"
```

---

## ⚡ Quick Start

### 1. Connect
```python
from surrealengine import create_connection

# Async connection with pooling
connection = create_connection(
    url="ws://localhost:8000/rpc",
    namespace="test", database="test",
    username="root", password="root",
    async_mode=True, use_pool=True
)
await connection.connect()
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
            # Standard Index
            {"name": "idx_name", "fields": ["name"], "unique": True},
            # HNSW Vector Index
            {"name": "idx_vector", "fields": ["embedding"], "dimension": 1536, "dist": "COSINE", "m": 16},
        ]
```

### 3. Query & Graph
```python
# Create
jane = await Person(name="Jane", age=30).save()

# Query with Django-style syntax
people = await Person.objects.filter(age__gt=25).all()

# Graph Relations
await jane.relate_to("knows", other_person)
friends = await jane.resolve_relation("knows")
```

### 4. Schema Generation
```python
# Generate DEFINE TABLE/INDEX/EVENT statements automatically
await Person.create_table(schemafull=True)
```

---

## ⚠️ Sharp Edges & Limitations

SurrealEngine is designed to be a robust, high-level abstraction. However, be aware of these specific behaviors:

> [!WARNING]
> Please review these carefully to avoid common pitfalls.

### 1. Embedded Connections & Live Queries
Attempting to use `.live()` on a `mem://` or `file://` connection will raise a `NotImplementedError`. Use `ws://` connections for Live Query support.

### 2. RecordID Field Access
The `RecordID` object uses `table_name` and `id` attributes.
*   **Gotcha**: Do not use `.table` (it doesn't exist). Use `.table_name`.
*   **Tip**: Use `RecordID.parse("table:id")` for safe string parsing.

### 3. Strict Mode by Default
Documents have `strict=True` by default. Set `strict=False` in `Meta` if you need to handle dynamic unstructured data.

### 4. Auto-Connect & Event Loops
Ensure `create_connection(..., auto_connect=True)` is called **within** a running event loop for async connections to avoid "Event loop is closed" errors.

---

<p align="center">
  Built with ❤️ by Iristech Systems
</p>
