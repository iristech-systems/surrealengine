import asyncio
from surrealengine import create_connection, Document, StringField, QuerySet

# Example document
class Person(Document):
    name = StringField()
    class Meta:
        collection = "person"

async def traverse_example(conn):
    # Simple traversal: people who ordered products
    qs = QuerySet(Person, conn).traverse("->order->product", unique=True)
    print("Traversal query:", qs.get_raw_query())
    try:
        rows = await qs.limit(5).all()
        # If traverse() is used, our SELECT projects the path as 'traversed'
        processed = []
        for r in rows:
            if isinstance(r, dict) and 'traversed' in r:
                processed.append(r['traversed'])
            else:
                processed.append(r)
        print("Traversed rows:", processed)
    except Exception as e:
        print("Traversal failed (ensure DB running and schema exists):", e)

async def live_example(conn):
    # Live changes on person table; we will generate some events to demonstrate output
    qs = QuerySet(Person, conn)

    async def consumer():
        try:
            async for event in qs.live():  # no where-filter so we see all events
                print("Live event:", event)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(consumer())

    # Give the subscription a moment to start
    await asyncio.sleep(0.5)

    # Generate some events: CREATE, UPDATE, DELETE
    try:
        anna = await Person(name="Anna").save()
        # Update existing Bob if present; otherwise create-and-update
        bob = await QuerySet(Person, conn).filter(name="Bob").first()
        if bob:
            bob.name = "Bobby"
            await bob.save()
        else:
            tmp = await Person(name="Bob").save()
            tmp.name = "Bobby"
            await tmp.save()
        # Delete a temp record to trigger DELETE
        temp = await Person(name="Temp").save()
        await temp.delete()
    except Exception as e:
        print("Event generation encountered an issue:", e)

    # Listen a bit longer to receive events
    await asyncio.sleep(3)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

async def seed_inline(conn):
    # Create minimal demo data directly in this script
    from surrealengine import create_tables_from_module
    # Ensure tables for Person, Product, and Order exist (schemaless)
    # Define lightweight Product/Order locally to keep self-contained
    class Product(Document):
        name = StringField(required=True)
        class Meta:
            collection = "product"
    class Order(Document):
        class Meta:
            collection = "order"
    await create_tables_from_module(__name__, schemafull=False)
    # Clear tiny dataset to keep demo deterministic
    try:
        await QuerySet(Person, conn).filter().delete()
    except Exception:
        pass
    try:
        await QuerySet(Product, conn).filter().delete()
    except Exception:
        pass
    try:
        await QuerySet(Order, conn).filter().delete()
    except Exception:
        pass
    # Seed some people and products
    alice = await Person(name="Alice").save()
    bob = await Person(name="Bob").save()
    phone = await Product(name="Phone").save()
    laptop = await Product(name="Laptop").save()
    # Create relations: person ->order-> product
    db = conn.db
    await db.person.relate(alice.id, "order", phone.id)
    await db.person.relate(alice.id, "order", laptop.id)
    await db.person.relate(bob.id, "order", phone.id)
    print("Seeded inline demo graph (Person, Product, order edges).")

async def main():
    conn = create_connection(
        url="ws://db:8000/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True,
    )
    await conn.connect()
    try:
        # Ensure some data exists for traversal and live demo
        try:
            await seed_inline(conn)
        except Exception as se:
            print("Inline seeding failed or skipped:", se)
        await traverse_example(conn)
        await live_example(conn)
    finally:
        await conn.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
