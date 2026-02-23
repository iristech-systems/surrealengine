"""
Live Query Fan-Out Pattern — FastAPI Example
============================================

THE PROBLEM
-----------
Without fan-out, every user who hits GET /notifications/stream opens their
own LIVE SELECT on SurrealDB:

    user A connects  →  LIVE SELECT * FROM notification  (query 1)
    user B connects  →  LIVE SELECT * FROM notification  (query 2)
    user C connects  →  LIVE SELECT * FROM notification  (query 3)

With 1 000 concurrent users you have 1 000 live queries — most of which are
watching the exact same table.

THE FIX
-------
Use start_live() once at app startup to get a UUID, then each user's
subscribe_to_live(uuid) call attaches a new asyncio.Queue to that single
running query.  SurrealDB sees one LIVE SELECT regardless of how many users
are listening.

    app startup       →  start_live()  →  uuid = "abc-123..."
    user A connects  →  subscribe_to_live(uuid)  (queue A attached)
    user B connects  →  subscribe_to_live(uuid)  (queue B attached)
    user C connects  →  subscribe_to_live(uuid)  (queue C attached)

HOW TO RUN
----------
    pip install fastapi uvicorn sse-starlette
    uvicorn test_live_fanout_app:app --reload --port 8080

Then open multiple browser tabs at:
    http://localhost:8080/notifications/stream

And POST to:
    http://localhost:8080/notifications  body: {"message": "hello"}

All tabs will receive the event simultaneously via a single SurrealDB subscription.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from surrealengine import Document, StringField, create_connection


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Notification(Document):
    message  = StringField(required=True)
    severity = StringField(default="info")  # info | warning | error

    class Meta:
        collection = "notification"


# ---------------------------------------------------------------------------
# App-level state — one live query UUID, shared across ALL users
# ---------------------------------------------------------------------------

class LiveState:
    uuid: str | None = None
    connection = None


state = LiveState()


# ---------------------------------------------------------------------------
# Lifespan: connect once, start one LIVE SELECT, store the UUID
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to SurrealDB
    conn = create_connection(
        url          = "ws://localhost:8000/rpc",
        namespace    = "test_ns",
        database     = "test_db",
        username     = "root",
        password     = "root",
        make_default = True,
    )
    await conn.connect()
    state.connection = conn
    print("[startup] Connected to SurrealDB")

    # Create table if needed
    await Notification.create_table(conn)

    # --- KEY PART ---
    # Start ONE live query for the whole app.
    # Every user's SSE stream will subscribe to this same UUID.
    state.uuid = await Notification.objects.start_live(connection=conn)
    print(f"[startup] Live query started: {state.uuid}")

    yield  # app runs here

    print("[shutdown] Disconnecting")
    await conn.close()


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# SSE stream endpoint — one per connected user, zero extra DB subscriptions
# ---------------------------------------------------------------------------

async def event_generator(uuid: str) -> AsyncGenerator[str, None]:
    """
    Attach a new queue listener to the shared live query.

    subscribe_to_live() injects an asyncio.Queue into the sdk's live_queues
    for this UUID — each call gets its own independent queue, but no new
    LIVE SELECT is sent to SurrealDB.
    """
    print(f"[stream] New user subscribed to {uuid}")
    try:
        async for evt in Notification.objects.subscribe_to_live(uuid, connection=state.connection):
            # SSE format: "data: <json>\n\n"
            payload = {
                "action":   evt.action,
                "message":  getattr(evt.document, "message",  None) if evt.document else None,
                "severity": getattr(evt.document, "severity", None) if evt.document else None,
            }
            yield f"data: {json.dumps(payload)}\n\n"
    except asyncio.CancelledError:
        print(f"[stream] User disconnected from {uuid}")
        raise


@app.get("/notifications/stream")
async def notifications_stream():
    """
    Server-Sent Events endpoint.

    Open this URL in a browser (or via EventSource JS) to receive live
    notification updates in real time.
    """
    if state.uuid is None:
        return {"error": "Live query not started yet"}, 503

    return StreamingResponse(
        event_generator(state.uuid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# Write endpoint — creates a notification, which the live query broadcasts
# ---------------------------------------------------------------------------

class NotificationIn(BaseModel):
    message:  str
    severity: str = "info"


@app.post("/notifications")
async def create_notification(body: NotificationIn):
    n = Notification(message=body.message, severity=body.severity)
    await n.save()
    return {"id": str(n.id), "message": n.message}


# ---------------------------------------------------------------------------
# Health check — shows how many users are currently streaming
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """
    Shows the shared live query UUID and whether it's active.
    Attach ?verbose=1 for more detail.
    """
    client = getattr(state.connection, "client", None)

    # Probe the SDK's live_queues to count attached subscribers
    under = None
    for attr in ("connection", "_connection", "conn", "_conn"):
        obj = getattr(client, attr, None)
        if obj is not None and hasattr(obj, "live_queues"):
            under = obj
            break
    if under is None and hasattr(client, "live_queues"):
        under = client

    subscriber_count = 0
    if under and state.uuid and state.uuid in getattr(under, "live_queues", {}):
        subscriber_count = len(under.live_queues[state.uuid])

    return {
        "live_query_uuid": state.uuid,
        "subscribers": subscriber_count,
        "note": "All subscribers share one LIVE SELECT on SurrealDB",
    }


# ---------------------------------------------------------------------------
# Optional: standalone asyncio demo (no FastAPI needed)
# ---------------------------------------------------------------------------

async def _standalone_demo():
    """
    Run without FastAPI to verify the fan-out mechanism works.
    Creates 3 consumers sharing one UUID, publishes a notification,
    and asserts all 3 consumers receive it.
    """
    conn = create_connection(
        url          = "ws://localhost:8000/rpc",
        namespace    = "test_ns",
        database     = "test_db",
        username     = "root",
        password     = "root",
        make_default = True,
    )
    await conn.connect()
    await Notification.create_table(conn)

    uuid = await Notification.objects.start_live(connection=conn)
    print(f"[demo] UUID: {uuid}")

    received = {0: [], 1: [], 2: []}

    async def consumer(idx: int):
        async for evt in Notification.objects.subscribe_to_live(uuid, connection=conn):
            msg = getattr(evt.document, "message", "?")
            print(f"[consumer {idx}] received: {msg}")
            received[idx].append(msg)
            if len(received[idx]) >= 2:
                break

    # Start 3 consumers
    tasks = [asyncio.create_task(consumer(i)) for i in range(3)]
    await asyncio.sleep(0.5)  # let them attach

    # Publish two notifications
    for text in ["hello from the publisher", "second event"]:
        n = Notification(message=text)
        await n.save()
        print(f"[demo] Published: {text}")
        await asyncio.sleep(0.3)

    await asyncio.gather(*tasks)

    # Verify
    for idx, msgs in received.items():
        assert len(msgs) == 2, f"Consumer {idx} only got {len(msgs)} messages"
        print(f"[demo] Consumer {idx} OK: {msgs}")

    print("[demo] All 3 consumers received both events from ONE live query ✓")
    await conn.close()


if __name__ == "__main__":
    # Run the standalone demo
    asyncio.run(_standalone_demo())
