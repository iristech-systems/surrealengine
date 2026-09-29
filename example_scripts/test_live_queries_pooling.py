import asyncio
from surrealengine import Document, StringField
from surrealengine.connection import create_connection

class LiveMessage(Document):
    text = StringField()

    class Meta:
        # Explicit collection: without it the default name derivation yields
        # 'livemessage' (lowercased class name), which would NOT match the
        # table created below — a LIVE SELECT against a table that doesn't
        # exist yet silently never fires on SurrealDB 3.x.
        collection = "live_message"

async def main():
    # We use create_connection with pool sizes. 
    # But because our clone() bypasses the pool pool_size=1 shouldn't deadlock it!
    # A single shared pool connection means normal saves and queries take it.
    conn = create_connection("ws://localhost:8000/rpc", "test", "test", "root", "root", use_pool=True, pool_size=1, make_default=True)
    await conn.connect()

    # ensure table exists and is empty
    await conn.client.query("DEFINE TABLE IF NOT EXISTS live_message SCHEMALESS")
    await conn.client.query("DELETE live_message")
    
    events = []
    
    async def listen():
        try:
            # This should checkout a clone entirely separate from the 1 connection pool
            print("Listening for events...")
            async for event in LiveMessage.objects.live():
                print(f"Got event: {event.action} - {event.data}")
                events.append(event)
                if len(events) >= 2:
                    break
        except Exception as e:
            print(f"Listen error: {e}")
            raise e
            
    # start listening
    listener = asyncio.create_task(listen())

    # Wait for subscription to establish (clone + connect + LIVE SELECT can
    # take longer than a second on a busy server, so allow up to 5s)
    print("Waiting up to 5 seconds for subscription...")
    await asyncio.sleep(3)

    # Send some data on the main pooled connection
    print("Saving msg1...")
    msg1 = LiveMessage(text="Hello")
    await msg1.save()

    print("Saving msg2...")
    msg2 = LiveMessage(text="World")
    await msg2.save()

    print("Waiting for listener to finish...")
    try:
        await asyncio.wait_for(listener, timeout=10.0)
    except asyncio.TimeoutError:
        print(f"Listener timed out! Events received: {len(events)}")
        # Dump any tasks?
    
    assert len(events) == 2
    assert events[0].is_create
    assert events[0].data['text'] == "Hello"
    
    await conn.disconnect()
    print("ALL TESTS PASSED: Auto-cloning connection prevents pool deadlock!")
    
if __name__ == "__main__":
    asyncio.run(main())
