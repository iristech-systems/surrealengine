import asyncio
import time
import random
import os
from surrealengine import Document, StringField, IntField, create_connection, RawSurrealConnection

# Configuration
DB_URL = os.getenv("SURREALDB_URL", "ws://localhost:8001/rpc")
NAMESPACE = "test_ns"
DATABASE = "test_db"
USERNAME = "root"
PASSWORD = "root"
NUM_RECORDS = 10000

# Define Model
class BenchmarkUser(Document):
    name = StringField()
    email = StringField()
    age = IntField()
    
    class Meta:
        collection = "benchmark_users"

async def setup_data():
    # User said data is already added, skipping setup to save time/avoid errors
    print("Skipping data generation (User provided data).")
    pass

async def benchmark():
    print(f"\n--- BENCHMARK: {NUM_RECORDS} Records (Target) ---")
    
    # Verify Connection & Count
    print("Connecting to DB...")
    # Standard connection creation for count check
    # Standard connection creation for count check
    conn = create_connection(DB_URL, username=USERNAME, password=PASSWORD, namespace=NAMESPACE, database=DATABASE)
    try:
        await conn.connect()
        
        count = await BenchmarkUser.objects.count()
        print(f"Total Records in DB: {count}")
        
        if count == 0:
            print("DB is empty. Generating data...")
            # Generate Data
            users = []
            for i in range(NUM_RECORDS):
                users.append(BenchmarkUser(
                    name=f"User{i}",
                    email=f"user{i}@example.com",
                    age=random.randint(18, 90)
                ))
            
            # Batch insert
            batch_size = 1000
            for i in range(0, len(users), batch_size):
                batch = users[i:i+batch_size]
                # Check how to bulk insert in this ODM. 
                # Assuming .save() loop or similar if bulk not exposed, 
                # but standard save is slow.
                # Use raw query for speed or multiple gathers?
                # User.objects.create() loop?
                pass
            
            # Actually, let's just use raw insert for speed
            import json
            print(f"Inserting {NUM_RECORDS} records...")
             # Build strict JSON for raw query
            values = []
            for u in users:
               values.append({
                   "name": u.name,
                   "email": u.email,
                   "age": u.age
               })
            
            # Use chunks
            for i in range(0, len(values), 1000):
                chunk = values[i:i+1000]
                await conn.client.query(f"INSERT INTO benchmark_users {json.dumps(chunk)}")
            
            count = await BenchmarkUser.objects.count()
            print(f"Target count reached: {count}")
        
    except Exception as e:
        print(f"Benchmark Aborted: Could not connect to DB: {e}")
        return
    finally:
        await conn.disconnect()

    # 2. Rust Accelerator (Zero-Copy) using authentic Raw Connection
    print("\nBenchmarking Rust Accelerator (Level 3)...")
    try:
        async with RawSurrealConnection(DB_URL, namespace=NAMESPACE, database=DATABASE, username=USERNAME, password=PASSWORD) as raw_conn:
            # Manually inject connection into a fresh QuerySet
            qs = BenchmarkUser.objects
            qs.connection = raw_conn
            
            start = time.time()
            table = await qs.to_arrow()
            duration = time.time() - start
            
            count_loaded = len(table)
            print(f"Zero-Copy Arrow: {duration:.4f}s ({count_loaded} records)")
            
            # Simple validation
            if count_loaded > 0:
                print(f"Sample: {table.column('name')[0]}")
            
    except Exception as e:
        print(f"Rust Benchmark Failed: {e}")
        import traceback
        traceback.print_exc()

    # 1. Standard ODM (Python Objects)
    print("\nBenchmarking Standard ODM (Level 0)...")
    conn = create_connection(DB_URL, username=USERNAME, password=PASSWORD, namespace=NAMESPACE, database=DATABASE)
    try:
        await conn.connect()
        
        # Override connection on Model to be sure
        BenchmarkUser.objects.connection = conn.connections[0] if hasattr(conn, 'connections') else conn
        
        start = time.time()
        users = await BenchmarkUser.objects.all()
        duration = time.time() - start
        
        count_loaded = len(users)
        print(f"Standard ODM:    {duration:.4f}s ({count_loaded} records)")
        
    except Exception as e:
        print(f"Standard ODM Benchmark Failed: {e}")
    finally:
        await conn.disconnect()

if __name__ == "__main__":
    asyncio.run(benchmark())
