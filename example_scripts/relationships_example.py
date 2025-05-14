import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from src.surrealengine import (
    Document, StringField, IntField, FloatField, ListField, 
    ReferenceField, RelationField, create_connection
)

# Define document models with relationships
class Author(Document):
    """Author document model."""

    name = StringField(required=True)
    bio = StringField()

    co_authors = Document.relate_to('co_author')

    class Meta:
        collection = "authors"

class Category(Document):
    """Category document model."""

    name = StringField(required=True)
    description = StringField()

    class Meta:
        collection = "categories"

class Book(Document):
    """Book document model with relationships to authors and categories."""

    title = StringField(required=True)
    summary = StringField()
    price = FloatField(required=True)
    page_count = IntField()

    # Reference to the primary author
    primary_author = ReferenceField(Author)

    # References to categories
    categories = ListField(field_type=ReferenceField(Category))

    class Meta:
        collection = "books"

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
        # Create authors
        author1 = Author(name="Jane Doe", bio="Bestselling author of fiction novels")
        author2 = Author(name="John Smith", bio="Award-winning science writer")

        await author1.save()
        await author2.save()
        print(f"Created authors: {author1.name}, {author2.name}")

        # Create categories
        fiction = Category(name="Fiction", description="Fictional literature")
        scifi = Category(name="Science Fiction", description="Fiction with scientific themes")

        await fiction.save()
        await scifi.save()
        print(f"Created categories: {fiction.name}, {scifi.name}")

        # Create books with references
        book1 = Book(
            title="The Great Adventure",
            summary="An epic journey through unknown lands",
            price=14.99,
            page_count=320,
            primary_author=author1,
            categories=[fiction]
        )

        book2 = Book(
            title="Space Explorers",
            summary="The future of interstellar travel",
            price=19.99,
            page_count=420,
            primary_author=author2,
            categories=[fiction, scifi]
        )

        await book1.save()
        await book2.save()
        print(f"Created books: {book1.title}, {book2.title}")

        # Create a relation between authors (co-authors)
        await author1.relate_to("co_author", author2, strength=5)
        print(f"Created co-author relationship between {author1.name} and {author2.name}")

        # Query books by primary author
        books_by_author1 = await Book.objects.filter(primary_author=author1.id).all()
        print(f"Books by {author1.name}: {[book.title for book in books_by_author1]}")

        # Query books by category
        books_in_scifi = await Book.objects.filter(categories__contains=scifi.id).all()
        print(f"Science Fiction books: {[book.title for book in books_in_scifi]}")

        # Fetch related authors
        co_authors = await author1.fetch_relation("co_author")
        print(f"Co-authors of {author1.name}: {co_authors}")

        # Graph traversal: Find all books by co-authors of Jane Doe
        # This demonstrates the power of resolve relation in SurrealDB
        books_by_coauthors = await author1.resolve_relation("co_author")
        print(f"Books by co-authors of {author1.name}: {[book.get('title') for book in books_by_coauthors]}")

    finally:
        # Clean up - delete all created documents
        for book in [book1, book2]:
            await book.delete()

        for category in [fiction, scifi]:
            await category.delete()

        for author in [author1, author2]:
            await author.delete()

        # Disconnect from the database
        await connection.disconnect()
        print("Cleaned up and disconnected from SurrealDB")

# Run the async example
if __name__ == "__main__":
    asyncio.run(main())
