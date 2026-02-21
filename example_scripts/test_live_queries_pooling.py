import asyncio
from surrealengine import Document, StringField
from surrealengine.connection import create_connection

class LiveMessage(Document):
    text = StringField()

async def main():
    # We use create_connection with pool sizes. 
    # But because our clone() bypasses the pool pool_size=1 shouldn't deadlock it!
    # A single shared pool connection means normal saves and queries take it.
    conn = create_connection("ws://localhost:8000/rpc", "test", "test", "root", "root", use_pool=True, pool_size=1, make_default=True)
    await conn.connect()
    
    # ensure table empty
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
    
    # Wait for subscription to establish
    print("Waiting 1 second for subscription...")
    await asyncio.sleep(1)
    
    # Send some data on the main pooled connection
    print("Saving msg1...")
    msg1 = LiveMessage(text="Hello")
    await msg1.save()
    
    print("Saving msg2...")
    msg2 = LiveMessage(text="World")
    await msg2.save()
    
    print("Waiting for listener to finish...")
    try:
        await asyncio.wait_for(listener, timeout=5.0)
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
