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

    class Meta:
        collection = "authors"

# Optional: attach a class-level relation helper after the class is defined
# Use Author.co_authors() to build a RelationQuerySet bound to the Author class
Author.co_authors = Author.relates("co_author")

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
    published_year = IntField()  # Optional here to align with other examples using this field
    isbn = StringField()  # Optional here to be compatible with other examples that may require it

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
        # Ensure tables exist (schemafull) to avoid conflicts and have predictable schema
        try:
            await Author.create_table()
            await Category.create_table()
            await Book.create_table()
        except Exception as e:
            # Tables might already exist
            pass
        
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
            published_year=2021,
            isbn="978-0-00-000000-1",
            primary_author=author1,
            categories=[fiction]
        )

        book2 = Book(
            title="Space Explorers",
            summary="The future of interstellar travel",
            price=19.99,
            page_count=420,
            published_year=2023,
            isbn="978-0-00-000000-2",
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
        # Clean up - delete all created documents (guard against unsaved instances)
        for book in [locals().get('book1'), locals().get('book2')]:
            if book is not None and getattr(book, 'id', None):
                await book.delete()

        for category in [locals().get('fiction'), locals().get('scifi')]:
            if category is not None and getattr(category, 'id', None):
                await category.delete()

        for author in [locals().get('author1'), locals().get('author2')]:
            if author is not None and getattr(author, 'id', None):
                await author.delete()

        # Disconnect from the database
        await connection.disconnect()
        print("Cleaned up and disconnected from SurrealDB")

# Run the async example
if __name__ == "__main__":
    asyncio.run(main())
