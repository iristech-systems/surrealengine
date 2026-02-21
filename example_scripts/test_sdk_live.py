import asyncio
from surrealdb import Surreal
import time
import threading

def main():
    db = Surreal("mem://")
    db.use("test", "test")
    
    # ensure empty
    db.query("DELETE test_table")
    
    events = []
    
    def listen():
        try:
            print("Listening...")
            # Try to start a live query on the embedded database
            # This is synchronous blocking method in mem:// ?
            res = db.live("test_table")
            print(f"Live returned: {res}")
            
            # Wait, how do you consume the live stream if there is no generator?
            # Embedded doesn't have an asynchronous SDK interface and db.live returns a UUID
            # But the synchronous SDK doesn't expose a subscribe_live generator natively in python?
        except Exception as e:
            print(f"Listen error: {e}")

    t = threading.Thread(target=listen)
    t.start()
    
    time.sleep(1)
    
    db.create("test_table", {"name": "hello"})
    
    time.sleep(1)
    
    t.join()
    
    print("Done")

if __name__ == "__main__":
    main()
