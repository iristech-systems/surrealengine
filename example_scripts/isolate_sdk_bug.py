import asyncio
from surrealdb import Surreal
from surrealdb import RecordID
from surrealengine import create_connection

async def main():
    print("Testing native SDK relate")
    connection = create_connection(
        url="memory://",
        namespace="test_ns",
        database="test_db"
    )
    await connection.connect()

    # Create manual test data
    p1 = await connection.client.create("person", {"name": "Bob"})
    b1 = await connection.client.create("book", {"title": "Test Book"})
    pub1 = await connection.client.create("publisher", {"name": "Penguin"})

    p_id = p1[0]["id"] if isinstance(p1, list) else p1["id"]
    b_id = b1[0]["id"] if isinstance(b1, list) else b1["id"]
    pub_id = pub1[0]["id"] if isinstance(pub1, list) else pub1["id"]

    query = f"RELATE {p_id}->authored->{b_id} SET publisher = {pub_id}"
    print(query)
    rel = await connection.client.query(query)
    print(f"Relate output: {rel}")

    query2 = f"RELATE {p_id}->authored2->{b_id} CONTENT {{ publisher: {pub_id} }}"
    print(query2)
    rel2 = await connection.client.query(query2)
    print(f"Relate 2 output: {rel2}")

    q3 = await connection.client.query("SELECT * FROM authored")
    print(f"Check authored: {q3}")
    
    q4 = await connection.client.query("SELECT * FROM authored2")
    print(f"Check authored2: {q4}")

if __name__ == "__main__":
    asyncio.run(main())
