
# SurrealEngine

SurrealEngine is an async Object-Document Mapper (ODM) for SurrealDB, providing a Pythonic interface for working with SurrealDB databases.

> **Important Note**: I have been testing SurrealDB in certain use-cases and am not a long time user or well verse in the deep down details of the system. I focus on user ergonomics over direct compatibility with the core python SurrealDB SDK.  This means much of the module translates queries directly into SurrealQL vs operating through SDK abstraction.  Currently, schema registration with SurrealDB is not implemented. The ODM provides Python-side validation and structure only.  

## Requirements

- Python >= 3.13 (Built and Tested on)
- surrealdb >= 1.0.3  (Built and Tested on)

## Installation
```bash
pip install surrealengine
``` 

## Quick Start

### Connecting to SurrealDB
> **Important Note**:  Connection management is done through the Python SDK and is established within the context/workspace. Initialization and Import of SurrealEngine is not required to use the system, better documentation of flows soon to come.
```python
from surrealengine import SurrealEngineConnection
conn = SurrealEngineConnection(
    url="wss://CONNECTION_STRING",
    namespace="NAMESPACE",
    database="DATABASE_NAME",
    username="USERNAME",
    password="PASSWORD",
)
await conn.connect()
``` 
OR
> **Important Note**: SurrealEngine import allows usage without Document Class declaration and no pythonic validation.  
```python
from surrealengine import SurrealEngineConnection, SurrealEngine
conn = SurrealEngineConnection(
    url="wss://CONNECTION_STRING",
    namespace="NAMESPACE",
    database="DATABASE_NAME",
    username="USERNAME",
    password="PASSWORD",
)
await conn.connect()
db = SurrealEngine(conn)
``` 
### Basic Document Model
```python
class Person(Document):
    name = StringField(required=True)
    age = IntField()

    class Meta:
        collection = "person"

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
```python
# Creating a document
jane = await Person(name="Jane", age=30).save()
jane.id
jane.name
jane.age
# Get a document
person = await Person.objects.get(name="Jane")
# Access fields
person.id
person.name
person.age
# Get documents
Person(name="Jane") # Just joining team SurrealFan sooo could be problematic with core SurrealDB functionality.  Also should be awaitable, but is not.
await Person.objects(name="Jane")
await Person.objects.filter(name="Jane").all()
# Get without schema declaration
await db.person(name="Jane")
await db.person.objects(name="Jane")
await conn.client.query("SELECT * FROM person WHERE name = 'Jane'")
```

### Working with Relations

Create and relate documents:
```python
# Create an actor
actor = Actor(
    name="Tom Hanks",
    birth_date="1956-07-09",
    nationality="American"
)
await actor.save()

# Create a movie
movie = Movie(
    title="Forrest Gump",
    release_year=1994,
    rating=8.8,
    director="Robert Zemeckis"
)
await movie.save()

await actor.relate_to(
        'acted_in',
        movie,
        role="Forrest Gump",
        award="Academy Award for Best Actor"
    )
``` 

### Working with Relations

```python
# Fetch actor
actor = await Actor.objects.get(name="Tom Hanks")
actor.to_dict()
{'birth_date': '1956-07-09T00:00:00',
 'name': 'Tom Hanks',
 'nationality': 'American'}
# Get relation data
relations = await actor.fetch_relation('acted_in')
{'id': RecordID(table_name=actor, record_id=q33bto59e6b49wjoie12),
 'related': [RecordID(table_name=movie, record_id=4gys3es1yv8bld17xc67),
  RecordID(table_name=movie, record_id=3efb85z1xxm32au81gi9)]}
# Resolve related documents
movies = await actor.resolve_relation('acted_in')
[{'director': 'Robert Zemeckis',
  'id': RecordID(table_name=movie, record_id=4gys3es1yv8bld17xc67),
  'rating': 8.8,
  'release_year': 1994,
  'title': 'Forrest Gump'},
 {'director': 'Robert Zemeckis',
  'id': RecordID(table_name=movie, record_id=3efb85z1xxm32au81gi9),
  'rating': 8.8,
  'release_year': 2025,
  'title': 'New Movie'}]
```

### Querying
``` python
# Using the document class
result1 = await Person.objects(age=30)

# Using the database engine (Without Model declaration)
result2 = await db.person.objects.filter(age=30).all()
```
## Available Fields
- `StringField`: For text data
- : For integer values `IntField`
- `FloatField`: For floating-point numbers with optional min/max values
- `DateTimeField`: For datetime values
- `BooleanField`: For true/false values
- : For arrays `ListField`
- : For nested objects `DictField`
- : For document references `ReferenceField`
- : For graph relationships `RelationField`
- `GeometryField`: For geometric data

## Features in Development
- Schema registration with SurrealDB
- Migration support
- Advanced indexing
- Bulk operations optimization
- Transaction support
- More complex graph queries

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
## License
[Your License Here]
