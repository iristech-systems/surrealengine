import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from src.surrealengine import (
    Document, RelationDocument, StringField, IntField, FloatField,
    BooleanField, DateTimeField, ListField, ReferenceField,
    create_connection
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


async def main():
    # Connect to the database
    connection = create_connection(
        url="ws://db:8000/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True
    )

    await connection.connect()
    print("Connected to SurrealDB")

    try:
        # Create tables
        await Person.create_table(connection)
        await Book.create_table(connection)

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
            date_written="2022-01-15T00:00:00Z",
            is_primary_author=True
        )
        print(f"Created relation: {relation.to_dict()}")

        # Fetch the books authored by the person
        authored_books = await person.resolve_relation("authored", Book)
        print(f"Books authored by {person.name}:")
        for authored_book in authored_books:
            print(f"  - {authored_book.get('title')} (ISBN: {authored_book.get('isbn')})")

        # Fetch the relation details
        author_relations = await AuthorRelation.find_by_in_document(person.id)
        print(f"Author relations for {person.name} - {person.id}:")
        for rel in author_relations:
            print(rel.to_dict())
            print(f"  - {rel.id} (Primary: {rel.is_primary_author}, Date: {rel.date_written})")

        # Clean up
        await person.delete()
        await book.delete()
        print("Deleted person and book")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Disconnected from SurrealDB")


if __name__ == "__main__":
    asyncio.run(main())