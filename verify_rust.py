import surrealengine.surrealengine_accelerator as accelerator
import cbor2

# Simulate CBOR data from SurrealDB (list of objects)
records = [
    {"name": "Alice", "age": 30, "active": True},
    {"name": "Bob", "age": 25, "active": False},
    {"name": "Charlie", "age": 35, "active": True}
]
# Rust extension expects root -> "result" (list) -> [0] -> "result" (list of records)
# Or if it iterates maps, it finds "result".
# src/lib.rs: 
#   let records_values_opt = if let Value::Map(ref map) = root { ... find "result" ... get [0] ... find "result"
data = {"result": [{"result": records}]}
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
