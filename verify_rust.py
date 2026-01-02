import surrealengine.surrealengine_accelerator as accelerator
import pyarrow as pa
import cbor2

# Simulate CBOR data from SurrealDB (list of objects)
data = [
    {"name": "Alice", "age": 30, "active": True},
    {"name": "Bob", "age": 25, "active": False},
    {"name": "Charlie", "age": 35, "active": True}
]
cbor_bytes = cbor2.dumps(data)

print(f"CBOR Bytes: {len(cbor_bytes)} bytes")

# Test cbor_to_arrow
try:
    batch = accelerator.cbor_to_arrow(cbor_bytes)
    print("Success! Result type:", type(batch))
    print("RecordBatch:", batch)
    
    # Verify content
    df = batch.to_pandas()
    print("\nPandas DataFrame:")
    print(df)
    
    assert len(df) == 3
    assert df.iloc[0]["name"] == "Alice"
    print("\nVerification Passed!")
except Exception as e:
    print("\nVerification Failed!")
    print(e)
