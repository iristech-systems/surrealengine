"""Demonstration of conditional aggregation features.

This script showcases the new conditional aggregation capabilities
without requiring a live database connection.
"""

from surrealengine import (
    Document, StringField, FloatField,
    Count, Sum, Mean, CountIf, SumIf, MeanIf, MinIf, MaxIf, DistinctCountIf,
    Expr
)
from surrealengine.query.base import QuerySet


class MockConnection:
    """Mock connection for demonstration."""
    def __init__(self):
        self.client = None


class Sale(Document):
    """Sale document for demonstration."""
    
    store = StringField(required=True)
    product = StringField(required=True)
    amount = FloatField(required=True)
    status = StringField(required=True)  # 'completed', 'refunded', 'pending'
    customer_type = StringField(required=True)  # 'regular', 'premium', 'new'
    
    class Meta:
        collection = "sale"


def demonstrate_conditional_aggregations():
    """Demonstrate conditional aggregation features."""
    print("🚀 SurrealEngine Conditional Aggregations Demo")
    print("=" * 50)
    
    # Create mock queryset
    mock_connection = MockConnection()
    queryset = QuerySet(Sale, mock_connection)
    
    # Override get_raw_query to return a base query
    queryset.get_raw_query = lambda: "SELECT * FROM sale"
    
    print("\n📊 1. Basic Conditional Counting")
    print("-" * 30)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.group(
        by_fields="store",
        total_sales=Count(),
        completed_sales=CountIf("status = 'completed'"),
        refunded_sales=CountIf("status = 'refunded'"),
        premium_customers=CountIf("customer_type = 'premium'"),
        high_value_sales=CountIf("amount > 500")
    )
    
    query = pipeline.build_query()
    print("Generated Query:")
    print(query)
    print("\nThis query will count:")
    print("• Total sales per store")
    print("• Completed sales per store")
    print("• Refunded sales per store")
    print("• Premium customer sales per store")
    print("• High-value sales (>$500) per store")
    
    print("\n💰 2. Conditional Revenue Analysis")
    print("-" * 35)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.group(
        by_fields="product",
        total_revenue=Sum("amount"),
        completed_revenue=SumIf("amount", "status = 'completed'"),
        refunded_amount=SumIf("amount", "status = 'refunded'"),
        avg_sale_amount=Mean("amount"),
        avg_completed_amount=MeanIf("amount", "status = 'completed'"),
        premium_revenue=SumIf("amount", "customer_type = 'premium'")
    ).sort(total_revenue="DESC")
    
    query = pipeline.build_query()
    print("Generated Query:")
    print(query)
    print("\nThis query will calculate:")
    print("• Total revenue per product")
    print("• Revenue from completed sales only")
    print("• Amount refunded per product")
    print("• Average sale amount")
    print("• Average amount for completed sales")
    print("• Revenue from premium customers")
    
    print("\n🔍 3. Complex Conditions with Expression Builder")
    print("-" * 45)
    
    # Build complex conditions
    high_value_completed = Expr.eq("status", "completed") & Expr.gt("amount", 100)
    established_customers = Expr.in_("customer_type", ["premium", "regular"])
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.group(
        by_fields="store",
        total_sales=Count(),
        high_value_completed_count=CountIf(str(high_value_completed)),
        high_value_completed_revenue=SumIf("amount", str(high_value_completed)),
        established_customer_sales=CountIf(str(established_customers)),
        complex_condition_avg=MeanIf("amount", str(high_value_completed & established_customers))
    )
    
    query = pipeline.build_query()
    print("Complex Conditions Used:")
    print(f"• High Value Completed: {high_value_completed}")
    print(f"• Established Customers: {established_customers}")
    print(f"• Combined Condition: {high_value_completed & established_customers}")
    print("\nGenerated Query:")
    print(query)
    
    print("\n🎯 4. Pre-aggregation Filtering with match()")
    print("-" * 42)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.match(status="completed", amount__gte=50)
    pipeline = pipeline.group(
        by_fields="customer_type",
        count=Count(),
        total_revenue=Sum("amount"),
        avg_revenue=Mean("amount"),
        min_sale=MinIf("amount", "amount > 0"),
        max_sale=MaxIf("amount", "amount < 10000")
    ).sort(total_revenue="DESC")
    
    query = pipeline.build_query()
    print("Pre-filters applied:")
    print("• Only completed sales")
    print("• Only sales >= $50")
    print("\nGenerated Query:")
    print(query)
    print("\nThis filters BEFORE aggregation, improving performance!")
    
    print("\n🏆 5. Post-aggregation Filtering with having()")
    print("-" * 43)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.group(
        by_fields="product",
        sale_count=Count(),
        total_revenue=Sum("amount"),
        completed_count=CountIf("status = 'completed'"),
        avg_amount=Mean("amount")
    )
    pipeline = pipeline.having(sale_count__gte=10, total_revenue__gt=1000)
    pipeline = pipeline.sort(total_revenue="DESC")
    
    query = pipeline.build_query()
    print("Post-aggregation filters:")
    print("• Products with at least 10 sales")
    print("• Products with revenue > $1000")
    print("\nGenerated Query:")
    print(query)
    print("\nThis filters AFTER aggregation, allowing filtering on computed values!")
    
    print("\n🔧 6. Complete Pipeline: match() → group() → having()")
    print("-" * 52)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.match(amount__gte=100)  # Pre-filter: high-value sales only
    pipeline = pipeline.group(
        by_fields=["store", "product"],
        count=Count(),
        revenue=Sum("amount"),
        avg_amount=Mean("amount"),
        completed_count=CountIf("status = 'completed'"),
        completion_rate=MeanIf("1", "status = 'completed'")
    )
    pipeline = pipeline.having(count__gte=5, revenue__gt=2000)  # Post-filter: significant volume
    pipeline = pipeline.sort(revenue="DESC")
    pipeline = pipeline.limit(5)
    
    query = pipeline.build_query()
    print("Complete pipeline:")
    print("1. PRE-FILTER: Only sales >= $100")
    print("2. GROUP BY: Store and product")
    print("3. AGGREGATE: Count, revenue, completion rates")
    print("4. POST-FILTER: At least 5 sales and $2000+ revenue")
    print("5. SORT: By revenue descending")
    print("6. LIMIT: Top 5 results")
    print("\nGenerated Query:")
    print(query)
    
    print("\n🎯 7. Min/Max Conditional Aggregations")
    print("-" * 37)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.group(
        by_fields="store",
        min_completed_sale=MinIf("amount", "status = 'completed'"),
        max_completed_sale=MaxIf("amount", "status = 'completed'"),
        min_premium_sale=MinIf("amount", "customer_type = 'premium'"),
        max_premium_sale=MaxIf("amount", "customer_type = 'premium'"),
        price_range=MaxIf("amount", "status = 'completed'")  # Could subtract MinIf for range
    )
    
    query = pipeline.build_query()
    print("Conditional Min/Max operations:")
    print("• Minimum/Maximum completed sale amounts")
    print("• Minimum/Maximum premium customer sale amounts")
    print("\nGenerated Query:")
    print(query)
    
    print("\n🔢 8. Distinct Count with Conditions")
    print("-" * 33)
    
    pipeline = queryset.aggregate()
    pipeline = pipeline.group(
        by_fields="store",
        total_products=DistinctCountIf("product", "amount > 0"),
        premium_products=DistinctCountIf("product", "customer_type = 'premium'"),
        high_value_products=DistinctCountIf("product", "amount > 500")
    )
    
    query = pipeline.build_query()
    print("Conditional distinct counts:")
    print("• Unique products sold (amount > 0)")
    print("• Unique products bought by premium customers")
    print("• Unique products in high-value sales")
    print("\nGenerated Query:")
    print(query)
    
    print("\n✨ Summary of New Features")
    print("=" * 50)
    print("🎯 Conditional Aggregations:")
    print("   • CountIf, SumIf, MeanIf, MinIf, MaxIf, DistinctCountIf")
    print("   • Use conditions like 'status = \"completed\"' or 'amount > 100'")
    print()
    print("🔧 Expression Builder:")
    print("   • Expr.eq(), Expr.gt(), Expr.in_(), etc.")
    print("   • Combine with & (AND), | (OR), ~ (NOT)")
    print("   • Build complex conditions programmatically")
    print()
    print("📊 Pipeline Methods:")
    print("   • match(**conditions) - Pre-aggregation filtering")
    print("   • having(**conditions) - Post-aggregation filtering")
    print("   • Support Django-style operators (__gt, __gte, etc.)")
    print()
    print("🚀 All features integrate seamlessly with existing aggregation API!")
    print("🔗 Method chaining works: .match().group().having().sort().limit()")
    print("⚡ Optimized query generation with proper SurrealQL syntax")


if __name__ == "__main__":
    demonstrate_conditional_aggregations()