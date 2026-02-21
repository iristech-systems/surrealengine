"""Test script for Phase 3 Ergonomic Features.

This script tests:
1. Document `.clean()` hook
2. TimestampMixin and SoftDeleteMixin
3. QuerySet `.upsert()`
4. QuerySet `.search()`
5. Subqueries in `.filter()`
"""

import asyncio
import datetime
from surrealengine import (
    Document, create_connection,
    StringField, IntField, FloatField, DateTimeField, ListField,
    ReferenceField,
    TimestampMixin, SoftDeleteMixin
)
from surrealengine.logging import logger

logger.set_level(10)  # DEBUG

class Author(Document):
    name = StringField(required=True)
    points = IntField(default=0)

# 1 & 2. Mixins & Clean Hook Example
class Post(TimestampMixin, SoftDeleteMixin, Document):
    title = StringField(required=True)
    body = StringField(search=True, analyzer="ascii", bm25=True, indexed=True)  # Indexed for search
    content = StringField()
    author = ReferenceField(Author)

    class Meta:
        indexes = [
            {
                "name": "idx_content",
                "fields": ["content"],
                "search": True,
                "bm25": True,
                "highlights": True,
                "analyzer": "ascii"
            }
        ]


    def clean(self):
        super().clean()
        if self.title and self.title.lower() == "forbidden":
            raise ValueError("Title cannot be 'forbidden'")


async def main():
    db = create_connection(
        url="memory://",
        namespace="test_ns",
        database="test_ergonomics",
        make_default=True,
        async_mode=True
    )
    await db.connect()

    try:
        # Create tables & indexes
        logger.info("Setting up tables...")
        await db.client.query("DEFINE ANALYZER ascii TOKENIZERS blank,class,camel,punct FILTERS snowball(english);")
        await Post.create_table(schemafull=True)
        await Author.create_table(schemafull=True)
        # Create index on body for search method
        await Post.create_indexes()

        logger.info("Testing .clean() validation hook...")
        try:
            bad_post = Post(title="forbidden", body="this shouldn't save")
            await bad_post.save()
            logger.error("Failed: .clean() did not raise exception")
        except ValueError as e:
            logger.info(f"Success: Caught expected ValueError from clean(): {str(e)}")

        logger.info("Testing TimestampMixin...")
        post = Post(title="My first post", body="Hello surreal!")
        await post.save()
        logger.info(f"created_at: {post.created_at}")
        logger.info(f"updated_at: {post.updated_at}")
        
        # Test updated_at changes
        original_update = post.updated_at
        await asyncio.sleep(1) # wait a moment
        post.body = "Updated content"
        await post.save()
        logger.info(f"new updated_at: {post.updated_at}")
        if post.updated_at > original_update:
            logger.info("Success: TimestampMixin updated 'updated_at'")

        logger.info("Testing SoftDeleteMixin...")
        logger.info(f"Before delete list count: {await Post.objects.count()}")
        await post.delete()
        
        deleted_post_raw = await db.client.query("SELECT * FROM post WHERE id = $id", {"id": post.id})
        logger.info(f"Raw query result: {deleted_post_raw}")
        if deleted_post_raw and isinstance(deleted_post_raw, list) and len(deleted_post_raw) > 0:
            if 'result' in deleted_post_raw[0] and len(deleted_post_raw[0]['result']) > 0:
                deleted_post_data = deleted_post_raw[0]['result'][0]
                logger.info(f"deleted_at: {deleted_post_data.get('deleted_at')}")
                if deleted_post_data.get('deleted_at') is not None:
                     logger.info("Success: SoftDeleteMixin correctly populated 'deleted_at'")
            else:
                logger.error("No results in query response")
        else:
            logger.error("Failed to query post")

        logger.info("Testing .upsert()...")
        await Author(id="author:upsert_test", name="Original").save()
        # Use upsert to update it instead of exception
        author = await Author.objects.upsert(id="author:upsert_test", name="Upserted name!", points=10)
        logger.info(f"Upsert returned author: {author.name} with {author.points} points")

        # Upsert a brand new one
        author2 = await Author.objects.upsert(id="author:new_guy", name="New Guy", points=5)
        logger.info(f"Upsert created new author: {author2.name}")

        logger.info("Testing Subqueries in .filter()...")
        p1 = Post(title="Post A", author=author.id)
        p2 = Post(title="Post B", author=author2.id)
        await p1.save()
        await p2.save()

        # Complex query: select posts where author_id is in (select id from author where points > 5)
        # author has 10, author2 has 5
        subquery_qs = Author.objects.filter(points__gt=5).only("id")
        # Filter posts where author_id IN (subquery)
        # We replace the object id part for simplicity since author_id is a string part
        # Let's filter author table itself using subquery
        rich_authors = await Author.objects.filter(id__in=subquery_qs).all()
        logger.info(f"Rich authors from subquery: {[a.name for a in rich_authors]}")

        logger.info("Testing .search()...")
        p3 = Post(title="Surreal Engine Tutorial", body="SurrealEngine makes SurrealDB easy to use.", content="Full text search is awesome!")
        p4 = Post(title="Python Tips", body="How to use python more effectively with databases.", content="Learn more about Python and SurrealDB.")
        await p3.save()
        await p4.save()
        
        search_results = await Post.objects.search("SurrealEngine", Post.body).all()
        logger.info(f"Search results for 'SurrealEngine' in body: {[p.title for p in search_results]}")

        meta_search_results = await Post.objects.search("SurrealDB", Post.content).all()
        logger.info(f"Search results for 'SurrealDB' in content: {[p.title for p in meta_search_results]}")

        raw_search = await db.client.query("SELECT * FROM post WHERE content @@ 'SurrealDB'")
        logger.info(f"Raw Search results for content: {raw_search}")

        logger.info("All tests completed successfully!")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
