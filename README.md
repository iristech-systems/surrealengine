
# SurrealEngine

SurrealEngine is an Object-Document Mapper (ODM) for SurrealDB, providing a Pythonic interface for working with SurrealDB databases. It supports both synchronous and asynchronous operations.

## Requirements

- Python >= 3.8
- surrealdb >= 1.0.3

## Installation
```bash
pip install surrealengine
```

## Quick Start

> **Note**: For detailed examples, please refer to the [notebooks](./notebooks) and [example_scripts](./example_scripts) directories. Written by a SurrealDB newbie to learn more about the system.

### Connecting to SurrealDB

SurrealEngine supports both synchronous and asynchronous connections. Choose the one that fits your application's needs.

```python
# Asynchronous connection
from surrealengine import SurrealEngineAsyncConnection, SurrealEngine
async_conn = SurrealEngineAsyncConnection(url="wss://CONNECTION_STRING", namespace="NAMESPACE", database="DATABASE_NAME", username="USERNAME", password="PASSWORD")
await async_conn.connect()
async_db = SurrealEngine(async_conn)

# Synchronous connection
from surrealengine import SurrealEngineSyncConnection, SurrealEngine
sync_conn = SurrealEngineSyncConnection(url="wss://CONNECTION_STRING", namespace="NAMESPACE", database="DATABASE_NAME", username="USERNAME", password="PASSWORD")
sync_conn.connect()  # Note: No await needed
sync_db = SurrealEngine(sync_conn)
```

> **Note**: For backward compatibility, `SurrealEngineConnection` is an alias for `SurrealEngineAsyncConnection`.

For more detailed examples, see [sync_api_example.py](./example_scripts/sync_api_example.py) and [sync_api.ipynb](./notebooks/sync_api.ipynb).
### Basic Document Model

Document models are defined the same way for both sync and async operations:

```python
from surrealengine import Document, StringField, IntField

class Person(Document):
    name = StringField(required=True)
    age = IntField()

    class Meta:
        collection = "person"
        indexes = [
            {"name": "idx_person_name", "fields": ["name"], "unique": True}
        ]
```

For more examples of document models including relationships, see [relationships_example.py](./example_scripts/relationships_example.py) and [relationships.ipynb](./notebooks/relationships.ipynb).

### Creating and Querying Documents

Here are basic examples of creating and querying documents:

```python
# Asynchronous operations
# Creating a document
jane = await Person(name="Jane", age=30).save()

# Get a document by ID
person = await Person.objects.get(id=jane.id)

# Query documents
people = await Person.objects.filter(age__gt=25).all()

# Synchronous operations
# Creating a document
jane = Person(name="Jane", age=30).save_sync()

# Get a document by ID
person = Person.objects.get_sync(id=jane.id)

# Query documents
people = Person.objects.filter_sync(age__gt=25).all_sync()
```

For more detailed examples of CRUD operations, see [basic_crud_example.py](./example_scripts/basic_crud_example.py).

For pagination examples, see [pagination_example.py](./example_scripts/pagination_example.py) and [pagination.ipynb](./notebooks/pagination.ipynb).

### Working with Document IDs

SurrealDB uses a unique identifier format for documents: `collection:id`. SurrealEngine handles this format automatically:

```python
# Create a document
person = await Person(name="Jane", age=30).save()

# The ID is a RecordID object
print(person.id)  # Output: person:abc123def456

# Access the table name and record ID separately
print(person.id.table_name)  # Output: "person"
print(person.id.record_id)   # Output: "abc123def456"
```

SurrealEngine automatically handles the conversion between different ID formats, making it easy to work with document references.

For more examples of working with document IDs, see [basic_crud_example.py](./example_scripts/basic_crud_example.py).

### Working with Relations

SurrealEngine provides a simple API for working with graph relationships:

```python
# Asynchronous operations
# Create a relation
await actor.relate_to('acted_in', movie, role="Forrest Gump")

# Resolve related documents
movies = await actor.resolve_relation('acted_in')

# Synchronous operations
# Create a relation
actor.relate_to_sync('acted_in', movie, role="Forrest Gump")

# Resolve related documents
movies = actor.resolve_relation_sync('acted_in')
```

For more detailed examples of working with relations, see [relationships_example.py](./example_scripts/relationships_example.py) and [relationships.ipynb](./notebooks/relationships.ipynb).

### Advanced Querying

SurrealEngine provides a powerful query API for filtering, ordering, and paginating results:

```python
# Asynchronous operations
# Filter with complex conditions
results = await Person.objects.filter(
    age__gt=25,
    name__contains="Jo"
).all()

# Order results
results = await Person.objects.filter(age__gt=25).order_by("name", "DESC").all()

# Pagination
page1 = await Person.objects.filter(age__gt=25).limit(10).all()
page2 = await Person.objects.filter(age__gt=25).limit(10).start(10).all()

# Synchronous operations
# Filter with complex conditions
results = Person.objects.filter_sync(
    age__gt=25,
    name__contains="Jo"
).all_sync()
```

For more detailed examples of advanced querying, see [basic_crud_example.py](./example_scripts/basic_crud_example.py).

For pagination examples, see [pagination_example.py](./example_scripts/pagination_example.py) and [pagination.ipynb](./notebooks/pagination.ipynb).

### Schemaless Operations

SurrealEngine provides a schemaless API for working with tables without a predefined schema. This is useful for exploratory data analysis, prototyping, or working with dynamic data structures.

```python
# Asynchronous operations
# Create a relation between two records
await async_db.person.relate("person:jane", "knows", "person:john", since="2020-01-01")

# Get related records
related = await async_db.person.get_related("person:jane", "knows")

# Bulk create records
people = [{"name": f"Person {i}", "age": 20+i} for i in range(10)]
created_people = await async_db.person.bulk_create(people)

# Synchronous operations
# Create a relation between two records
sync_db.person.relate_sync("person:jane", "knows", "person:john", since="2020-01-01")

# Bulk create records
created_people = sync_db.person.bulk_create_sync(people)
```

For more detailed examples of schemaless operations, see [basic_crud_example.py](./example_scripts/basic_crud_example.py) and [relationships_example.py](./example_scripts/relationships_example.py).

## Available Fields

### Basic Types
- `StringField`: For text data with optional min/max length and regex validation
- `IntField`: For integer values with optional min/max constraints
- `FloatField`: For floating-point numbers with optional min/max constraints
- `BooleanField`: For true/false values
- `DateTimeField`: For datetime values, handles various input formats

### Numeric Types
- `DecimalField`: For precise decimal numbers (uses Python's Decimal)
- `DurationField`: For time durations

### Collection Types
- `ListField`: For arrays, can specify the field type for items
- `DictField`: For nested objects, can specify the field type for values

### Reference Types
- `ReferenceField`: For document references
- `RelationField`: For graph relationships

### Specialized Types
- `GeometryField`: For geometric data (points, lines, polygons)
- `BytesField`: For binary data
- `RegexField`: For regular expression patterns
- `RangeField`: For range values (min-max pairs)
- `OptionField`: For optional values (similar to Rust's Option type)
- `FutureField`: For future/promise values and computed fields

## When to Use Sync vs. Async

### Use Synchronous Operations When:

- Working in a synchronous environment (like scripts, CLI tools)
- Simplicity is more important than performance
- Making simple, sequential database operations
- Working with frameworks that don't support async (like Flask)
- Prototyping or debugging

```python
# Example of synchronous usage
from surrealengine import SurrealEngineSyncConnection, SurrealEngine, Document

# Connect
conn = SurrealEngineSyncConnection(url="wss://...", namespace="test", database="test", username="root", password="pass")
conn.connect()
db = SurrealEngine(conn)

# Use
person = db.person.call_sync(name="Jane")
```

### Use Asynchronous Operations When:

- Working in an async environment (like FastAPI, asyncio)
- Performance and scalability are important
- Making many concurrent database operations
- Building high-throughput web applications
- Handling many simultaneous connections

```python
# Example of asynchronous usage
import asyncio
from surrealengine import SurrealEngineAsyncConnection, SurrealEngine, Document

async def main():
    # Connect
    conn = SurrealEngineAsyncConnection(url="wss://...", namespace="test", database="test", username="root", password="pass")
    await conn.connect()
    db = SurrealEngine(conn)

    # Use
    person = await db.person(name="Jane")

asyncio.run(main())
```

## Schema Generation

SurrealEngine supports generating SurrealDB schema statements from Document classes. This allows you to create tables and fields in SurrealDB based on your Python models.

```python
# Create a SCHEMAFULL table (Async)
await Person.create_table(schemafull=True)

# Create a SCHEMALESS table (Sync)
Person.create_table_sync(schemafull=False)

# Hybrid schema approach
class Product(Document):
    name = StringField(required=True, define_schema=True)  # Will be in schema
    price = FloatField(define_schema=True)                # Will be in schema
    description = StringField()                           # Won't be in schema
```

For more detailed examples of schema management, see [schema_management_example.py](./example_scripts/schema_management_example.py), [hybrid_schema_example.py](./example_scripts/hybrid_schema_example.py), and [schema_management.ipynb](./notebooks/schema_management.ipynb).

For hybrid schemas, see [hybrid_schemas.ipynb](./notebooks/hybrid_schemas.ipynb).

## Features in Development

- Migration support
- Advanced indexing
- Query optimization
- Expanded transaction support
- Enhanced schema validation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
