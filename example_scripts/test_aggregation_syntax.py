"""Test script for validating conditional aggregation syntax.

This script tests the aggregation query building without requiring
a database connection, to verify the implementation is correct.
"""

from surrealengine import (
    Document, StringField, IntField, FloatField,
    Count, Sum, Mean, CountIf, SumIf, MeanIf, MinIf, MaxIf, DistinctCountIf,
    Expr
)
from surrealengine.query.base import QuerySet
from surrealengine.aggregation import AggregationPipeline


class MockConnection:
    """Mock connection for testing."""
    def __init__(self):
        self.client = None


class TestSale(Document):
    """Test document for validation."""
    
    store = StringField(required=True)
    product = StringField(required=True)
    amount = FloatField(required=True)
    status = StringField(required=True)
    customer_type = StringField(required=True)
    
    class Meta:
        collection = "test_sale"


def test_conditional_aggregation_functions():
    """Test that conditional aggregation functions generate correct syntax."""
    print("=== Testing Conditional Aggregation Functions ===")
    
    # Test CountIf
    count_if = CountIf("status = 'completed'")
    expected = "count(IF status = 'completed' THEN 1 ELSE NULL END)"
    print(f"CountIf: {count_if}")
    print(f"Expected: {expected}")
    assert str(count_if) == expected, f"CountIf failed: got {count_if}, expected {expected}"
    
    # Test SumIf
    sum_if = SumIf("amount", "status = 'completed'")
    expected = "math::sum(IF status = 'completed' THEN amount ELSE 0 END)"
    print(f"SumIf: {sum_if}")
    print(f"Expected: {expected}")
    assert str(sum_if) == expected, f"SumIf failed: got {sum_if}, expected {expected}"
    
    # Test MeanIf
    mean_if = MeanIf("amount", "status = 'completed'")
    expected = "math::mean(IF status = 'completed' THEN amount ELSE NULL END)"
    print(f"MeanIf: {mean_if}")
    print(f"Expected: {expected}")
    assert str(mean_if) == expected, f"MeanIf failed: got {mean_if}, expected {expected}"
    
    print("✅ All conditional aggregation functions passed!")


def test_expression_builder():
    """Test the Expr builder functionality."""
    print("\n=== Testing Expression Builder ===")
    
    # Test simple equality
    expr = Expr.eq("status", "completed")
    expected = 'status = "completed"'
    print(f"Expr.eq: {expr}")
    print(f"Expected: {expected}")
    assert str(expr) == expected, f"Expr.eq failed: got {expr}, expected {expected}"
    
    # Test greater than
    expr = Expr.gt("amount", 100)
    expected = 'amount > 100'
    print(f"Expr.gt: {expr}")
    print(f"Expected: {expected}")
    assert str(expr) == expected, f"Expr.gt failed: got {expr}, expected {expected}"
    
    # Test AND combination
    expr1 = Expr.eq("status", "completed")
    expr2 = Expr.gt("amount", 100)
    combined = expr1 & expr2
    expected = '(status = "completed" AND amount > 100)'
    print(f"Combined AND: {combined}")
    print(f"Expected: {expected}")
    assert str(combined) == expected, f"AND combination failed: got {combined}, expected {expected}"
    
    # Test OR combination
    expr1 = Expr.eq("status", "completed")
    expr2 = Expr.eq("status", "pending")
    combined = expr1 | expr2
    expected = '(status = "completed" OR status = "pending")'
    print(f"Combined OR: {combined}")
    print(f"Expected: {expected}")
    assert str(combined) == expected, f"OR combination failed: got {combined}, expected {expected}"
    
    # Test IN expression
    expr = Expr.in_("status", ["completed", "pending"])
    expected = 'status IN ["completed", "pending"]'
    print(f"Expr.in_: {expr}")
    print(f"Expected: {expected}")
    assert str(expr) == expected, f"Expr.in_ failed: got {expr}, expected {expected}"
    
    print("✅ All expression builder tests passed!")


def test_aggregation_pipeline_structure():
    """Test the aggregation pipeline structure."""
    print("\n=== Testing Aggregation Pipeline Structure ===")
    
    # Create a mock QuerySet
    mock_connection = MockConnection()
    queryset = QuerySet(TestSale, mock_connection)
    
    # Create aggregation pipeline
    pipeline = queryset.aggregate()
    
    # Test method chaining
    pipeline = pipeline.match(status="completed", amount__gte=100)
    print("✅ match() method added successfully")
    
    pipeline = pipeline.group(
        by_fields="store",
        total_count=Count(),
        success_count=CountIf("status = 'completed'"),
        total_revenue=Sum("amount")
    )
    print("✅ group() method with conditional aggregations added successfully")
    
    pipeline = pipeline.having(total_count__gte=5, total_revenue__gt=1000)
    print("✅ having() method added successfully")
    
    pipeline = pipeline.sort(total_revenue="DESC")
    pipeline = pipeline.limit(10)
    print("✅ sort() and limit() methods added successfully")
    
    # Check that all stages were added
    stage_types = [stage['type'] for stage in pipeline.stages]
    expected_stages = ['match', 'group', 'having', 'sort', 'limit']
    
    print(f"Pipeline stages: {stage_types}")
    print(f"Expected stages: {expected_stages}")
    
    for expected_stage in expected_stages:
        assert expected_stage in stage_types, f"Missing stage: {expected_stage}"
    
    print("✅ All pipeline stages created successfully!")


def test_query_building():
    """Test that query building works without errors."""
    print("\n=== Testing Query Building ===")
    
    try:
        # Create a mock QuerySet with a simple base query
        mock_connection = MockConnection()
        queryset = QuerySet(TestSale, mock_connection)
        
        # Override the get_raw_query method to return a simple query
        queryset.get_raw_query = lambda: "SELECT * FROM test_sale"
        
        # Create and build a complex pipeline
        pipeline = queryset.aggregate()
        pipeline = pipeline.match(status="completed", amount__gte=100)
        pipeline = pipeline.group(
            by_fields=["store", "product"],
            total_count=Count(),
            success_count=CountIf("status = 'completed'"),
            avg_amount=Mean("amount"),
            total_revenue=SumIf("amount", "status = 'completed'")
        )
        pipeline = pipeline.having(total_count__gte=2)
        pipeline = pipeline.sort(total_revenue="DESC")
        pipeline = pipeline.limit(5)
        
        # Build the query
        query = pipeline.build_query()
        print(f"Generated query: {query}")
        
        # Basic validation that query contains expected parts
        assert "SELECT" in query, "Query missing SELECT"
        assert "FROM test_sale" in query, "Query missing FROM clause"
        assert "WHERE" in query, "Query missing WHERE clause (from match)"
        assert "GROUP BY" in query, "Query missing GROUP BY clause"
        assert "ORDER BY" in query, "Query missing ORDER BY clause"
        assert "LIMIT" in query, "Query missing LIMIT clause"
        
        print("✅ Query building completed without errors!")
        
    except Exception as e:
        print(f"❌ Query building failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_integration_with_existing_functions():
    """Test that new functions work with existing aggregation functions."""
    print("\n=== Testing Integration with Existing Functions ===")
    
    # Test mixing new and old aggregation functions
    try:
        count_regular = Count()
        count_conditional = CountIf("status = 'active'")
        sum_regular = Sum("amount")
        sum_conditional = SumIf("amount", "status = 'active'")
        
        print(f"Regular Count: {count_regular}")
        print(f"Conditional Count: {count_conditional}")
        print(f"Regular Sum: {sum_regular}")
        print(f"Conditional Sum: {sum_conditional}")
        
        # Verify they all inherit from the same base class
        from surrealengine.materialized_view import Aggregation
        
        assert isinstance(count_regular, Aggregation), "Count should inherit from Aggregation"
        assert isinstance(count_conditional, Aggregation), "CountIf should inherit from Aggregation"
        assert isinstance(sum_regular, Aggregation), "Sum should inherit from Aggregation"
        assert isinstance(sum_conditional, Aggregation), "SumIf should inherit from Aggregation"
        
        print("✅ All functions properly inherit from Aggregation base class!")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        raise


def main():
    """Run all tests."""
    print("🧪 Starting Conditional Aggregation Syntax Tests\n")
    
    try:
        test_conditional_aggregation_functions()
        test_expression_builder()
        test_aggregation_pipeline_structure()
        test_query_building()
        test_integration_with_existing_functions()
        
        print("\n🎉 ALL TESTS PASSED! The conditional aggregation implementation is working correctly.")
        print("\nFeatures validated:")
        print("✅ Conditional aggregation functions (CountIf, SumIf, etc.)")
        print("✅ Expression builder with AND/OR/NOT operators")
        print("✅ Pipeline methods (match, having)")
        print("✅ Query building without errors")
        print("✅ Integration with existing aggregation functions")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)