import asyncio
from unittest.mock import AsyncMock, MagicMock
from surrealengine import QuerySet, Document, StringField, IntField
# Import RawSurrealConnection from namespace to ensure it's exposed
import pyarrow as pa
import polars as pl
import sys

# Define a sample document
class Person(Document):
    name = StringField()
    age = IntField()
    class Meta:
        collection = "person"

async def test_queryset_to_arrow_fallback():
    print("Testing to_arrow() fallback...")
    mock_conn = MagicMock()
    # Explicitly ensure query_arrow is absent for fallback test
    del mock_conn.query_arrow 
    
    mock_client = AsyncMock()
    mock_conn.client = mock_client
    
    mock_response = [
        {"id": "person:1", "name": "Alice", "age": 30},
        {"id": "person:2", "name": "Bob", "age": 25}
    ]
    mock_client.query.return_value = mock_response
    
    qs = QuerySet(Person, mock_conn)
    table = await qs.to_arrow()
    
    assert isinstance(table, pa.Table)
    assert len(table) == 2
    assert table.column("name")[0].as_py() == "Alice"
    print("Fallback Passed!")

async def test_queryset_to_polars():
    print("Testing to_polars()...")
    mock_conn = MagicMock()
    del mock_conn.query_arrow
    mock_client = AsyncMock()
    mock_conn.client = mock_client
    mock_response = [{"id": "person:1", "name": "Alice", "age": 30}]
    mock_client.query.return_value = mock_response
    
    qs = QuerySet(Person, mock_conn)
    df = await qs.to_polars()
    
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 1
    assert df["name"][0] == "Alice"
    print("Polars Passed!")

async def test_queryset_raw_conn():
    print("Testing RawSurrealConnection integration...")
    mock_raw_conn = MagicMock()
    mock_raw_conn.query_arrow = AsyncMock()
    
    mock_table = pa.Table.from_pylist([{"name": "FastAlice", "age": 99}])
    mock_raw_conn.query_arrow.return_value = mock_table
    
    qs = QuerySet(Person, mock_raw_conn)
    result = await qs.to_arrow()
    
    assert result == mock_table
    mock_raw_conn.query_arrow.assert_called_once()
    print("Raw Connection Passed!")

async def main():
    try:
        await test_queryset_to_arrow_fallback()
        await test_queryset_to_polars()
        await test_queryset_raw_conn()
        print("\nALL INTEGRATION TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
