import asyncio
from surrealdb import AsyncSurreal

async def main():
    db = AsyncSurreal("memory://")
    await db.use("test", "test")
    
    await db.query("CREATE test:1 SET count = 0;")
    
    # Try transaction as a single string
    await db.query("""
    BEGIN TRANSACTION;
    UPDATE test:1 SET count = 1;
    CANCEL TRANSACTION;
    """)
    
    # Check if rollback worked
    result = await db.query("SELECT * FROM test:1;")
    print("Result after single-string rollback:", result)
    
    # Try commit as single string
    await db.query("""
    BEGIN TRANSACTION;
    UPDATE test:1 SET count = 2;
    COMMIT TRANSACTION;
    """)
    result = await db.query("SELECT * FROM test:1;")
    print("Result after single-string commit:", result)

if __name__ == "__main__":
    asyncio.run(main())
