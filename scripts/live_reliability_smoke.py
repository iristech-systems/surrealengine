#!/usr/bin/env python3
import argparse
import asyncio
import os
import time

from surrealengine import Document, StringField, create_connection


class FeedItem(Document):
    text = StringField()

    class Meta:
        collection = "feed_items_live_smoke"


async def run_fanout_sanity(conn, timeout_seconds: float) -> None:
    qid = await FeedItem.objects.start_live(connection=conn)
    print(f"[fanout] started qid={qid}")

    async def recv_one(label: str):
        stream = FeedItem.objects.subscribe_to_live(
            qid, connection=conn, queue_maxsize=200
        )
        try:
            evt = await asyncio.wait_for(anext(stream), timeout=timeout_seconds)
            print(f"[fanout] {label} received action={evt.action} id={evt.id}")
            return evt
        finally:
            await stream.aclose()

    t1 = asyncio.create_task(recv_one("A"))
    t2 = asyncio.create_task(recv_one("B"))
    await asyncio.sleep(0.2)
    created = await FeedItem(text="fanout-sanity").save(connection=conn)
    print(f"[fanout] created id={created.id}")
    await asyncio.gather(t1, t2)
    await conn.client.kill(qid)
    print("[fanout] qid closed")


async def run_managed_soak(
    conn,
    duration_seconds: float,
    publish_interval: float,
    event_timeout: float,
) -> int:
    start = time.monotonic()
    deadline = start + duration_seconds
    produced = 0
    consumed = 0
    failures = 0

    async def producer() -> None:
        nonlocal produced
        i = 0
        while time.monotonic() < deadline:
            i += 1
            await FeedItem(text=f"soak-{i}").save(connection=conn)
            produced += 1
            await asyncio.sleep(publish_interval)

    producer_task = asyncio.create_task(producer())
    stream = FeedItem.objects.live(
        action=["CREATE"],
        queue_maxsize=1000,
        backpressure_policy="drop_oldest",
        retry_limit=8,
        initial_delay=0.5,
        backoff=2.0,
    )

    print(
        f"[soak] running for {duration_seconds:.1f}s, "
        f"publish every {publish_interval:.2f}s, timeout {event_timeout:.1f}s"
    )

    try:
        while time.monotonic() < deadline:
            try:
                evt = await asyncio.wait_for(anext(stream), timeout=event_timeout)
            except asyncio.TimeoutError:
                remaining = deadline - time.monotonic()
                if remaining > max(1.0, publish_interval * 1.5):
                    failures += 1
                    print("[soak] timeout waiting for next live event")
                else:
                    print("[soak] timeout near end of run; stopping without failure")
                break
            consumed += 1
            if consumed % 20 == 0:
                elapsed = time.monotonic() - start
                print(
                    f"[soak] elapsed={elapsed:.1f}s produced={produced} consumed={consumed} "
                    f"last={evt.id}"
                )
    finally:
        await stream.aclose()
        await producer_task

    print(
        f"[soak] complete produced={produced} consumed={consumed} failures={failures}"
    )
    if consumed == 0:
        failures += 1
    # Allow a small tail gap from startup/shutdown timing.
    if produced > 0 and consumed < max(1, produced - 2):
        failures += 1
        print("[soak] consumed too few events relative to produced messages")
    return failures


async def main() -> int:
    parser = argparse.ArgumentParser(description="LIVE reliability smoke/soak test")
    parser.add_argument("--url", default=os.getenv("SURREAL_URL", "ws://localhost:8080/rpc"))
    parser.add_argument("--namespace", default=os.getenv("SURREAL_NS", "demo"))
    parser.add_argument("--database", default=os.getenv("SURREAL_DB", "live_demo"))
    parser.add_argument("--username", default=os.getenv("SURREAL_USER", "root"))
    parser.add_argument("--password", default=os.getenv("SURREAL_PASS", "secret"))
    parser.add_argument("--duration-seconds", type=float, default=900.0)
    parser.add_argument("--publish-interval", type=float, default=2.0)
    parser.add_argument("--event-timeout", type=float, default=20.0)
    parser.add_argument("--skip-fanout", action="store_true")
    args = parser.parse_args()

    conn = create_connection(
        url=args.url,
        namespace=args.namespace,
        database=args.database,
        username=args.username,
        password=args.password,
        make_default=True,
    )
    await conn.connect()
    await FeedItem.create_table(connection=conn)
    await conn.client.query(f"DELETE {FeedItem._get_collection_name()};")

    failures = 0
    try:
        if not args.skip_fanout:
            await run_fanout_sanity(conn, timeout_seconds=args.event_timeout)

        failures += await run_managed_soak(
            conn,
            duration_seconds=args.duration_seconds,
            publish_interval=args.publish_interval,
            event_timeout=args.event_timeout,
        )
    finally:
        await conn.disconnect()

    if failures:
        print(f"[result] FAIL ({failures} failure conditions)")
        return 1
    print("[result] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
