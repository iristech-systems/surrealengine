"""Test script for conditional aggregation features.

This script demonstrates the new conditional aggregation capabilities:
1. Conditional aggregation functions (CountIf, SumIf, etc.)
2. Pre-aggregation filtering with match()
3. Post-aggregation filtering with having()
4. Complex expressions with the Expr builder
"""

import asyncio
import datetime
from surrealengine import (
    Document, create_connection,
    StringField, IntField, FloatField, DateTimeField,
    Count, Sum, Mean, CountIf, SumIf, MeanIf, MinIf, MaxIf, DistinctCountIf,
    Expr
)
from surrealengine.logging import logger

# Set up logging
logger.set_level(10)  # DEBUG level


class Transaction(Document):
    """Transaction document for testing aggregations."""
    
    user_id = StringField(required=True, indexed=True)
    product_id = StringField(required=True, indexed=True)
    amount = FloatField(required=True)
    status = StringField(required=True, indexed=True)  # 'success', 'failed', 'pending'
    category = StringField(required=True, indexed=True)
    payment_method = StringField(required=True)  # 'credit_card', 'debit_card', 'paypal', 'cash'
    created_at = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        collection = "transaction"


async def main():
    # Connect to SurrealDB
    db = create_connection(
        url="ws://localhost:8001/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True,
        async_mode=True
    )
    await db.connect()

    try:
        # Create table
        logger.info("Creating transaction table...")
        await Transaction.create_table(schemafull=True)
        await Transaction.create_indexes()

        # Create test data
        logger.info("Creating test transactions...")
        transactions = []
        
        # Generate diverse transaction data
        users = ['user1', 'user2', 'user3', 'user4', 'user5']
        products = ['prod_a', 'prod_b', 'prod_c', 'prod_d']
        categories = ['electronics', 'clothing', 'food', 'books']
        statuses = ['success', 'failed', 'pending']
        payment_methods = ['credit_card', 'debit_card', 'paypal', 'cash']
        
        for i in range(100):
            transaction = Transaction(
                user_id=users[i % len(users)],
                product_id=products[i % len(products)],
                amount=10.0 + (i % 20) * 5.0,  # Amounts from 10 to 105
                status=statuses[i % 3] if i % 10 != 0 else 'success',  # More success transactions
                category=categories[i % len(categories)],
                payment_method=payment_methods[i % len(payment_methods)],
                created_at=datetime.datetime.now() - datetime.timedelta(days=i % 30)
            )
            await transaction.save()
            transactions.append(transaction)
        
        logger.info(f"Created {len(transactions)} transactions")

        # Test 1: Basic conditional aggregations
        logger.info("\n=== Test 1: Basic Conditional Aggregations ===")
        result = await Transaction.objects.aggregate() \
            .group(
                by_fields="category",
                total_count=Count(),
                success_count=CountIf("status = 'success'"),
                failed_count=CountIf("status = 'failed'"),
                pending_count=CountIf("status = 'pending'"),
                total_amount=Sum("amount"),
                success_amount=SumIf("amount", "status = 'success'"),
                avg_amount=Mean("amount"),
                avg_success_amount=MeanIf("amount", "status = 'success'")
            ) \
            .sort(total_amount="DESC") \
            .execute()
        
        logger.info("Transaction statistics by category:")
        for stat in result:
            logger.info(f"Category: {stat.get('category')}")
            logger.info(f"  Total: {stat.get('total_count')}, Success: {stat.get('success_count')}, "
                       f"Failed: {stat.get('failed_count')}, Pending: {stat.get('pending_count')}")
            logger.info(f"  Total Amount: ${stat.get('total_amount'):.2f}, "
                       f"Success Amount: ${stat.get('success_amount'):.2f}")
            logger.info(f"  Avg Amount: ${stat.get('avg_amount'):.2f}, "
                       f"Avg Success Amount: ${stat.get('avg_success_amount', 0):.2f}")

        # Test 2: Complex conditions with Expr
        logger.info("\n=== Test 2: Complex Conditions with Expression Builder ===")
        
        # High value successful transactions
        high_value_success = Expr.eq("status", "success") & Expr.gt("amount", 50)
        
        # Credit card or PayPal transactions
        digital_payment = Expr.in_("payment_method", ["credit_card", "paypal"])
        
        result = await Transaction.objects.aggregate() \
            .group(
                by_fields="user_id",
                total_transactions=Count(),
                high_value_success_count=CountIf(str(high_value_success)),
                digital_payment_count=CountIf(str(digital_payment)),
                high_value_digital_count=CountIf(str(high_value_success & digital_payment)),
                total_spent=Sum("amount"),
                high_value_spent=SumIf("amount", str(high_value_success))
            ) \
            .sort(high_value_spent="DESC") \
            .execute()
        
        logger.info("User transaction analysis:")
        for stat in result:
            logger.info(f"User: {stat.get('user_id')}")
            logger.info(f"  Total Transactions: {stat.get('total_transactions')}")
            logger.info(f"  High Value Success: {stat.get('high_value_success_count')}")
            logger.info(f"  Digital Payments: {stat.get('digital_payment_count')}")
            logger.info(f"  High Value Digital: {stat.get('high_value_digital_count')}")
            logger.info(f"  Total Spent: ${stat.get('total_spent'):.2f}")
            logger.info(f"  High Value Spent: ${stat.get('high_value_spent', 0):.2f}")

        # Test 3: Pre-aggregation filtering with match()
        logger.info("\n=== Test 3: Pre-aggregation Filtering with match() ===")
        
        # Only analyze recent successful transactions
        result = await Transaction.objects.aggregate() \
            .match(status="success") \
            .group(
                by_fields="payment_method",
                count=Count(),
                total_amount=Sum("amount"),
                avg_amount=Mean("amount"),
                min_amount=MinIf("amount", "amount > 0"),
                max_amount=MaxIf("amount", "amount < 1000")
            ) \
            .sort(total_amount="DESC") \
            .execute()
        
        logger.info("Successful transactions by payment method:")
        for stat in result:
            logger.info(f"Payment Method: {stat.get('payment_method')}")
            logger.info(f"  Count: {stat.get('count')}, Total: ${stat.get('total_amount'):.2f}")
            logger.info(f"  Average: ${stat.get('avg_amount'):.2f}")
            logger.info(f"  Min (>0): ${stat.get('min_amount', 0):.2f}, "
                       f"Max (<1000): ${stat.get('max_amount', 0):.2f}")

        # Test 4: Post-aggregation filtering with having()
        logger.info("\n=== Test 4: Post-aggregation Filtering with having() ===")
        
        # Find categories with significant transaction volume
        result = await Transaction.objects.aggregate() \
            .group(
                by_fields="category",
                transaction_count=Count(),
                total_revenue=Sum("amount"),
                success_rate=MeanIf("1", "status = 'success'"),
                unique_users=DistinctCountIf("user_id", "status = 'success'")
            ) \
            .having(transaction_count__gte=20, total_revenue__gt=500) \
            .sort(total_revenue="DESC") \
            .execute()
        
        logger.info("High-volume categories:")
        for stat in result:
            logger.info(f"Category: {stat.get('category')}")
            logger.info(f"  Transactions: {stat.get('transaction_count')}")
            logger.info(f"  Revenue: ${stat.get('total_revenue'):.2f}")
            logger.info(f"  Success Rate: {stat.get('success_rate', 0)*100:.1f}%")
            logger.info(f"  Unique Successful Users: {stat.get('unique_users')}")

        # Test 5: Combined match, group, having
        logger.info("\n=== Test 5: Combined match(), group(), and having() ===")
        
        # Complex analysis: Recent high-value transactions by active users
        recent_date = datetime.datetime.now() - datetime.timedelta(days=7)
        
        result = await Transaction.objects.aggregate() \
            .match(status="success", amount__gte=30) \
            .group(
                by_fields=["user_id", "category"],
                transaction_count=Count(),
                total_spent=Sum("amount"),
                avg_transaction=Mean("amount"),
                payment_methods_used=DistinctCountIf("payment_method", "amount > 0")
            ) \
            .having(transaction_count__gte=2, total_spent__gt=100) \
            .sort(total_spent="DESC") \
            .limit(10) \
            .execute()
        
        logger.info("Top user-category combinations (high-value, active):")
        for stat in result:
            logger.info(f"User: {stat.get('user_id')}, Category: {stat.get('category')}")
            logger.info(f"  Transactions: {stat.get('transaction_count')}")
            logger.info(f"  Total Spent: ${stat.get('total_spent'):.2f}")
            logger.info(f"  Avg Transaction: ${stat.get('avg_transaction'):.2f}")
            logger.info(f"  Payment Methods Used: {stat.get('payment_methods_used')}")

        # Clean up
        logger.info("\n=== Cleaning up ===")
        for transaction in transactions:
            await transaction.delete()
        
        logger.info("Test completed successfully!")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

    finally:
        # Close the connection
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())