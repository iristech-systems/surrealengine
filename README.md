
# SurrealEngine

SurrealEngine is an Object-Document Mapper (ODM) for SurrealDB, providing a Pythonic interface for working with SurrealDB databases. It supports both synchronous and asynchronous operations.

> **Important Note**: I have been testing SurrealDB in certain use-cases and am not a long time user or well verse in the deep down details of the system. I focus on user ergonomics over direct compatibility with the core python SurrealDB SDK.  This means much of the module translates queries directly into SurrealQL vs operating through SDK abstraction.  Currently, schema registration with SurrealDB is not implemented. The ODM provides Python-side validation and structure only. 

## Requirements

- Python >= 3.8
- surrealdb >= 1.0.3

## Installation
```bash
pip install surrealengine
```

## Quick Start

> **Note**: The examples below demonstrate the key features of SurrealEngine.

### Connecting to SurrealDB

SurrealEngine supports both synchronous and asynchronous connections. Choose the one that fits your application's needs.

#### Asynchronous Connection
```python
from surrealengine import SurrealEngineAsyncConnection, SurrealEngine

# Create an async connection
async_conn = SurrealEngineAsyncConnection(
    url="wss://CONNECTION_STRING",
    namespace="NAMESPACE",
    database="DATABASE_NAME",
    username="USERNAME",
    password="PASSWORD",
)
await async_conn.connect()
async_db = SurrealEngine(async_conn)
```

#### Synchronous Connection
```python
from surrealengine import SurrealEngineSyncConnection, SurrealEngine

# Create a sync connection
sync_conn = SurrealEngineSyncConnection(
    url="wss://CONNECTION_STRING",
    namespace="NAMESPACE",
    database="DATABASE_NAME",
    username="USERNAME",
    password="PASSWORD",
)
sync_conn.connect()  # Note: No await needed
sync_db = SurrealEngine(sync_conn)
```

#### Using the Factory Function
```python
from surrealengine import create_connection, SurrealEngine

# Create an async connection
async_conn = create_connection(
    url="wss://CONNECTION_STRING",
    namespace="NAMESPACE",
    database="DATABASE_NAME",
    username="USERNAME",
    password="PASSWORD",
    async_mode=True  # Default is True
)
await async_conn.connect()

# Create a sync connection
sync_conn = create_connection(
    url="wss://CONNECTION_STRING",
    namespace="NAMESPACE",
    database="DATABASE_NAME",
    username="USERNAME",
    password="PASSWORD",
    async_mode=False
)
sync_conn.connect()
```

> **Note**: For backward compatibility, `SurrealEngineConnection` is an alias for `SurrealEngineAsyncConnection`.
### Basic Document Model

Document models are defined the same way for both sync and async operations:

```python
from surrealengine import Document, StringField, IntField, FloatField, DateTimeField, ListField, DictField, BooleanField

class Person(Document):
    name = StringField(required=True)
    age = IntField()

    class Meta:
        collection = "person"
        indexes = [
            {"name": "idx_person_name", "fields": ["name"], "unique": True}
        ]

class Actor(Document):
    name = StringField(required=True)
    birth_date = DateTimeField()
    nationality = StringField()

    class Meta:
        collection = 'actor'

    # Define relation to movies through the 'acted_in' relation
    acted_in = Document.relates('acted_in')

class Movie(Document):
    title = StringField(required=True)
    release_year = IntField()
    rating = FloatField(min_value=0, max_value=10)
    director = StringField()

    class Meta:
        collection = 'movie'

    # Define relation to actors through the 'acted_in' relation
    actors = Document.relates('acted_in')
``` 

### Creating and Querying Documents

#### Asynchronous Operations

```python
# Creating a document
jane = await Person(name="Jane", age=30).save()

# Get a document by ID
person = await Person.objects.get(id=jane.id)

# Get a document by field
person = await Person.objects.get(name="Jane")

# Query documents
people = await Person.objects.filter(age__gt=25).all()

# Create an index
await Person.create_index(
    "person_age_index",
    fields=["age"],
    unique=False,
    comment="Person age index"
)

# Create all indexes defined in Meta
await Person.create_indexes()

# Bulk create documents
people = [
    Person(name=f"Person {i}", age=20+i) 
    for i in range(10)
]
created_people = await Person.bulk_create(people)

# Update documents
updated = await Person.objects.filter(age__lt=30).update(age=30)

# Delete documents
deleted_count = await Person.objects.filter(age__gt=50).delete()

# Schemaless queries
results = await async_db.person(name="Jane")
results = await async_db.person.objects.filter(age__gt=25).all()
```

#### Synchronous Operations

```python
# Creating a document
jane = Person(name="Jane", age=30).save_sync()

# Get a document by ID
person = Person.objects.get_sync(id=jane.id)

# Get a document by field
person = Person.objects.get_sync(name="Jane")

# Query documents
people = Person.objects.filter_sync(age__gt=25).all_sync()

# Create an index
Person.create_index_sync(
    "person_age_index",
    fields=["age"],
    unique=False,
    comment="Person age index"
)

# Create all indexes defined in Meta
Person.create_indexes_sync()

# Bulk create documents
people = [
    Person(name=f"Person {i}", age=20+i) 
    for i in range(10)
]
created_people = Person.bulk_create_sync(people)

# Update documents
updated = Person.objects.filter_sync(age__lt=30).update_sync(age=30)

# Delete documents
deleted_count = Person.objects.filter_sync(age__gt=50).delete_sync()

# Schemaless queries
results = sync_db.person.call_sync(name="Jane")
results = sync_db.person.objects.filter(age__gt=25).all_sync()
```

### Working with Document IDs

SurrealDB uses a unique identifier format for documents: `collection:id`. SurrealEngine handles this format automatically:

```python
# Create a document
person = await Person(name="Jane", age=30).save()

# The ID is a RecordID object
print(person.id)  # Output: person:abc123def456

# You can access the raw ID string
print(str(person.id))  # Output: "person:abc123def456"

# Or access the table name and record ID separately
print(person.id.table_name)  # Output: "person"
print(person.id.record_id)   # Output: "abc123def456"

# When updating a document, you can use the full ID or just the RecordID object
await person.save()  # Uses the RecordID object internally

# When querying by ID, you can use either format
person = await Person.objects.get(id="person:abc123def456")
# or
person = await Person.objects.get(id=person.id)
```

SurrealEngine automatically handles the conversion between different ID formats, making it easy to work with document references.

### Working with Relations

#### Asynchronous Operations

```python
# Create an actor and a movie
actor = Actor(
    name="Tom Hanks",
    birth_date="1956-07-09",
    nationality="American"
)
await actor.save()

movie = Movie(
    title="Forrest Gump",
    release_year=1994,
    rating=8.8,
    director="Robert Zemeckis"
)
await movie.save()

# Create a relation
await actor.relate_to(
    'acted_in',
    movie,
    role="Forrest Gump",
    award="Academy Award for Best Actor"
)

# Fetch actor
actor = await Actor.objects.get(name="Tom Hanks")

# Get relation data
relations = await actor.fetch_relation('acted_in')
# Example output:
# {'id': RecordID(table_name=actor, record_id=q33bto59e6b49wjoie12),
#  'related': [RecordID(table_name=movie, record_id=4gys3es1yv8bld17xc67)]}

# Resolve related documents
movies = await actor.resolve_relation('acted_in')
# Example output:
# [{'director': 'Robert Zemeckis',
#   'id': RecordID(table_name=movie, record_id=4gys3es1yv8bld17xc67),
#   'rating': 8.8,
#   'release_year': 1994,
#   'title': 'Forrest Gump'}]

# Update relation
await actor.update_relation('acted_in', movie, award="Multiple Awards")

# Delete relation
await actor.delete_relation('acted_in', movie)
```

#### Synchronous Operations

```python
# Create an actor and a movie
actor = Actor(
    name="Tom Hanks",
    birth_date="1956-07-09",
    nationality="American"
)
actor.save_sync()

movie = Movie(
    title="Forrest Gump",
    release_year=1994,
    rating=8.8,
    director="Robert Zemeckis"
)
movie.save_sync()

# Create a relation
actor.relate_to_sync(
    'acted_in',
    movie,
    role="Forrest Gump",
    award="Academy Award for Best Actor"
)

# Fetch actor
actor = Actor.objects.get_sync(name="Tom Hanks")

# Get relation data
relations = actor.fetch_relation_sync('acted_in')

# Resolve related documents
movies = actor.resolve_relation_sync('acted_in')

# Update relation
actor.update_relation_sync('acted_in', movie, award="Multiple Awards")

# Delete relation
actor.delete_relation_sync('acted_in', movie)
```

### Advanced Querying

#### Asynchronous Operations

```python
# Filter with complex conditions
results = await Person.objects.filter(
    age__gt=25,
    name__contains="Jo"
).all()

# Order results
results = await Person.objects.filter(age__gt=25).order_by("name", "DESC").all()

# Limit results
results = await Person.objects.filter(age__gt=25).limit(10).all()

# Pagination
page1 = await Person.objects.filter(age__gt=25).limit(10).all()
page2 = await Person.objects.filter(age__gt=25).limit(10).start(10).all()

# Count results
count = await Person.objects.filter(age__gt=25).count()

# Using indexes
results = await Person.objects.with_index("person_age_index").filter(age__gt=25).all()

# Using the database engine (schemaless)
results = await async_db.person.objects.filter(age__gt=25).all()
```

#### Synchronous Operations

```python
# Filter with complex conditions
results = Person.objects.filter_sync(
    age__gt=25,
    name__contains="Jo"
).all_sync()

# Order results
results = Person.objects.filter_sync(age__gt=25).order_by("name", "DESC").all_sync()

# Limit results
results = Person.objects.filter_sync(age__gt=25).limit(10).all_sync()

# Pagination
page1 = Person.objects.filter_sync(age__gt=25).limit(10).all_sync()
page2 = Person.objects.filter_sync(age__gt=25).limit(10).start(10).all_sync()

# Count results
count = Person.objects.filter_sync(age__gt=25).count_sync()

# Using indexes
results = Person.objects.with_index("person_age_index").filter(age__gt=25).all_sync()

# Using the database engine (schemaless)
results = sync_db.person.objects.filter(age__gt=25).all_sync()
```

### Schemaless Operations

SurrealEngine provides a schemaless API for working with tables without a predefined schema. This is useful for exploratory data analysis, prototyping, or working with dynamic data structures.

#### Schemaless Relation Operations

##### Asynchronous Operations

```python
# Create a relation between two records
await async_db.person.relate("person:jane", "knows", "person:john", since="2020-01-01")

# Get related records
related = await async_db.person.get_related("person:jane", "knows")

# Get related records with target table
friends = await async_db.person.get_related("person:jane", "knows", "person")

# Update a relation
await async_db.person.update_relation("person:jane", "knows", "person:john", since="2021-01-01", close=True)

# Delete a relation
await async_db.person.delete_relation("person:jane", "knows", "person:john")

# Delete all relations of a type
await async_db.person.delete_relation("person:jane", "knows")
```

##### Synchronous Operations

```python
# Create a relation between two records
sync_db.person.relate_sync("person:jane", "knows", "person:john", since="2020-01-01")

# Get related records
related = sync_db.person.get_related_sync("person:jane", "knows")

# Get related records with target table
friends = sync_db.person.get_related_sync("person:jane", "knows", "person")

# Update a relation
sync_db.person.update_relation_sync("person:jane", "knows", "person:john", since="2021-01-01", close=True)

# Delete a relation
sync_db.person.delete_relation_sync("person:jane", "knows", "person:john")

# Delete all relations of a type
sync_db.person.delete_relation_sync("person:jane", "knows")
```

#### Schemaless Bulk Operations

##### Asynchronous Operations

```python
# Create multiple records in a single operation
people = [
    {"name": f"Person {i}", "age": 20+i} 
    for i in range(10)
]
created_people = await async_db.person.bulk_create(people)

# Create multiple records without returning them
count = await async_db.person.bulk_create(people, return_documents=False)

# Create multiple records with custom batch size
created_people = await async_db.person.bulk_create(people, batch_size=5)

# Using the query set directly
created_people = await async_db.person.objects.bulk_create(people)
```

##### Synchronous Operations

```python
# Create multiple records in a single operation
people = [
    {"name": f"Person {i}", "age": 20+i} 
    for i in range(10)
]
created_people = sync_db.person.bulk_create_sync(people)

# Create multiple records without returning them
count = sync_db.person.bulk_create_sync(people, return_documents=False)

# Create multiple records with custom batch size
created_people = sync_db.person.bulk_create_sync(people, batch_size=5)

# Using the query set directly
created_people = sync_db.person.objects.bulk_create_sync(people)
```

#### Schemaless Transaction Operations

##### Asynchronous Operations

```python
# Define coroutines to execute in a transaction
async def create_person():
    return await async_db.person.objects.create(name="Jane", age=30)

async def create_movie():
    return await async_db.movie.objects.create(title="Inception", year=2010)

# Execute coroutines in a transaction
results = await async_db.person.transaction([
    create_person(),
    create_movie()
])

# Access the results
person, movie = results
```

##### Synchronous Operations

```python
# Define functions to execute in a transaction
def create_person():
    return sync_db.person.objects.create_sync(name="Jane", age=30)

def create_movie():
    return sync_db.movie.objects.create_sync(title="Inception", year=2010)

# Execute functions in a transaction
results = sync_db.person.transaction_sync([
    create_person,
    create_movie
])

# Access the results
person, movie = results
```

### Graph Traversal

SurrealEngine provides powerful graph traversal capabilities through both the Document class and the dedicated GraphQuery class.

#### Document Path Traversal

You can traverse paths in the graph starting from a document instance:

```python
# Async traversal
# Find all movies that actors in the same nationality as this actor have acted in
movies = await actor.traverse_path(
    "->[acted_in]->actor<-[acted_in]-", 
    target_document=Movie,
    nationality=actor.nationality
)

# Sync traversal
movies = actor.traverse_path_sync(
    "->[acted_in]->actor<-[acted_in]-", 
    target_document=Movie,
    nationality=actor.nationality
)
```

#### GraphQuery Builder

For more complex graph queries, use the GraphQuery class:

```python
from surrealengine import GraphQuery

# Async graph query
query = GraphQuery(async_conn)
results = await query.start_from(Actor, name="Tom Hanks")
                     .traverse("->[acted_in]->")
                     .end_at(Movie)
                     .filter_results(rating__gt=8.0)
                     .execute()

# Results will be Movie instances
for movie in results:
    print(f"{movie.title} ({movie.release_year}): {movie.rating}")
```

This fluent interface makes it easy to build complex graph traversals while maintaining readability.

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

## Features in Development

- Schema registration with SurrealDB
- Migration support
- Advanced indexing
- Query optimization
- Expanded transaction support
- Enhanced schema validation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
