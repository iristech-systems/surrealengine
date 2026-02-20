"""Test script for transaction decorators and context managers."""

import asyncio
import logging
from typing import Tuple

from surrealengine import (
    Document, StringField, IntField, 
    create_connection, transaction, transactional
)

logger = logging.getLogger('surrealengine')
logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)


class Account(Document):
    """Test account document for transaction testing."""
    name = StringField(required=True)
    balance = IntField(default=0)
    
    class Meta:
        collection = "test_account"


@transactional()
async def transfer_funds(from_account: Account, to_account: Account, amount: int) -> Tuple[Account, Account]:
    """Transfer funds using the transactional decorator with query buffering."""
    logger.info(f"Transferring {amount} from {from_account.name} to {to_account.name}...")
    
    # Normally we might reload objects, but doing reads inside the write-behind 
    # proxy currently executes against the real DB synchronously, meaning it won't 
    # see uncommitted writes if we did it mid-transaction.
    # We will just mutate our memory copies and .save() them, which is fully supported.
    from_account.balance -= amount
    to_account.balance += amount
    
    if from_account.balance < 0:
        raise ValueError(f"Insufficient funds in {from_account.name}'s account")
        
    await from_account.save()
    await to_account.save()
    
    return from_account, to_account


async def test_successful_transaction():
    """Test a successful transaction."""
    logger.info("\n=== Testing Successful Transaction ===")
    
    # Create accounts
    alice = Account(name="Alice", balance=1000)
    await alice.save()
    
    bob = Account(name="Bob", balance=500)
    await bob.save()
    
    # Perform transfer
    await transfer_funds(alice, bob, 200)
    
    # Verify results
    alice_final = await Account.objects.get(id=alice.id)
    bob_final = await Account.objects.get(id=bob.id)
    
    logger.info(f"Alice: {alice_final.balance}")
    logger.info(f"Bob: {bob_final.balance}")
    
    assert alice_final.balance == 800, "Alice balance incorrect"
    assert bob_final.balance == 700, "Bob balance incorrect"
    
    logger.info("✅ Successful transaction test passed")


async def test_failed_transaction():
    """Test a failed transaction that should rollback."""
    logger.info("\n=== Testing Failed Transaction (Rollback) ===")
    
    # Create accounts
    charlie = Account(name="Charlie", balance=100)
    await charlie.save()
    
    dave = Account(name="Dave", balance=500)
    await dave.save()
    
    logger.info("Attempting overdraft transfer...")
    try:
        await transfer_funds(charlie, dave, 200)
    except ValueError as e:
        logger.info(f"Caught expected error: {e}")
        
    # Verify results - should be unchanged
    charlie_final = await Account.objects.get(id=charlie.id)
    dave_final = await Account.objects.get(id=dave.id)
    
    logger.info(f"Charlie: {charlie_final.balance}")
    logger.info(f"Dave: {dave_final.balance}")
    
    assert charlie_final.balance == 100, "Charlie balance was modified during rollback!"
    assert dave_final.balance == 500, "Dave balance was modified during rollback!"
    
    logger.info("✅ Failed transaction rollback test passed")


async def test_context_manager():
    """Test the context manager directly."""
    logger.info("\n=== Testing Context Manager ===")
    
    eve = Account(name="Eve", balance=1000)
    await eve.save()
    
    logger.info("Starting context block...")
    try:
        async with transaction():
            eve.balance -= 500
            await eve.save()
            
            logger.info("Raising exception to trigger CANCEL TRANSACTION")
            raise RuntimeError("Something bad happened!")
    except RuntimeError:
        pass
        
    eve_final = await Account.objects.get(id=eve.id)
    logger.info(f"Eve balance: {eve_final.balance}")
    
    assert eve_final.balance == 1000, "Context Manager failed to rollback!"
    
    logger.info("✅ Context Manager rollback test passed")


async def main():
    logger.info("🚀 Starting Transaction tests")
    db = create_connection(
        url="memory://",
        namespace="test_ns",
        database="test_db",
        make_default=True,
    )
    
    try:
        await db.connect()
        logger.info("✅ Connected to SurrealDB")
        
        # Cleanup
        try:
            await db.client.query("REMOVE TABLE test_account")
        except:
            pass
            
        await Account.create_table()
        
        await test_successful_transaction()
        await test_failed_transaction()
        await test_context_manager()
        
        logger.info("\n🎉 All transaction tests passed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
