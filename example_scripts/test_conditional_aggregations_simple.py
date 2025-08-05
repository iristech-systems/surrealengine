"""Simple test script for conditional aggregation features.

This script provides a straightforward demonstration of the new conditional
aggregation capabilities with easy-to-verify results.
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


class Sale(Document):
    """Simple sale document for testing."""
    
    store = StringField(required=True, indexed=True)
    product = StringField(required=True, indexed=True)
    amount = FloatField(required=True)
    quantity = IntField(required=True)
    status = StringField(required=True)  # 'completed', 'refunded', 'pending'
    customer_type = StringField(required=True)  # 'regular', 'premium', 'new'
    sale_date = DateTimeField(default=datetime.datetime.now)
    
    class Meta:
        collection = "sale"


async def create_test_data():
    """Create simple, predictable test data."""
    sales_data = [
        # Store A - 10 sales
        {"store": "A", "product": "laptop", "amount": 1000, "quantity": 1, "status": "completed", "customer_type": "premium"},
        {"store": "A", "product": "laptop", "amount": 1200, "quantity": 1, "status": "completed", "customer_type": "regular"},
        {"store": "A", "product": "mouse", "amount": 30, "quantity": 2, "status": "completed", "customer_type": "new"},
        {"store": "A", "product": "keyboard", "amount": 80, "quantity": 1, "status": "refunded", "customer_type": "regular"},
        {"store": "A", "product": "monitor", "amount": 300, "quantity": 1, "status": "completed", "customer_type": "premium"},
        {"store": "A", "product": "laptop", "amount": 1100, "quantity": 1, "status": "pending", "customer_type": "new"},
        {"store": "A", "product": "mouse", "amount": 25, "quantity": 1, "status": "completed", "customer_type": "regular"},
        {"store": "A", "product": "keyboard", "amount": 90, "quantity": 1, "status": "completed", "customer_type": "premium"},
        {"store": "A", "product": "monitor", "amount": 350, "quantity": 1, "status": "refunded", "customer_type": "regular"},
        {"store": "A", "product": "laptop", "amount": 950, "quantity": 1, "status": "completed", "customer_type": "new"},
        
        # Store B - 10 sales
        {"store": "B", "product": "laptop", "amount": 900, "quantity": 1, "status": "completed", "customer_type": "regular"},
        {"store": "B", "product": "laptop", "amount": 1100, "quantity": 1, "status": "completed", "customer_type": "premium"},
        {"store": "B", "product": "mouse", "amount": 35, "quantity": 3, "status": "completed", "customer_type": "new"},
        {"store": "B", "product": "keyboard", "amount": 75, "quantity": 1, "status": "completed", "customer_type": "regular"},
        {"store": "B", "product": "monitor", "amount": 280, "quantity": 1, "status": "pending", "customer_type": "premium"},
        {"store": "B", "product": "laptop", "amount": 1300, "quantity": 1, "status": "completed", "customer_type": "premium"},
        {"store": "B", "product": "mouse", "amount": 40, "quantity": 2, "status": "refunded", "customer_type": "regular"},
        {"store": "B", "product": "keyboard", "amount": 85, "quantity": 1, "status": "completed", "customer_type": "new"},
        {"store": "B", "product": "monitor", "amount": 320, "quantity": 1, "status": "completed", "customer_type": "regular"},
        {"store": "B", "product": "laptop", "amount": 1050, "quantity": 1, "status": "completed", "customer_type": "new"},
    ]
    
    sales = []
    for data in sales_data:
        sale = Sale(**data)
        await sale.save()
        sales.append(sale)
    
    return sales


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
        logger.info("Creating sale table...")
        await Sale.create_table(schemafull=True)
        await Sale.create_indexes()

        # Create test data
        logger.info("Creating test sales data...")
        sales = await create_test_data()
        logger.info(f"Created {len(sales)} sales records")

        # Test 1: Basic conditional counting
        logger.info("\n=== Test 1: Basic Conditional Counting ===")
        result = await Sale.objects.aggregate() \
            .group(
                by_fields="store",
                total_sales=Count(),
                completed_sales=CountIf("status = 'completed'"),
                refunded_sales=CountIf("status = 'refunded'"),
                pending_sales=CountIf("status = 'pending'"),
                premium_customers=CountIf("customer_type = 'premium'"),
                high_value_sales=CountIf("amount > 500")
            ) \
            .sort(store="ASC") \
            .execute()
        
        logger.info("Sales count by store:")
        for stat in result:
            logger.info(f"\nStore {stat.get('store')}:")
            logger.info(f"  Total Sales: {stat.get('total_sales')}")
            logger.info(f"  Completed: {stat.get('completed_sales')}, Refunded: {stat.get('refunded_sales')}, Pending: {stat.get('pending_sales')}")
            logger.info(f"  Premium Customers: {stat.get('premium_customers')}")
            logger.info(f"  High Value Sales (>500): {stat.get('high_value_sales')}")

        # Test 2: Conditional sums and averages
        logger.info("\n=== Test 2: Conditional Sums and Averages ===")
        result = await Sale.objects.aggregate() \
            .group(
                by_fields="product",
                total_revenue=Sum("amount"),
                completed_revenue=SumIf("amount", "status = 'completed'"),
                refunded_amount=SumIf("amount", "status = 'refunded'"),
                avg_sale_amount=Mean("amount"),
                avg_completed_amount=MeanIf("amount", "status = 'completed'"),
                total_quantity=Sum("quantity"),
                completed_quantity=SumIf("quantity", "status = 'completed'")
            ) \
            .sort(total_revenue="DESC") \
            .execute()
        
        logger.info("Revenue by product:")
        for stat in result:
            logger.info(f"\nProduct: {stat.get('product')}")
            logger.info(f"  Total Revenue: ${stat.get('total_revenue'):.2f}")
            logger.info(f"  Completed Revenue: ${stat.get('completed_revenue', 0):.2f}")
            logger.info(f"  Refunded Amount: ${stat.get('refunded_amount', 0):.2f}")
            logger.info(f"  Avg Sale: ${stat.get('avg_sale_amount'):.2f}, Avg Completed: ${stat.get('avg_completed_amount', 0):.2f}")
            logger.info(f"  Total Quantity: {stat.get('total_quantity')}, Completed Quantity: {stat.get('completed_quantity', 0)}")

        # Test 3: Using Expr for complex conditions
        logger.info("\n=== Test 3: Complex Conditions with Expr ===")
        
        # High value completed sales
        high_value_completed = Expr.eq("status", "completed") & Expr.gt("amount", 100)
        
        # Premium or regular customers
        established_customers = Expr.in_("customer_type", ["premium", "regular"])
        
        result = await Sale.objects.aggregate() \
            .group(
                by_fields="store",
                total_sales=Count(),
                high_value_completed_count=CountIf(str(high_value_completed)),
                high_value_completed_revenue=SumIf("amount", str(high_value_completed)),
                established_customer_sales=CountIf(str(established_customers)),
                new_customer_sales=CountIf("customer_type = 'new'")
            ) \
            .execute()
        
        logger.info("Complex condition analysis by store:")
        for stat in result:
            logger.info(f"\nStore {stat.get('store')}:")
            logger.info(f"  High Value Completed Sales (>$100 & completed): {stat.get('high_value_completed_count')}")
            logger.info(f"  High Value Completed Revenue: ${stat.get('high_value_completed_revenue', 0):.2f}")
            logger.info(f"  Established Customer Sales: {stat.get('established_customer_sales')}")
            logger.info(f"  New Customer Sales: {stat.get('new_customer_sales')}")

        # Test 4: Pre-aggregation filtering with match()
        logger.info("\n=== Test 4: Pre-aggregation Filtering with match() ===")
        
        # Only analyze completed sales
        result = await Sale.objects.aggregate() \
            .match(status="completed") \
            .group(
                by_fields="customer_type",
                count=Count(),
                total_revenue=Sum("amount"),
                avg_revenue=Mean("amount"),
                min_sale=MinIf("amount", "amount > 0"),
                max_sale=MaxIf("amount", "amount < 10000"),
                unique_products=DistinctCountIf("product", "amount > 50")
            ) \
            .sort(total_revenue="DESC") \
            .execute()
        
        logger.info("Completed sales by customer type:")
        for stat in result:
            logger.info(f"\nCustomer Type: {stat.get('customer_type')}")
            logger.info(f"  Count: {stat.get('count')}, Revenue: ${stat.get('total_revenue'):.2f}")
            logger.info(f"  Average: ${stat.get('avg_revenue'):.2f}")
            logger.info(f"  Min Sale: ${stat.get('min_sale', 0):.2f}, Max Sale: ${stat.get('max_sale', 0):.2f}")
            logger.info(f"  Unique Products (>$50): {stat.get('unique_products', 0)}")

        # Test 5: Post-aggregation filtering with having()
        logger.info("\n=== Test 5: Post-aggregation Filtering with having() ===")
        
        # Find products with significant sales
        result = await Sale.objects.aggregate() \
            .group(
                by_fields="product",
                sale_count=Count(),
                total_revenue=Sum("amount"),
                completed_count=CountIf("status = 'completed'"),
                completion_rate=MeanIf("1", "status = 'completed'")
            ) \
            .having(sale_count__gte=4, total_revenue__gt=1000) \
            .sort(total_revenue="DESC") \
            .execute()
        
        logger.info("High-volume products:")
        for stat in result:
            logger.info(f"\nProduct: {stat.get('product')}")
            logger.info(f"  Sales: {stat.get('sale_count')}, Revenue: ${stat.get('total_revenue'):.2f}")
            logger.info(f"  Completed: {stat.get('completed_count')}")
            logger.info(f"  Completion Rate: {stat.get('completion_rate', 0)*100:.1f}%")

        # Test 6: Combined match, group, and having
        logger.info("\n=== Test 6: Combined match(), group(), and having() ===")
        
        # Analyze high-value sales by store and product
        result = await Sale.objects.aggregate() \
            .match(amount__gte=100) \
            .group(
                by_fields=["store", "product"],
                count=Count(),
                revenue=Sum("amount"),
                avg_amount=Mean("amount"),
                completed_count=CountIf("status = 'completed'"),
                customer_types=DistinctCountIf("customer_type", "status = 'completed'")
            ) \
            .having(count__gte=2, revenue__gt=500) \
            .sort(revenue="DESC") \
            .limit(5) \
            .execute()
        
        logger.info("Top store-product combinations (high-value):")
        for stat in result:
            logger.info(f"\nStore {stat.get('store')} - {stat.get('product')}:")
            logger.info(f"  Sales: {stat.get('count')}, Revenue: ${stat.get('revenue'):.2f}")
            logger.info(f"  Average: ${stat.get('avg_amount'):.2f}")
            logger.info(f"  Completed: {stat.get('completed_count')}")
            logger.info(f"  Customer Type Diversity: {stat.get('customer_types', 0)}")

        # Test 7: Min/Max conditional aggregations
        logger.info("\n=== Test 7: Conditional Min/Max Aggregations ===")
        
        result = await Sale.objects.aggregate() \
            .group(
                by_fields="store",
                min_completed_sale=MinIf("amount", "status = 'completed'"),
                max_completed_sale=MaxIf("amount", "status = 'completed'"),
                min_laptop_price=MinIf("amount", "product = 'laptop'"),
                max_laptop_price=MaxIf("amount", "product = 'laptop'")
            ) \
            .execute()
        
        logger.info("Price ranges by store:")
        for stat in result:
            logger.info(f"\nStore {stat.get('store')}:")
            logger.info(f"  Completed Sales Range: ${stat.get('min_completed_sale', 0):.2f} - ${stat.get('max_completed_sale', 0):.2f}")
            logger.info(f"  Laptop Price Range: ${stat.get('min_laptop_price', 0):.2f} - ${stat.get('max_laptop_price', 0):.2f}")

        # Clean up
        logger.info("\n=== Cleaning up ===")
        for sale in sales:
            await sale.delete()
        
        logger.info("\n✅ All tests completed successfully!")

    except Exception as e:
        logger.error(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        # Close the connection
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())