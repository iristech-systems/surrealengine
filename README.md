
# SurrealEngine

SurrealEngine is an Object-Document Mapper (ODM) for SurrealDB, providing a Pythonic interface for working with SurrealDB databases. It supports both synchronous and asynchronous operations.

## Requirements

- Python >= 3.8
- surrealdb >= 1.0.3

## Installation

### Basic Installation
```bash
pip install git+https://github.com/iristech-systems/surrealengine.git
```

### Optional Dependencies

SurrealEngine has optional dependencies that can be installed based on your needs:

- **signals**: Adds support for signals (using blinker) to enable event-driven programming
- **jupyter**: Adds support for Jupyter notebooks for interactive development and documentation

To install with optional dependencies:

```bash
# Install with signals support
pip install git+https://github.com/iristech-systems/surrealengine.git#egg=surrealengine[signals]

# Install with Jupyter support
pip install git+https://github.com/iristech-systems/surrealengine.git#egg=surrealengine[jupyter]

# Install with all optional dependencies
pip install git+https://github.com/iristech-systems/surrealengine.git#egg=surrealengine[all]
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

### Advanced Connection Management

SurrealEngine provides advanced connection management features for improved performance, reliability, and flexibility.

#### Connection String Parsing

You can use connection strings to simplify connection configuration:

```python
from surrealengine import SurrealEngineSyncConnection
from surrealengine.connection import parse_connection_string

# Parse a connection string with connection parameters
connection_string = "surrealdb://root:root@localhost:8000/test/test?pool_size=5&retry_limit=3"
config = parse_connection_string(connection_string)

# Create a connection using the parsed config
conn = SurrealEngineSyncConnection(
    url=config["url"],
    namespace=config["namespace"],
    database=config["database"],
    username=config["username"],
    password=config["password"]
)
```

Connection strings support various parameters for configuring connection pooling, timeouts, retries, and more. The "surrealdb://" scheme is automatically mapped to "ws://" for compatibility with the SurrealDB client.

#### Connection Pooling

Connection pooling improves performance by reusing connections instead of creating new ones for each operation:

```python
from surrealengine.connection import SyncConnectionPool, AsyncConnectionPool

# Create a synchronous connection pool
sync_pool = SyncConnectionPool(
    url="ws://localhost:8000",
    namespace="test",
    database="test",
    username="root",
    password="root",
    pool_size=10,                # Maximum number of connections in the pool
    max_idle_time=60,            # Maximum time a connection can be idle before being closed
    connect_timeout=5,           # Timeout for establishing a connection
    operation_timeout=30,        # Timeout for operations
    validate_on_borrow=True      # Validate connections when borrowing from the pool
)

# Get a connection from the pool
conn = sync_pool.get_connection()

# Use the connection
result = conn.client.query("SELECT * FROM user LIMIT 1")

# Return the connection to the pool
sync_pool.return_connection(conn)

# Close the pool when done
sync_pool.close()

# Asynchronous connection pool works similarly
async_pool = AsyncConnectionPool(
    url="ws://localhost:8000",
    namespace="test",
    database="test",
    username="root",
    password="root",
    pool_size=10
)

# Get a connection from the pool
conn = await async_pool.get_connection()

# Use the connection
result = await conn.client.query("SELECT * FROM user LIMIT 1")

# Return the connection to the pool
await async_pool.return_connection(conn)

# Close the pool when done
await async_pool.close()
```

#### Retry Strategy

The retry strategy allows operations to be automatically retried with exponential backoff when they fail:

```python
from surrealengine.connection import RetryStrategy

# Create a retry strategy
retry = RetryStrategy(
    retry_limit=3,       # Maximum number of retries
    retry_delay=1.0,     # Initial delay in seconds between retries
    retry_backoff=2.0    # Backoff multiplier for retry delay
)

# Execute an operation with retry
try:
    result = retry.execute_with_retry(lambda: conn.client.query("SELECT * FROM user"))
except Exception as e:
    print(f"Operation failed after retries: {str(e)}")

# For async operations
try:
    result = await retry.execute_with_retry_async(lambda: conn.client.query("SELECT * FROM user"))
except Exception as e:
    print(f"Async operation failed after retries: {str(e)}")
```

#### Automatic Reconnection

SurrealEngine supports automatic reconnection when a connection is lost, with event notifications and operation queuing:

```python
from surrealengine.connection import ConnectionEvent, ConnectionEventListener

# Create a connection event listener
class MyConnectionListener(ConnectionEventListener):
    def on_event(self, event_type, connection, **kwargs):
        if event_type == ConnectionEvent.RECONNECTING:
            print("Connection lost, attempting to reconnect...")
        elif event_type == ConnectionEvent.RECONNECTED:
            print("Connection reestablished!")

# Register the listener with a connection
listener = MyConnectionListener()
conn.add_listener(listener)
```

For a complete example of the connection management features, see [connection_management_example.py](./example_scripts/connection_management_example.py).

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

#### RelationDocument

For more complex relationships with additional attributes, SurrealEngine provides the `RelationDocument` class:

```python
# Define a RelationDocument class
class ActedIn(RelationDocument):
    role = StringField()
    year = IntField()

    class Meta:
        collection = "acted_in"

# Create a relation with attributes
relation = await ActedIn.create_relation(actor, movie, role="Forrest Gump", year=1994)

# Find relations by in_document
actor_relations = await ActedIn.find_by_in_document(actor)
for rel in actor_relations:
    print(f"{rel.in_document.name} played {rel.role} in {rel.out_document.title}")

# Use RelationQuerySet for advanced querying
acted_in = ActedIn.relates()
await acted_in().relate(actor, movie, role="Forrest Gump", year=1994)
```

The `RelationDocument` class provides methods for creating, querying, updating, and deleting relations with additional attributes. It works with the `RelationQuerySet` class to provide a powerful API for working with complex relationships.

For more detailed examples of working with relations, see [relationships_example.py](./example_scripts/relationships_example.py), [relationships.ipynb](./notebooks/relationships.ipynb), and [embedded_relation_example.py](./example_scripts/embedded_relation_example.py).

### Working with References and Dereferencing

SurrealEngine provides powerful features for working with references between documents and automatically resolving (dereferencing) those references:

```python
# Define document classes with references
class User(Document):
    name = StringField(required=True)
    email = StringField(required=True)

class Post(Document):
    title = StringField(required=True)
    content = StringField()
    author = ReferenceField(User)  # Reference to User document

class Comment(Document):
    content = StringField(required=True)
    post = ReferenceField(Post)    # Reference to Post document
    author = ReferenceField(User)  # Reference to User document

# Create documents with references
user = await User(name="Alice", email="alice@example.com").save()
post = await Post(title="Hello World", content="My first post", author=user).save()
comment = await Comment(content="Great post!", post=post, author=user).save()

# Automatic reference resolution with dereference parameter
# Get a comment with references resolved to depth 2
comment = await Comment.get(id=comment.id, dereference=True, dereference_depth=2)

# Access referenced documents directly
print(comment.content)                # Output: "Great post!"
print(comment.author.name)            # Output: "Alice"
print(comment.post.title)             # Output: "Hello World"
print(comment.post.author.name)       # Output: "Alice"

# Manual reference resolution
comment = await Comment.get(id=comment.id)  # References not resolved
await comment.resolve_references(depth=2)   # Manually resolve references

# JOIN-like operations for efficient retrieval of referenced documents
# Get all comments with their authors joined
comments = await Comment.objects.join("author", dereference=True, dereference_depth=2)
for comment in comments:
    print(f"Comment: {comment.content}, Author: {comment.author.name}")

# Synchronous operations
# Get a comment with references resolved
comment = Comment.get_sync(id=comment.id, dereference=True)

# Manually resolve references synchronously
comment = Comment.get_sync(id=comment.id)  # References not resolved
comment.resolve_references_sync(depth=2)   # Manually resolve references

# JOIN-like operations synchronously
comments = Comment.objects.join_sync("author", dereference=True)
```

The dereferencing functionality makes it easy to work with complex document relationships without writing multiple queries. The `dereference` parameter controls whether references should be automatically resolved, and the `dereference_depth` parameter controls how deep the resolution should go.

For more examples of working with references and dereferencing, see [test_reference_resolution.py](./example_scripts/test_reference_resolution.py).

### Advanced Querying

SurrealEngine provides a powerful query API for filtering, ordering, and paginating results:

```python
# Asynchronous operations
# Filter with complex conditions
results = await Person.objects.filter(
    age__gt=25,
    name__contains="Jo"
).all()

# Filter with nested fields in DictField
users_with_dark_theme = await User.objects.filter(
    settings__theme="dark",
    settings__notifications=True
).all()

# Order results
results = await Person.objects.filter(age__gt=25).order_by("name", "DESC").all()

# Pagination
# Basic pagination with limit and start
page1 = await Person.objects.filter(age__gt=25).limit(10).all()
page2 = await Person.objects.filter(age__gt=25).limit(10).start(10).all()

# Enhanced pagination with page method and metadata
paginated = await Person.objects.paginate(page=1, per_page=10)
print(f"Page 1 of {paginated.pages}, showing {len(paginated.items)} of {paginated.total} items")
print(f"Has next page: {paginated.has_next}, Has previous page: {paginated.has_prev}")

# Iterate through paginated results
for person in paginated:
    print(person.name)

# Get second page
page2 = await Person.objects.paginate(page=2, per_page=10)

# Group by
grouped = await Person.objects.group_by("age").all()

# Split results
split = await Person.objects.split("hobbies").all()

# Fetch related documents
with_books = await Person.objects.fetch("authored").all()

# Get first result
first = await Person.objects.filter(age__gt=25).first()

# Synchronous operations
# Filter with complex conditions
results = Person.objects.filter_sync(
    age__gt=25,
    name__contains="Jo"
).all_sync()
```

The query API is implemented using the `QuerySet` and `QuerySetDescriptor` classes, which provide a fluent interface for building and executing queries. The `QuerySet` class handles the actual query execution, while the `QuerySetDescriptor` provides the interface for building queries.

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
- `DictField`: For nested objects, can specify the field type for values. Supports nested field access in queries using double underscore syntax (e.g., `settings__theme="dark"`)

```python
# Example of using DictField with nested fields
class User(Document):
    name = StringField(required=True)
    settings = DictField()  # Can store nested data like {"theme": "dark", "notifications": True}

# Create a user with nested settings
user = User(name="John", settings={"theme": "dark", "notifications": True})
await user.save()

# Query users with a specific theme using double underscore syntax
dark_theme_users = await User.objects.filter(settings__theme="dark").all()
```

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
- `EmailField`: For storing email addresses with validation
- `URLField`: For storing URLs with validation
- `IPAddressField`: For storing IP addresses with validation (IPv4/IPv6)
- `SlugField`: For storing URL slugs with validation
- `ChoiceField`: For storing values from a predefined set of choices

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

# Using DictField with nested fields in a SCHEMAFULL table
class User(Document):
    name = StringField(required=True)
    settings = DictField()  # Will automatically define nested fields for common keys like 'theme'

# Create the table with schema support for nested fields
await User.create_table(schemafull=True)

# Now you can query nested fields using double underscore syntax
dark_theme_users = await User.objects.filter(settings__theme="dark").all()
```

For more detailed examples of schema management, see [schema_management_example.py](./example_scripts/schema_management_example.py), [hybrid_schema_example.py](./example_scripts/hybrid_schema_example.py), and [schema_management.ipynb](./notebooks/schema_management.ipynb).

For hybrid schemas, see [hybrid_schemas.ipynb](./notebooks/hybrid_schemas.ipynb).

## Logging

SurrealEngine includes a built-in logging system that provides a centralized way to log messages at different levels. The logging system is based on Python's standard logging module but provides a simpler interface.

```python
from surrealengine.logging import logger

# Set the log level
logger.set_level(10)  # DEBUG level (10)

# Log messages at different levels
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")

# Add a file handler to log to a file
logger.add_file_handler("app.log")
```

The logging system supports the following log levels:
- DEBUG (10): Detailed information, typically useful only when diagnosing problems
- INFO (20): Confirmation that things are working as expected
- WARNING (30): An indication that something unexpected happened, or may happen in the near future
- ERROR (40): Due to a more serious problem, the software has not been able to perform some function
- CRITICAL (50): A serious error, indicating that the program itself may be unable to continue running

For more examples of using the logging system, see [test_new_features.py](./example_scripts/test_new_features.py).

## Features in Development

- Migration support
- Advanced indexing
- Query optimization
- Expanded transaction support
- Enhanced schema validation
- Connection health checks and monitoring
- Connection middleware support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
