import asyncio
import uuid
import logging
import websockets
try:
    import cbor2
except ImportError:
    cbor2 = None
try:
    import surrealengine.surrealengine_accelerator as accelerator
except ImportError:
    accelerator = None

logger = logging.getLogger(__name__)

def cbor_tag_hook(decoder, tag):
    # Tag 8: Custom Record ID [table, id]
    if tag.tag == 8:
        if isinstance(tag.value, list) and len(tag.value) == 2:
            return f"{tag.value[0]}:{tag.value[1]}"
        return str(tag.value)
    # Tag 7: Datetime (standard CBOR, but maybe custom encoding?)
    # Tag 6: UUID (standard)
    # Tag 10: Array?
    return tag.value

class RawSurrealConnection:
    """
    A lightweight, dedicated connection for performing Zero-Copy operations.
    
    This connection bypasses the standard SurrealDB SDK to directly manage
    WebSocket communication and binary CBOR data. It allows passing raw bytes
    to the `surrealengine_accelerator` for high-performance Arrow conversion.
    
    Use this context manager when you need to fetch large datasets for analytics.
    """
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __init__(self, url: str, token: str = None, namespace: str = None, database: str = None, username: str = None, password: str = None):
        self.url = url
        self.token = token
        self.namespace = namespace
        self.database = database
        self.username = username
        self.password = password
        self.ws = None
        
        if cbor2 is None:
            raise ImportError("cbor2 is required for RawSurrealConnection")
        if accelerator is None:
            raise ImportError("surrealengine_accelerator is required for Zero-Copy features")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        # Ensure URL has /rpc endpoint if not present
        ws_url = self.url
        if not ws_url.endswith("/rpc"):
             ws_url = f"{ws_url.rstrip('/')}/rpc"

        # Connect with CBOR subprotocol support and increased size limit
        # Set max_size to None (no limit) or very high for large datasets
        self.ws = await websockets.connect(ws_url, subprotocols=["cbor"], max_size=None)
        
        # Authenticate
        if self.token:
             # Just use the token
             req_id = str(uuid.uuid4())
             req = {
                 "id": req_id,
                 "method": "authenticate",
                 "params": [self.token]
             }
             await self.ws.send(cbor2.dumps(req))
             resp = await self.ws.recv() 
             # Basic check
             if isinstance(resp, str):
                 pass # JSON response likely OK
             else:
                 cbor2.loads(resp) # Validate CBOR
        elif self.username and self.password:
             # Signin
             req_id = str(uuid.uuid4())
             req = {
                 "id": req_id,
                 "method": "signin",
                 "params": [{
                     "user": self.username,
                     "pass": self.password,
                 }]
             }
             await self.ws.send(cbor2.dumps(req))
             resp = await self.ws.recv()
             if isinstance(resp, str):
                 import json
                 decoded = json.loads(resp)
             else:
                 decoded = cbor2.loads(resp)
                 
             if "error" in decoded:
                 raise RuntimeError(f"Auth failed: {decoded['error']}")

        if self.namespace and self.database:
             await self.use(self.namespace, self.database)

    async def close(self):
        if self.ws:
            await self.ws.close()

    async def use(self, ns: str, db: str):
        """Switch namespace and database."""
        req_id = str(uuid.uuid4())
        req = {
            "id": req_id,
            "method": "use",
            "params": [ns, db]
        }
        await self.ws.send(cbor2.dumps(req))
        resp_bytes = await self.ws.recv()
        # We process response just to ensure it succeeded, but we don't strictly need the content for 'use'
        # unless checking for errors. For now, simplistic.
        

    async def query_arrow(self, sql: str, vars: dict = None):
        """
        Execute the query and return an Arrow RecordBatch using the Rust accelerator.
        """
        if not self.ws:
            raise RuntimeError("Not connected")

        req_id = str(uuid.uuid4())
        req = {
            "id": req_id,
            "method": "query",
            "params": [sql, vars or {}]
        }
        
        # Send CBOR encoded request
        await self.ws.send(cbor2.dumps(req))
        
        # Receive Raw Bytes
        resp_bytes = await self.ws.recv()
        
        # Level 3: Rust Zero-Copy Accelerator
        # We pass the raw bytes directly to Rust. 
        # The Rust extension handles envelope parsing and Arrow conversion.
        try:
            batch = accelerator.cbor_to_arrow(resp_bytes)
            if batch:
                import pyarrow as pa
                return pa.Table.from_batches([batch])
            else:
                # Empty result
                return None
        except Exception as e:
            # Fallback for debugging, or re-raise
            # raise RuntimeError(f"Rust Accelerator Failed: {e}")
            logger.error(f"Rust Accelerator Failed: {e}. Falling back to Python.")
            pass

        # Fallback to Python decoding (Level 2) logic if Rust fails
        # Decode using hook for tags
        decoded = cbor2.loads(resp_bytes, tag_hook=cbor_tag_hook)
        
        # Extract the actual data rows
        if "result" in decoded and isinstance(decoded["result"], list):
            first_result = decoded["result"][0]
            if first_result.get("status") == "OK":
                data = first_result.get("result", [])
                import pyarrow as pa
                return pa.Table.from_pylist(data)

        return None
