import asyncio
import datetime
from surrealengine import (
    Document, RelationDocument, StringField, IntField, FloatField,
    BooleanField, DateTimeField, create_connection
)


# Define a Document class for Person
class Person(Document):
    """A document representing a person."""
    name = StringField(required=True)
    age = IntField(min_value=0)
    email = StringField()

    class Meta:
        collection = "people"


# Define a Document class for Book
class Book(Document):
    """A document representing a book."""
    title = StringField(required=True)
    isbn = StringField()
    published_year = IntField()
    price = FloatField(min_value=0)

    class Meta:
        collection = "books"


# Define a RelationDocument class for AuthorRelation
class AuthorRelation(RelationDocument):
    """A relation document representing an author relationship."""
    date_written = DateTimeField()
    is_primary_author = BooleanField(default=True)

    class Meta:
        collection = "authored"

# Connection pool configuration
POOL_SIZE = 5
MAX_IDLE_TIME = 300  # 5 minutes
CONNECT_TIMEOUT = 10
OPERATION_TIMEOUT = 30
RETRY_LIMIT = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0

async def main():
    # Connect to the database
    connection = create_connection(
        url="ws://db:8000/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True,  # This automatically sets it as the default
        use_pool=True,  # Enable connection pooling
        pool_size=POOL_SIZE,
        max_idle_time=MAX_IDLE_TIME,
        connect_timeout=CONNECT_TIMEOUT,
        operation_timeout=OPERATION_TIMEOUT,
        retry_limit=RETRY_LIMIT,
        retry_delay=RETRY_DELAY,
        retry_backoff=RETRY_BACKOFF,
        validate_on_borrow=True
    )


    await connection.connect()
    print("Connected to SurrealDB")

    try:
        # Create tables
        try:
            await Person.create_table()
            await Book.create_table()
            print("Created tables")
        except Exception as e:
            print(f"Tables might already exist: {e}")

        # Create a person with an embedded address
        person = Person(
            name="John Doe",
            age=35,
            email="john.doe@example.com"
        )
        await person.save()
        print(f"Created person: {person.to_dict()}")

        # Create a book
        book = Book(
            title="The Great Novel",
            isbn="978-3-16-148410-0",
            published_year=2023,
            price=19.99
        )
        await book.save()
        print(f"Created book: {book.to_dict()}")

        # Create a relation between the person and the book
        relation = await AuthorRelation.create_relation(
            person, book,
            date_written=datetime.datetime.now(datetime.UTC),
            is_primary_author=True
        )
        print(f"Created relation: {relation.to_dict()}")

        # Fetch the books authored by the person using relate_to method
        # First create the relation using relate_to
        await person.relate_to("authored", book)
        
        # Query for related books
        print(f"Books authored by {person.name}:")
        print(f"  - {book.title} (ISBN: {book.isbn})")

        # Fetch the relation details using query
        print(f"Author relations for {person.name} - {person.id}:")
        print(f"  - Relation ID: {relation.id} (Primary: {relation.is_primary_author}, Date: {relation.date_written})")

        # Clean up

        print("Deleted person and book")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await connection.disconnect()
        print("Disconnected from SurrealDB")


if __name__ == "__main__":
    asyncio.run(main())