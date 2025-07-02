"""
Example demonstrating the new query expression functionality in SurrealEngine.

This script shows how to use Q objects and QueryExpressions for complex queries
including fetch with objects(query) and filter(query) syntax.
"""

import asyncio
from surrealengine import (
    Document, StringField, IntField, BooleanField, ReferenceField,
    create_connection, Q, QueryExpression
)


# Define document models
class User(Document):
    """User document model."""
    
    username = StringField(required=True)
    email = StringField(required=True)
    age = IntField(min_value=0)
    active = BooleanField(default=True)
    
    class Meta:
        collection = "users"


class Post(Document):
    """Post document model with reference to User."""
    
    title = StringField(required=True)
    content = StringField()
    author = ReferenceField(User, required=True)
    published = BooleanField(default=False)
    views = IntField(default=0)
    
    class Meta:
        collection = "posts"


async def main():
    # Connect to the database
    connection = create_connection(
        url="ws://localhost:8001/rpc",
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
        await User.create_table()
        await Post.create_table()
        print("Created tables")
        
        # Create some test data
        user1 = User(username="alice", email="alice@example.com", age=25, active=True)
        user2 = User(username="bob", email="bob@example.com", age=30, active=False)
        user3 = User(username="charlie", email="charlie@example.com", age=35, active=True)
        
        await user1.save()
        await user2.save()
        await user3.save()
        print("Created test users")
        
        post1 = Post(title="Hello World", content="First post", author=user1, published=True, views=100)
        post2 = Post(title="Another Post", content="Second post", author=user2, published=False, views=50)
        post3 = Post(title="Great Content", content="Third post", author=user1, published=True, views=200)
        
        await post1.save()
        await post2.save()
        await post3.save()
        print("Created test posts")
        
        print("\n=== Testing Q Object Functionality ===")
        
        # 1. Simple Q object usage
        print("\n1. Simple Q object with age filter:")
        q1 = Q(age__gt=25)
        users = await User.objects.filter(q1).all()
        print(f"Users with age > 25: {[u.username for u in users]}")
        
        # 2. Complex Q objects with AND/OR
        print("\n2. Complex Q object with AND/OR:")
        q2 = Q(age__gt=25) & Q(active=True)  # AND condition
        active_older_users = await User.objects.filter(q2).all()
        print(f"Active users with age > 25: {[u.username for u in active_older_users]}")
        
        q3 = Q(age__lt=30) | Q(username="charlie")  # OR condition
        users_or = await User.objects.filter(q3).all()
        print(f"Users with age < 30 OR username='charlie': {[u.username for u in users_or]}")
        
        # 3. Using NOT
        print("\n3. Using NOT with Q objects:")
        q4 = ~Q(active=True)  # NOT active
        inactive_users = await User.objects.filter(q4).all()
        print(f"Inactive users: {[u.username for u in inactive_users]}")
        
        # 4. Raw query with Q.raw()
        print("\n4. Raw query with Q.raw():")
        q5 = Q.raw("age > 20 AND username CONTAINS 'a'")
        users_raw = await User.objects.filter(q5).all()
        print(f"Users from raw query: {[u.username for u in users_raw]}")
        
        print("\n=== Testing objects(query) Functionality ===")
        
        # 5. Using objects(query) syntax
        print("\n5. Using objects(query) directly:")
        query = Q(published=True) & Q(views__gt=75)
        popular_posts = await Post.objects(query)
        print(f"Popular published posts: {[p.title for p in popular_posts]}")
        
        # 6. Combining objects(query) with additional filters
        print("\n6. Combining objects(query) with additional filters:")
        base_query = Q(published=True)
        high_view_posts = await Post.objects(base_query, views__gt=150)
        print(f"High-view published posts: {[p.title for p in high_view_posts]}")
        
        print("\n=== Testing QueryExpression with FETCH ===")
        
        # 7. QueryExpression with FETCH for dereferencing
        print("\n7. QueryExpression with FETCH:")
        expr = QueryExpression(where=Q(published=True)).fetch("author")
        posts_with_authors = await Post.objects.filter(expr).all()
        
        for post in posts_with_authors:
            # The author should be dereferenced due to FETCH
            author_name = post.author.username if hasattr(post.author, 'username') else str(post.author)
            print(f"Post: '{post.title}' by {author_name}")
        
        # 8. Complex QueryExpression with multiple clauses
        print("\n8. Complex QueryExpression with ORDER BY and LIMIT:")
        complex_expr = (QueryExpression(where=Q(active=True))
                       .order_by("age", "DESC")
                       .limit(2))
        
        top_users = await User.objects.filter(complex_expr).all()
        print(f"Top 2 oldest active users: {[(u.username, u.age) for u in top_users]}")
        
        print("\n=== Testing Advanced Query Combinations ===")
        
        # 9. Multiple Q objects combined
        print("\n9. Multiple Q objects combined:")
        young = Q(age__lt=30)
        active = Q(active=True)
        has_a = Q(username__contains="a")
        
        complex_query = (young & active) | has_a
        result_users = await User.objects.filter(complex_query).all()
        print(f"Complex query result: {[u.username for u in result_users]}")
        
        # 10. Using Q with different operators
        print("\n10. Various Q object operators:")
        queries = [
            Q(age__in=[25, 30]),  # IN operator
            Q(username__startswith="a"),  # STARTSWITH
            Q(email__contains="example"),  # CONTAINS
            Q(age__gte=25) & Q(age__lte=35),  # Range
        ]
        
        for i, query in enumerate(queries, 1):
            users = await User.objects.filter(query).all()
            print(f"Query {i} result: {[u.username for u in users]}")
        
        print("\n=== All examples completed successfully! ===")
        
        # Clean up
        all_users = await User.objects.all()
        all_posts = await Post.objects.all()
        
        for post in all_posts:
            await post.delete()
        for user in all_users:
            await user.delete()
        print("Cleaned up test data")
        
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await connection.disconnect()
        print("Disconnected from SurrealDB")


if __name__ == "__main__":
    asyncio.run(main())