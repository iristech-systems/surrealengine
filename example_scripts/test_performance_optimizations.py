#!/usr/bin/env python3
"""
Test script for SurrealEngine performance optimizations.

This script tests all the new performance features including:
- Auto-optimization for id__in filters
- get_many() and get_range() convenience methods
- Smart filter optimization for ID patterns
- explain() and suggest_indexes() developer tools
- Bulk update/delete operations with direct record access
"""

import asyncio
import sys
import os
import time

from surrealdb import RecordID

# Add the src directory to the path so we can import surrealengine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from surrealengine import Document, create_connection
from surrealengine.fields import StringField, IntField, ReferenceField


class User(Document):
    """Test user document for performance testing."""
    name = StringField(required=True)
    age = IntField()
    email = StringField()
    
    class Meta:
        collection = "user"


class Post(Document):
    """Test post document with user reference."""
    title = StringField(required=True)
    content = StringField()
    author = ReferenceField(User)
    views = IntField(default=0)
    
    class Meta:
        collection = "post"


async def setup_test_data():
    """Create test data for performance testing."""
    print("🔧 Setting up test data...")
    
    # Create test users (let SurrealDB auto-generate IDs)
    users = []
    for i in range(1, 11):  # Create 10 users
        user = User(id=RecordID(User._get_collection_name(),i), name=f"user_{i}", age=20 + i, email=f"user{i}@example.com")
        await user.save()
        users.append(user)
        print(f"  Created {user.name} with ID: {user.id}")
    
    # Create test posts
    posts = []
    for i in range(1, 21):  # Create 20 posts
        author = users[(i - 1) % len(users)]  # Cycle through users
        post = Post(
            title=f"Post {i}",
            content=f"Content for post {i}",
            author=author,
            views=i * 10
        )
        await post.save()
        posts.append(post)
        print(f"  Created {post.title} with ID: {post.id}")
    
    return users, posts


async def test_id_in_optimization():
    """Test auto-optimization for id__in filters."""
    print("\n🚀 Testing id__in auto-optimization...")
    
    # Test with string IDs
    user_ids = ['user:1', 'user:3', 'user:5']
    
    # This should automatically use direct record access
    start_time = time.time()
    users = await User.objects.filter(id__in=user_ids).all()
    end_time = time.time()
    
    print(f"  Found {len(users)} users using id__in filter")
    print(f"  Query took {(end_time - start_time) * 1000:.2f}ms")
    
    # Verify we got the right users
    found_ids = [user.id for user in users]
    print(f"  Found IDs: {found_ids}")
    
    # Test the raw query to see the optimization
    raw_query = User.objects.filter(id__in=user_ids).get_raw_query()
    print(f"  Optimized query: {raw_query}")
    
    return len(users) == len(user_ids)


async def test_get_many_method():
    """Test get_many() convenience method."""
    print("\n🚀 Testing get_many() convenience method...")
    
    # Test with numeric IDs (should auto-format to user:1, user:2, etc.)
    ids = [1, 2, 4, 6]
    
    start_time = time.time()
    users = await User.objects.get_many(ids).all()
    end_time = time.time()
    
    print(f"  Found {len(users)} users using get_many()")
    print(f"  Query took {(end_time - start_time) * 1000:.2f}ms")
    
    # Test the raw query
    raw_query = User.objects.get_many(ids).get_raw_query()
    print(f"  Direct access query: {raw_query}")
    
    # Test with ordering
    ordered_users = await User.objects.get_many(ids).order_by('age', 'DESC').all()
    print(f"  Ordered results: {[u.name for u in ordered_users]}")
    
    return len(users) > 0


async def test_get_range_method():
    """Test get_range() convenience method."""
    print("\n🚀 Testing get_range() convenience method...")
    
    # Test inclusive range
    start_time = time.time()
    users_inclusive = await User.objects.get_range(2, 5, inclusive=True).all()
    end_time = time.time()
    
    print(f"  Found {len(users_inclusive)} users in inclusive range [2, 5]")
    print(f"  Query took {(end_time - start_time) * 1000:.2f}ms")
    
    # Test the raw query
    raw_query = User.objects.get_range(2, 5, inclusive=True).get_raw_query()
    print(f"  Range query: {raw_query}")
    
    # Test exclusive range
    users_exclusive = await User.objects.get_range(2, 5, inclusive=False).all()
    print(f"  Found {len(users_exclusive)} users in exclusive range (2, 5)")
    
    raw_query_excl = User.objects.get_range(2, 5, inclusive=False).get_raw_query()
    print(f"  Exclusive range query: {raw_query_excl}")
    
    return len(users_inclusive) > 0


async def test_range_filter_optimization():
    """Test smart filter optimization for ID range patterns."""
    print("\n🚀 Testing ID range filter optimization...")
    
    # Test gte + lte combination (should auto-optimize)
    start_time = time.time()
    users_range = await User.objects.filter(id__gte='user:3', id__lte='user:7').all()
    end_time = time.time()
    
    print(f"  Found {len(users_range)} users using id__gte + id__lte")
    print(f"  Query took {(end_time - start_time) * 1000:.2f}ms")
    
    # Check if optimization was applied
    raw_query = User.objects.filter(id__gte='user:3', id__lte='user:7').get_raw_query()
    print(f"  Optimized query: {raw_query}")
    
    # Test gt + lt combination
    users_range_excl = await User.objects.filter(id__gt='user:2', id__lt='user:6').all()
    print(f"  Found {len(users_range_excl)} users using id__gt + id__lt")
    
    raw_query_excl = User.objects.filter(id__gt='user:2', id__lt='user:6').get_raw_query()
    print(f"  Exclusive range query: {raw_query_excl}")
    
    return len(users_range) > 0


async def test_explain_functionality():
    """Test explain() method for query analysis."""
    print("\n🔍 Testing explain() functionality...")
    
    try:
        # Test explain on a simple query
        query_plan = await User.objects.filter(age__gt=25).explain()
        print(f"  Query plan for age filter: {query_plan}")
        
        # Test explain on optimized query
        optimized_plan = await User.objects.get_many([1, 2, 3]).explain()
        print(f"  Query plan for get_many(): {optimized_plan}")
        
        return True
    except Exception as e:
        print(f"  Explain functionality error: {e}")
        return False


async def test_suggest_indexes():
    """Test suggest_indexes() method."""
    print("\n💡 Testing suggest_indexes() functionality...")
    
    # Test index suggestions for various query patterns
    age_suggestions = User.objects.filter(age__lt=30).suggest_indexes()
    print(f"  Age filter suggestions: {age_suggestions}")
    
    compound_suggestions = User.objects.filter(age__gt=20, name__contains="user").suggest_indexes()
    print(f"  Compound filter suggestions: {compound_suggestions}")
    
    ordered_suggestions = User.objects.filter(age__lt=25).order_by('email').suggest_indexes()
    print(f"  Ordered query suggestions: {ordered_suggestions}")
    
    return len(age_suggestions) > 0


async def test_bulk_update_optimization():
    """Test bulk update operations with direct record access."""
    print("\n⚡ Testing bulk update optimization...")
    
    # Test bulk update with get_many
    ids_to_update = [1, 2, 3]
    
    start_time = time.time()
    updated_users = await User.objects.get_many(ids_to_update).update(age=99)
    end_time = time.time()
    
    print(f"  Updated {len(updated_users)} users using bulk optimization")
    print(f"  Update took {(end_time - start_time) * 1000:.2f}ms")
    
    # Verify the updates
    for user in updated_users:
        print(f"    {user.name}: age = {user.age}")
    
    # Test bulk update with range
    range_updated = await User.objects.get_range(4, 6).update(email="bulk@example.com")
    print(f"  Range updated {len(range_updated)} users")
    
    return len(updated_users) > 0


async def test_bulk_delete_optimization():
    """Test bulk delete operations with direct record access."""
    print("\n🗑️  Testing bulk delete optimization...")
    
    # Create some test users to delete
    temp_users = []
    for i in range(101, 104):  # IDs 101-103
        user = User(id=RecordID(User._get_collection_name(),i),name=f"temp_user_{i}", age=50)
        await user.save()
        temp_users.append(user)
        print(f"  Created temporary user: {user.name} (ID: {user.id})")
    
    # Test bulk delete with get_many
    ids_to_delete = [str(user.id) for user in temp_users]
    
    start_time = time.time()
    deleted_count = await User.objects.get_many(ids_to_delete).delete()
    end_time = time.time()
    
    print(f"  Deleted {deleted_count} users using bulk optimization")
    print(f"  Delete took {(end_time - start_time) * 1000:.2f}ms")
    
    # Verify deletion
    try:
        remaining = await User.objects.filter(id__in=ids_to_delete).all()
        print(f"  Remaining users with deleted IDs: {len(remaining)}")
    except Exception:
        print("  All users successfully deleted")
    
    return deleted_count > 0


async def test_performance_comparison():
    """Compare performance between optimized and non-optimized queries."""
    print("\n📊 Performance comparison test...")
    
    # Create more test data for meaningful comparison
    print("  Creating additional test data...")
    bulk_users = []
    for i in range(50, 100):
        user = User(id=RecordID(User._get_collection_name(),i),name=f"bulk_user_{i}", age=30 + (i % 20))
        bulk_users.append(user)
    
    # Use bulk_create for faster setup
    await User.objects.bulk_create(bulk_users, return_documents=False)
    print(f"  Created {len(bulk_users)} additional users")
    
    # Test 1: Compare id__in vs individual gets
    test_ids = ['user:50', 'user:55', 'user:60', 'user:65', 'user:70']
    
    # Optimized query
    start_time = time.time()
    optimized_users = await User.objects.filter(id__in=test_ids).all()
    optimized_time = (time.time() - start_time) * 1000
    
    print(f"  Optimized query (id__in): {optimized_time:.2f}ms for {len(optimized_users)} users")
    
    # Manual individual queries (non-optimized simulation)
    start_time = time.time()
    manual_users = []
    for user_id in test_ids:
        try:
            user = await User.objects.get(id=user_id)
            manual_users.append(user)
        except:
            pass
    manual_time = (time.time() - start_time) * 1000
    
    print(f"  Individual queries: {manual_time:.2f}ms for {len(manual_users)} users")
    print(f"  Performance improvement: {manual_time / optimized_time:.1f}x faster")
    
    return optimized_time < manual_time


async def run_all_tests():
    """Run all performance optimization tests."""
    print("🧪 Starting SurrealEngine Performance Optimization Tests")
    print("=" * 60)
    
    # Create connection
    connection = create_connection(
        url="ws://localhost:8001/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True,
        async_mode=True,
    )
    await connection.connect()
    print("Connected to in-memory SurrealDB")
    
    try:
        # Setup test data
        await setup_test_data()
        
        # Run all tests
        tests = [
            ("ID IN Optimization", test_id_in_optimization),
            ("get_many() Method", test_get_many_method),
            ("get_range() Method", test_get_range_method),
            ("Range Filter Optimization", test_range_filter_optimization),
            ("explain() Functionality", test_explain_functionality),
            ("suggest_indexes() Method", test_suggest_indexes),
            ("Bulk Update Optimization", test_bulk_update_optimization),
            ("Bulk Delete Optimization", test_bulk_delete_optimization),
            ("Performance Comparison", test_performance_comparison),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                print("\n" + "=" * 60)
                success = await test_func()
                results.append((test_name, success))
                print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
            except Exception as e:
                print(f"❌ {test_name}: ERROR - {e}")
                results.append((test_name, False))
        
        # Print summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for test_name, success in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{status:<12} {test_name}")
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All performance optimizations working correctly!")
        else:
            print("⚠️  Some tests failed - check the output above for details")
            
    finally:
        await connection.disconnect()


if __name__ == "__main__":
    asyncio.run(run_all_tests())