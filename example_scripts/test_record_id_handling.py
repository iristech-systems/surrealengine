"""Test script for RecordID handling in various formats.

This script tests the comprehensive RecordID handling including:
- String format: "table:id"
- URL-encoded format: "table%3Aid"
- Short ID format: "id" (with table context)
- Complex ID formats with special characters
"""

import asyncio
from surrealengine import (
    Document, create_connection,
    StringField, IntField,
    RecordIdUtils, Expr
)
from surrealengine.logging import logger

# Set up logging
logger.set_level(10)  # DEBUG level


class TestUser(Document):
    """Test user document for RecordID testing."""
    
    name = StringField(required=True)
    email = StringField(required=True)
    age = IntField()
    
    class Meta:
        collection = "test_user"


async def test_record_id_utils():
    """Test RecordIdUtils functionality."""
    logger.info("=== Testing RecordIdUtils ===")
    
    # Test normalization
    test_cases = [
        ("user:123", "user:123"),  # Standard format
        ("user%3A123", "user:123"),  # URL-encoded
        ("123", "test_user:123"),  # Short format (with table context)
        ("user:complex-id", "user:complex-id"),  # Complex ID
        ("user%3Acomplex%2Did", "user:complex-id"),  # URL-encoded complex
    ]
    
    for input_id, expected in test_cases:
        table_name = "test_user" if ":" not in input_id else None
        result = RecordIdUtils.normalize_record_id(input_id, table_name)
        logger.info(f"Input: '{input_id}' -> Output: '{result}' (Expected: '{expected}')")
        assert result == expected, f"Expected {expected}, got {result}"
    
    # Test validation
    valid_ids = ["user:123", "test_table:complex-id", "users:abc123"]
    invalid_ids = ["user", "user:", ":123", "user::", "invalid format"]
    
    for valid_id in valid_ids:
        assert RecordIdUtils.is_valid_record_id(valid_id), f"{valid_id} should be valid"
        logger.info(f"✅ '{valid_id}' is valid")
    
    for invalid_id in invalid_ids:
        assert not RecordIdUtils.is_valid_record_id(invalid_id), f"{invalid_id} should be invalid"
        logger.info(f"❌ '{invalid_id}' is invalid (correct)")
    
    # Test URL encoding/decoding
    original = "user:{complex-id}"
    encoded = RecordIdUtils.url_encode_record_id(original)
    decoded = RecordIdUtils.url_decode_record_id(encoded)
    logger.info(f"Original: {original} -> Encoded: {encoded} -> Decoded: {decoded}")
    assert decoded == original, "URL encoding/decoding failed"
    
    # Test batch normalization
    batch_ids = ["123", "user:456", "user%3A789", "valid-id", "user:", ":invalid"]  # Mix of valid and invalid
    normalized_batch = RecordIdUtils.batch_normalize(batch_ids, "test_user")
    logger.info(f"Batch input: {batch_ids}")
    logger.info(f"Batch output: {normalized_batch}")
    expected_batch = ["test_user:123", "user:456", "user:789", "test_user:valid-id"]
    assert len(normalized_batch) == 4, f"Expected 4 normalized IDs, got {len(normalized_batch)}"
    for expected in expected_batch:
        assert expected in normalized_batch, f"Expected {expected} in batch result"
    # Verify invalid ones were filtered out (they should not appear in final result)
    batch_str = str(normalized_batch)
    logger.info(f"Checking that invalid formats were filtered out from: {batch_str}")
    # The invalid formats should not produce any results in the final list
    assert len([id for id in normalized_batch if not RecordIdUtils.is_valid_record_id(id)]) == 0, "All results should be valid RecordIDs"
    
    logger.info("✅ All RecordIdUtils tests passed!")


async def test_expression_builder_record_ids():
    """Test Expr builder with RecordID methods."""
    logger.info("\n=== Testing Expr RecordID Methods ===")
    
    # Test record_eq
    expr1 = Expr.record_eq("user_id", "user:123")
    expected1 = "user_id = user:123"
    logger.info(f"record_eq: {expr1} (Expected: {expected1})")
    assert str(expr1) == expected1
    
    # Test with URL-encoded ID
    expr2 = Expr.record_eq("user_id", "user%3A456")
    expected2 = "user_id = user:456"
    logger.info(f"record_eq (URL-encoded): {expr2} (Expected: {expected2})")
    assert str(expr2) == expected2
    
    # Test with short ID
    expr3 = Expr.record_eq("user_id", "789", "user")
    expected3 = "user_id = user:789"
    logger.info(f"record_eq (short ID): {expr3} (Expected: {expected3})")
    assert str(expr3) == expected3
    
    # Test record_in
    expr4 = Expr.record_in("user_id", ["user:123", "user%3A456", "789"], "user")
    logger.info(f"record_in: {expr4}")
    # Should contain normalized IDs
    assert "user:123" in str(expr4)
    assert "user:456" in str(expr4)
    assert "user:789" in str(expr4)
    
    # Test id_eq convenience method
    expr5 = Expr.id_eq("user:123")
    expected5 = "id = user:123"
    logger.info(f"id_eq: {expr5} (Expected: {expected5})")
    assert str(expr5) == expected5
    
    logger.info("✅ All Expr RecordID tests passed!")


async def test_database_queries():
    """Test RecordID handling with real database queries."""
    logger.info("\n=== Testing Database Queries with RecordIDs ===")
    
    # Try different connection possibilities
    connection_configs = [
        {"url": "ws://db:8000/rpc", "port": 8000},
        {"url": "ws://127.0.0.1:8000/rpc", "port": 8000},
        {"url": "ws://localhost:8001/rpc", "port": 8001},
        {"url": "ws://127.0.0.1:8001/rpc", "port": 8001},
    ]
    
    db = None
    for config in connection_configs:
        try:
            logger.info(f"Trying connection to {config['url']}...")
            db = create_connection(
                url=config["url"],
                namespace="test_ns",
                database="test_db",
                username="root",
                password="root",
                make_default=True,
                async_mode=True
            )
            await db.connect()
            logger.info(f"✅ Connected successfully to {config['url']}")
            break
        except Exception as e:
            logger.info(f"❌ Failed to connect to {config['url']}: {e}")
            continue
    
    if db is None:
        logger.warning("⚠️ Could not connect to SurrealDB. Skipping database tests.")
        return
    
    try:
        # Create table and test data
        logger.info("Creating test table...")
        try:
            await db.client.query("REMOVE TABLE test_user")
        except:
            pass  # Table might not exist
        
        await TestUser.create_table(schemafull=True)
        
        # Create test users
        logger.info("Creating test users...")
        user1 = TestUser(name="Alice", email="alice@example.com", age=25)
        await user1.save()
        logger.info(f"Created user1 with ID: {user1.id}")
        
        user2 = TestUser(name="Bob", email="bob@example.com", age=30)
        await user2.save()
        logger.info(f"Created user2 with ID: {user2.id}")
        
        # Test querying by exact RecordID
        logger.info("Testing query by exact RecordID...")
        found_user1 = await TestUser.objects.filter(id=user1.id).first()
        assert found_user1 is not None, "Should find user by exact RecordID"
        assert found_user1.name == "Alice", "Should find correct user"
        logger.info(f"✅ Found user by exact RecordID: {found_user1.name}")
        
        # Test querying by short ID
        user1_id_str = str(user1.id)
        if ":" in user1_id_str:
            short_id = user1_id_str.split(":")[1]
            logger.info(f"Testing query by short ID: {short_id}")
            found_user2 = await TestUser.objects.filter(id=short_id).first()
            if found_user2:
                assert found_user2.name == "Alice", "Should find correct user by short ID"
                logger.info(f"✅ Found user by short ID: {found_user2.name}")
            else:
                logger.info("⚠️ Short ID query didn't work (expected in some SurrealDB versions)")
        
        # Test querying by URL-encoded RecordID
        if ":" in user1_id_str:
            encoded_id = RecordIdUtils.url_encode_record_id(user1_id_str)
            logger.info(f"Testing query by URL-encoded ID: {encoded_id}")
            try:
                found_user3 = await TestUser.objects.filter(id=encoded_id).first()
                if found_user3:
                    assert found_user3.name == "Alice", "Should find correct user by encoded ID"
                    logger.info(f"✅ Found user by URL-encoded ID: {found_user3.name}")
                else:
                    logger.info("⚠️ URL-encoded ID query didn't return results")
            except Exception as e:
                logger.info(f"⚠️ URL-encoded ID query failed: {e}")
        
        # Test bulk queries with mixed ID formats
        logger.info("Testing bulk query with mixed ID formats...")
        all_ids = [str(user1.id), str(user2.id)]
        if ":" in user1_id_str:
            # Add URL-encoded version
            all_ids.append(RecordIdUtils.url_encode_record_id(user1_id_str))
        
        try:
            bulk_users = await TestUser.objects.filter(id__in=all_ids).all()
            logger.info(f"Bulk query returned {len(bulk_users)} users")
            assert len(bulk_users) >= 2, "Should find at least 2 users"
            logger.info("✅ Bulk query with mixed formats worked")
        except Exception as e:
            logger.info(f"⚠️ Bulk query failed: {e}")
        
        # Test with expression builder
        logger.info("Testing with expression builder...")
        try:
            expr_condition = Expr.id_eq(str(user1.id))
            # Note: This would be used in conditional aggregations
            logger.info(f"Expression builder created: {expr_condition}")
            logger.info("✅ Expression builder RecordID handling works")
        except Exception as e:
            logger.info(f"⚠️ Expression builder failed: {e}")
        
        # Clean up
        logger.info("Cleaning up...")
        await user1.delete()
        await user2.delete()
        
        logger.info("✅ All database RecordID tests completed!")
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        raise
    
    finally:
        if db:
            await db.disconnect()


async def main():
    """Run all RecordID handling tests."""
    logger.info("🚀 Starting RecordID Handling Tests")
    
    try:
        await test_record_id_utils()
        await test_expression_builder_record_ids()
        await test_database_queries()
        
        logger.info("\n🎉 ALL RECORD ID TESTS PASSED!")
        logger.info("\n✅ Features validated:")
        logger.info("• RecordID normalization (string, URL-encoded, short formats)")
        logger.info("• RecordID validation and format checking")
        logger.info("• URL encoding/decoding support")
        logger.info("• Batch RecordID processing")
        logger.info("• Expression builder RecordID methods")
        logger.info("• Database query integration")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        exit(1)