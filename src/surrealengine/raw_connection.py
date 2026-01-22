import uuid
import asyncio
import logging
from typing import Optional, List, Any, Dict, Union

# Optional dependencies with type checking guards
try:
    import websockets # type: ignore
    from websockets.client import connect as ws_connect # type: ignore
except ImportError:
    websockets = None
    ws_connect = None

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
    A high-performance, lower-level connection to SurrealDB using websockets directly.
    
    This connection bypasses the standard SDK's abstraction layers for:
    1. Zero-copy Arrow data transfer (when enabled)
    2. Direct CBOR messaging
    3. Lower overhead for high-throughput scenarios
    
    Features:
    - Level 1: Pure Python Optimization (Bypass SDK overhead)
    - Level 2: Rust Accelerator (Serialization speedup)
    - Level 3: Zero-Copy Arrow (Data transfer speedup)
    """
    
    def __init__(self, url: str, token: Optional[str] = None, namespace: Optional[str] = None, database: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        self.url = url
        self.token = token
        self.namespace = namespace
        self.database = database
        self.username = username
        self.password = password
        self.ws = None
        self.id_counter = 0
        self._connected = False
        
        # Performance flags
        self.use_accelerator = accelerator is not None
        self.use_arrow = False # Enabled explicitly
        
        if not cbor2:
            logger.warning("cbor2 not installed. Raw connection will be limited.")
            
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        """Establish the websocket connection and authenticate."""
        if self._connected:
            return

        if not websockets:
            raise ImportError("websockets package is required for RawSurrealConnection")

        # Convert http/https to ws/wss
        ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://")
        if not ws_url.endswith("/rpc"):
             ws_url = f"{ws_url.rstrip('/')}/rpc"
             
        try:
            # Connect with CBOR subprotocol
            self.ws = await ws_connect(ws_url, subprotocols=["cbor"], max_size=None)
            self._connected = True
            
            # Authenticate
            if self.token:
                await self.authenticate_token(self.token)
            elif self.username and self.password:
                await self.signin(self.username, self.password)
                
            # Use namespace/db
            if self.namespace and self.database:
                await self.use(self.namespace, self.database)
                
        except Exception as e:
            logger.error(f"Failed to connect to SurrealDB: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """Close the connection."""
        if self.ws:
            await self.ws.close()
            self._connected = False
            
    async def _send_rust(self, req: Dict) -> bytes:
        """Helper to send request via Rust accelerator if available."""
        if not accelerator:
            raise RuntimeError("Rust accelerator not available.")
        if not self.ws:
            raise ConnectionError("Websocket not connected")
        
        # The accelerator handles the CBOR serialization and sends it
        # This assumes accelerator has a method to send and receive raw bytes
        # For now, let's assume it just serializes and we send it.
        # A more advanced accelerator might directly manage the websocket.
        
        # For now, we'll serialize with Python cbor2 and then pass to accelerator for processing response
        # Or, if the accelerator can serialize, we'd use that.
        # Let's assume accelerator.cbor_dumps(req) exists for sending.
        # If not, we fall back to cbor2.dumps(req)
        
        # Placeholder: Assuming accelerator.cbor_dumps exists for sending
        # If not, this part needs adjustment based on actual accelerator API
        try:
            # If accelerator can serialize, use it
            serialized_req = accelerator.cbor_dumps(req)
        except AttributeError:
            # Fallback to Python cbor2 for serialization
            if cbor2 is None:
                raise ImportError("cbor2 is required for serialization when accelerator cannot.")
            serialized_req = cbor2.dumps(req)
            
        await self.ws.send(serialized_req)
        return await self.ws.recv()

    async def authenticate_token(self, token: str):
        """Authenticate with a token."""
        if cbor2 is None:
            raise ImportError("cbor2 is required for authentication.")
        req_id = str(self.id_counter)
        self.id_counter += 1
        req = {
            "id": req_id,
            "method": "authenticate",
            "params": [token]
        }
        if self.ws:
            await self.ws.send(cbor2.dumps(req))
            resp_bytes = await self.ws.recv()
            # Basic check for error
            decoded = cbor2.loads(resp_bytes)
            if "error" in decoded:
                raise RuntimeError(f"Authentication failed: {decoded['error']}")
        else:
            raise ConnectionError("Websocket not connected")

    async def signin(self, username: str, password: str):
        """Sign in with username and password."""
        if cbor2 is None:
            raise ImportError("cbor2 is required for signin.")
        req_id = str(self.id_counter)
        self.id_counter += 1
        req = {
            "id": req_id,
            "method": "signin",
            "params": [{
                "user": username,
                "pass": password,
            }]
        }
        if self.ws:
            await self.ws.send(cbor2.dumps(req))
            resp_bytes = await self.ws.recv()
            decoded = cbor2.loads(resp_bytes)
            if "error" in decoded:
                raise RuntimeError(f"Signin failed: {decoded['error']}")
        else:
            raise ConnectionError("Websocket not connected")

    async def use(self, ns: str, db: str):
        """Switch namespace and database."""
        if cbor2 is None:
            raise ImportError("cbor2 is required for 'use' command.")
        req_id = str(self.id_counter)
        self.id_counter += 1
        req = {
            "id": req_id,
            "method": "use",
            "params": [ns, db]
        }
        if self.ws:
            await self.ws.send(cbor2.dumps(req))
            resp_bytes = await self.ws.recv()
            decoded = cbor2.loads(resp_bytes)
            if "error" in decoded:
                raise RuntimeError(f"Use failed: {decoded['error']}")
        else:
            raise ConnectionError("Websocket not connected")

    async def query_arrow(self, sql: str, vars: dict = None):
        """
        Execute the query and return an Arrow RecordBatch using the Rust accelerator.
        """
        if not self.ws:
            raise RuntimeError("Not connected")
        
        assert cbor2 is not None
        assert accelerator is not None

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
