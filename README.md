
# SurrealEngine

SurrealEngine is an Object-Document Mapper (ODM) for SurrealDB, providing a Pythonic interface for working with SurrealDB databases. It supports both synchronous and asynchronous operations.
Credit to MongoEngine for providing such an extensive ODM. Much of my work was directly influenced by my love for MongoEngine.


## Requirements

- Python >= 3.10
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
# Modern connection approach (recommended)
from surrealengine import create_connection

# Asynchronous connection
connection = create_connection(
    url="ws://localhost:8001/rpc",
    namespace="test_ns",
    database="test_db",
    username="root",
    password="root",
    make_default=True
)
await connection.connect()

# Synchronous connection
sync_connection = create_connection(
    url="ws://localhost:8001/rpc",
    namespace="test_ns", 
    database="test_db",
    username="root",
    password="root",
    async_mode=False,
    auto_connect=True
)

# Legacy connection approach (still supported)
from surrealengine import SurrealEngineAsyncConnection, SurrealEngine
async_conn = SurrealEngineAsyncConnection(url="ws://CONNECTION_STRING", namespace="NAMESPACE", database="DATABASE_NAME", username="USERNAME", password="PASSWORD")
await async_conn.connect()
async_db = SurrealEngine(async_conn)
```

> **Note**: For backward compatibility, `SurrealEngineConnection` is an alias for `SurrealEngineAsyncConnection`.

For more detailed examples, see [sync_api_example.py](./example_scripts/sync_api_example.py) and [sync_api.ipynb](./notebooks/sync_api.ipynb).

### Advanced Connection Management

SurrealEngine provides comprehensive connection management features including connection pooling, automatic reconnection, retry strategies, and flexible configuration options.

#### Factory Function and Auto-Connection

The `create_connection()` factory function provides a unified way to create connections with advanced features:

```python
from surrealengine import create_connection

# Create an async connection with pooling
conn = create_connection(
    url="ws://localhost:8000/rpc",
    namespace="test",
    database="test",
    username="root",
    password="root",
    async_mode=True,          # Create async connection (default)
    use_pool=True,            # Enable connection pooling
    pool_size=15,             # Pool size (default: 10)
    make_default=True,        # Set as default connection
    auto_connect=False        # Don't auto-connect (await conn.connect() manually)
)

# Create a sync connection (no pooling for sync)
sync_conn = create_connection(
    url="ws://localhost:8000/rpc",
    namespace="test",
    database="test",
    username="root",
    password="root",
    async_mode=False,         # Create sync connection
    auto_connect=True         # Auto-connect immediately
)
```

#### Connection String Parsing

SurrealEngine supports connection strings for streamlined configuration:

```python
from surrealengine.connection import parse_connection_string

# Parse a comprehensive connection string
connection_string = "surrealdb://root:root@localhost:8000/test/test?pool_size=15&retry_limit=5&connect_timeout=10&operation_timeout=45&validate_on_borrow=true"
config = parse_connection_string(connection_string)

# Create connection using parsed config
conn = create_connection(**config, async_mode=True, use_pool=True)
```

**Supported connection string parameters:**
- `pool_size`: Maximum connections in pool (default: 10)
- `max_idle_time`: Idle timeout in seconds (default: 60)
- `connect_timeout`: Connection timeout in seconds (default: 30)
- `operation_timeout`: Operation timeout in seconds (default: 30)
- `retry_limit`: Maximum retry attempts (default: 3)
- `retry_delay`: Initial retry delay in seconds (default: 1.0)
- `retry_backoff`: Retry delay multiplier (default: 2.0)
- `validate_on_borrow`: Validate connections when borrowed (default: true)

**Supported protocols:**
- `surrealdb://` (mapped to `ws://`)
- `ws://` and `wss://`
- `http://` and `https://`

#### Connection Pooling

Connection pooling dramatically improves performance by reusing connections:

```python
from surrealengine.connection import AsyncConnectionPool, SyncConnectionPool

# Async connection pool with comprehensive configuration
async_pool = AsyncConnectionPool(
    url="ws://localhost:8000/rpc",
    namespace="test",
    database="test",
    username="root",
    password="root",
    pool_size=20,                # Maximum connections
    max_idle_time=120,           # Idle timeout (seconds)
    connect_timeout=10,          # Connection timeout
    operation_timeout=60,        # Operation timeout
    retry_limit=5,               # Retry attempts
    retry_delay=0.5,             # Initial retry delay
    retry_backoff=2.0,           # Backoff multiplier
    validate_on_borrow=True      # Validate on borrow
)

# Async pool usage
conn = await async_pool.get_connection()
try:
    result = await conn.client.query("SELECT * FROM user LIMIT 1")
finally:
    await async_pool.return_connection(conn)

# Pool statistics
print(f"Pool stats: {async_pool.created_connections} created, {async_pool.borrowed_connections} borrowed")

# Close pool
await async_pool.close()

# Sync connection pool
sync_pool = SyncConnectionPool(
    url="ws://localhost:8000/rpc",
    namespace="test",
    database="test",
    username="root",
    password="root",
    pool_size=10
)

# Sync pool usage with context manager
with sync_pool.get_connection() as conn:
    result = conn.client.query("SELECT * FROM user LIMIT 1")

sync_pool.close()
```

#### Integrated Pool Client

The `ConnectionPoolClient` provides seamless pool integration:

```python
# Connection with integrated pooling
conn = create_connection(
    url="ws://localhost:8000/rpc",
    namespace="test",
    database="test", 
    username="root",
    password="root",
    use_pool=True,
    pool_size=15,
    async_mode=True
)

await conn.connect()  # Initializes the pool

# Use normally - pooling is transparent
result = await conn.client.query("SELECT * FROM user")

# Pool is automatically managed
await conn.disconnect()
```

#### Retry Strategy with Exponential Backoff

Automatic retry with configurable backoff strategies:

```python
from surrealengine.connection import RetryStrategy

# Create retry strategy
retry = RetryStrategy(
    retry_limit=5,         # Maximum retries
    retry_delay=0.5,       # Initial delay (seconds)
    retry_backoff=2.0      # Exponential backoff multiplier
)

# Async retry
try:
    result = await retry.execute_with_retry_async(
        lambda: conn.client.query("SELECT * FROM user")
    )
except Exception as e:
    print(f"Operation failed after {retry.retry_limit} retries: {e}")

# Sync retry
try:
    result = retry.execute_with_retry(
        lambda: conn.client.query("SELECT * FROM user")
    )
except Exception as e:
    print(f"Operation failed: {e}")
```

#### Event-Driven Connection Monitoring

Monitor connection lifecycle with event listeners:

```python
from surrealengine.connection import ConnectionEvent, ConnectionEventListener

class DatabaseConnectionMonitor(ConnectionEventListener):
    def on_event(self, event_type, connection, **kwargs):
        if event_type == ConnectionEvent.CONNECTING:
            print(f"Connecting to {connection.url}...")
        elif event_type == ConnectionEvent.CONNECTED:
            print("Successfully connected!")
        elif event_type == ConnectionEvent.DISCONNECTED:
            print("Connection closed")
        elif event_type == ConnectionEvent.RECONNECTING:
            print("Connection lost, attempting reconnection...")
        elif event_type == ConnectionEvent.RECONNECTED:
            print("Connection reestablished!")
        elif event_type == ConnectionEvent.ERROR:
            error = kwargs.get('error', 'Unknown error')
            print(f"Connection error: {error}")

# Register listener
monitor = DatabaseConnectionMonitor()
conn.add_listener(monitor)

# Remove listener when done
conn.remove_listener(monitor)
```

#### Connection Registry

Manage multiple named connections:

```python
from surrealengine.connection import get_connection, list_connections

# Create multiple connections
primary_conn = create_connection(
    url="ws://primary-db:8000/rpc",
    namespace="prod",
    database="main",
    username="root",
    password="secret",
    name="primary",
    make_default=True
)

analytics_conn = create_connection(
    url="ws://analytics-db:8000/rpc",
    namespace="analytics", 
    database="metrics",
    username="reader",
    password="readonly",
    name="analytics"
)

# Retrieve connections by name
primary = get_connection("primary")
analytics = get_connection("analytics")
default = get_connection()  # Gets default connection

# List all registered connections
all_connections = list_connections()
print(f"Registered connections: {list(all_connections.keys())}")
```

For a complete example of the connection management features, see [connection_management_example.py](./example_scripts/connection_management_example.py).
For newly added connection safety and observability features (ContextVar defaults, pool health checks, backpressure metrics, optional OTEL), see [connection_and_observability_example.py](./example_scripts/connection_and_observability_example.py).

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

SurrealEngine provides multiple powerful query APIs for filtering, ordering, and paginating results:
- **Traditional field lookups** for simple queries
- **Q objects** for complex boolean logic (AND/OR/NOT)
- **QueryExpression** for comprehensive query building with FETCH, ORDER BY, etc.

#### Traditional Field Lookup Queries

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
```

#### Complex Queries with Q Objects

For complex boolean logic, use Q objects which support AND (&), OR (|), and NOT (~) operations:

```python
from surrealengine import Q

# Complex AND/OR queries
query = Q(age__gt=18) & Q(active=True)  # AND condition
users = await User.objects.filter(query).all()

# OR conditions  
query = Q(department="engineering") | Q(department="sales")
users = await User.objects.filter(query).all()

# NOT conditions
query = ~Q(active=False)  # Get all active users
users = await User.objects.filter(query).all()

# Complex nested logic
query = (Q(age__gte=18) & Q(active=True)) | Q(role="admin")
users = await User.objects.filter(query).all()

# Raw queries for ultimate flexibility
query = Q.raw("age > 20 AND username CONTAINS 'admin'")
users = await User.objects.filter(query).all()

# Alternative objects(query) syntax
users = await User.objects(Q(active=True) & Q(age__gt=25))
```

#### QueryExpression for Comprehensive Query Building

For queries requiring FETCH, GROUP BY, ORDER BY, and other clauses:

```python
from surrealengine import QueryExpression, Q

# QueryExpression with FETCH for automatic dereferencing
expr = QueryExpression(where=Q(published=True)).fetch("author")
posts = await Post.objects.filter(expr).all()

# Complex expression with multiple clauses
expr = (QueryExpression(where=Q(active=True))
        .fetch("profile", "posts")
        .order_by("created_at", "DESC") 
        .limit(10))
users = await User.objects.filter(expr).all()

# Synchronous versions also supported
query = Q(age__gt=25) & Q(active=True)
users = User.objects.filter_sync(query).all_sync()

expr = QueryExpression(where=Q(active=True)).fetch("profile").limit(5)
users = User.objects.filter_sync(expr).all_sync()
```

The Q object and QueryExpression system provides Django-style querying with powerful boolean logic, automatic reference dereferencing through FETCH, and full compatibility with existing SurrealEngine query methods.

For comprehensive examples of Q objects and QueryExpression, see [query_expressions_example.py](./example_scripts/query_expressions_example.py).

#### Traditional Query Methods

```python
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
- `DecimalField`: For precise decimal numbers (uses Python's Decimal) - **Fixed**: Now properly inherits from NumberField, supports min_value/max_value constraints, and converts to float for SurrealDB compatibility
- `DurationField`: For time durations - **Fixed**: Now uses proper SurrealDB Duration objects and supports year-to-day conversions

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

## DataGrid API Support

SurrealEngine provides comprehensive frontend integration for data table libraries, allowing you to replace inefficient Python-based filtering with optimized SurrealDB queries.

### Performance Benefits

Instead of fetching all data and filtering in Python:
```python
# ❌ Inefficient approach
all_listings = await case.get_listings()  # Fetch everything
filtered_listings = []
for listing in all_listings:
    if marketplace and listing.marketplace != marketplace:
        continue
    # ... more Python filtering
```

Use efficient database-level operations:
```python
# ✅ Optimized approach
from surrealengine import get_grid_data

result = await get_grid_data(
    Listing,
    request.args.to_dict(),
    search_fields=['marketplace', 'seller_name', 'product_name'],
    custom_filters={'marketplace': 'marketplace', 'seller': 'seller_name'}
)
return jsonify(result)  # Perfect BootstrapTable format!
```

### BootstrapTable.js Support

SurrealEngine generates responses in BootstrapTable format by default:

```python
# Your existing route (async)
@app.route('/api/listings')
async def api_listings():
    result = await get_grid_data(
        Listing,
        request.args.to_dict(),
        search_fields=['product_name', 'marketplace', 'seller_name'],
        custom_filters={'marketplace': 'marketplace', 'seller': 'seller_name'},
        default_sort='date_collected'
    )
    # Returns: {"total": 150, "rows": [...]}
    return jsonify(result)

# Synchronous version
def api_listings_sync():
    from surrealengine import get_grid_data_sync
    result = get_grid_data_sync(Listing, request.args.to_dict(), search_fields, custom_filters)
    return jsonify(result)
```

### DataTables.js Support

For DataTables which uses different parameter names:

```python
from surrealengine import parse_datatables_params, format_datatables_response

@app.route('/api/listings/datatables', methods=['POST'])
async def api_listings_datatables():
    # Convert DataTables parameters (start/length) to standard format (offset/limit)
    params = parse_datatables_params(request.args.to_dict())
    
    result = await get_grid_data(Listing, params, search_fields, custom_filters)
    
    # Format for DataTables
    return jsonify(format_datatables_response(
        result['total'], 
        result['rows'], 
        params['draw']
    ))
```

### Search and Filtering

The DataGrid API supports:
- **Text search** across multiple fields using `contains` operator
- **Field-specific filters** with custom parameter mapping
- **Sorting** by any field (ascending/descending)
- **Pagination** with offset/limit or start/length parameters

```python
# Example with comprehensive filtering
result = await get_grid_data(
    ProductListing,
    {
        'limit': '25',
        'offset': '0',
        'search': 'wireless headphones',  # Searches across search_fields
        'marketplace': 'Amazon',          # Custom filter
        'seller': 'TechStore',           # Custom filter
        'sort': 'price',                 # Sort field
        'order': 'desc'                  # Sort direction
    },
    search_fields=['product_name', 'description', 'brand'],
    custom_filters={
        'marketplace': 'marketplace',     # URL param -> DB field mapping
        'seller': 'seller_name',
        'category': 'product_category'
    }
)
```

### Performance Improvements

The DataGrid API leverages SurrealDB's performance optimizations:
- **Direct record access** for ID-based queries (3.4x faster)
- **Native filtering** instead of Python loops
- **Index utilization** for optimized queries
- **Reduced data transfer** - only fetch needed records
- **Memory efficiency** - no large dataset loading

For complete examples, see [test_datagrid_functionality.py](./example_scripts/test_datagrid_functionality.py) and [datagrid_example.py](./example_scripts/datagrid_example.py).

## Query Performance Optimizations

SurrealEngine includes automatic query optimizations that can improve performance by up to 3.4x:

### Automatic ID Optimizations

```python
# These filters are automatically optimized:

# ✅ Optimized: Uses direct record access
users = await User.objects.filter(id__in=[1, 2, 3]).all()
# Becomes: SELECT * FROM user:1, user:2, user:3

# ✅ Optimized: Uses range syntax  
users = await User.objects.filter(id__gte=100, id__lte=200).all()
# Becomes: SELECT * FROM user:100..=200

# ✅ Optimized: Convenience methods
users = await User.objects.get_many([1, 2, 3]).all()
users = await User.objects.get_range(100, 200).all()
```

### Query Analysis Tools

```python
# Analyze query performance
results = await User.objects.filter(age__gt=25)
plan = await results.explain()
print(plan)  # Shows execution plan

# Get index suggestions
suggestions = await User.objects.suggest_indexes()
for suggestion in suggestions:
    print(f"Consider adding index: {suggestion}")
```

### Enhanced Bulk Operations

SurrealEngine provides optimized bulk operations with significant performance improvements:

```python
# Optimized bulk updates using direct record access
updated = await User.objects.get_many([1, 2, 3]).update(status='active')

# Optimized bulk deletes with direct record deletion
deleted = await User.objects.get_many([4, 5, 6]).delete()

# Bulk operations work with various ID formats
deleted = await User.objects.filter(id__in=['user:7', 'user:8']).delete()
```

**Recent Core Fixes:**
- **Fixed bulk delete operations**: Now correctly handles SurrealDB's direct record deletion syntax (`DELETE user:1, user:2`) which returns empty results on success
- **Fixed bulk_create async handling**: Resolved incorrect `asyncio.gather()` usage on synchronous validation methods
- **Validated performance**: All optimization tests now pass (9/9 = 100% success rate) with up to 3.4x performance improvements

For performance testing examples, see [test_performance_optimizations.py](./example_scripts/test_performance_optimizations.py).

### Graph Traversal and Live Queries

SurrealEngine exposes SurrealDB's arrow-based graph traversal and LIVE SELECT streaming API.

- Traverse relationships with bounded depth and direction via QuerySet.traverse(path, max_depth=None, unique=True)
- Subscribe to live changes via QuerySet.live(where=None) yielding {action, data, ts}

Example traversal:

```python
# People and their ordered products, unique results
rows = await QuerySet(Person, conn).traverse("->order->product", unique=True).limit(10).all()
```

Example LIVE subscription:

```python
# Listen for CREATE/UPDATE/DELETE on person table; cancel by breaking or task cancel
async for event in QuerySet(Person, conn).live(where=Q(name__startswith="A")):
    print(event)
    if should_stop():
        break
```

Note: Bounded depth is implemented by repeating a simple single-edge path up to max_depth as a pragmatic approach. SurrealDB's Python SDK currently offers table-level live queries; where filters are applied client-side.

See example_scripts/graph_and_live_example.py for a runnable demo. The script seeds a tiny dataset inline so you can run it as-is.

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
