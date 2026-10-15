"""
Rating event consumer — reads rating events off a Redis Stream and refreshes the models.

The API gateway XADDs a `rating.created` / `rating.deleted` event to the stream after every
rating write. This service reads them through a consumer group:

  • events published while the service is asleep or restarting wait in the stream and are
    read when it comes back
  • an event is XACKed only after the rebuild that includes it has finished, so if the service
    dies mid-rebuild the event stays pending and is read again (at-least-once delivery);
    pending events left by a previous instance (a redeploy changes the hostname) are claimed
  • everything that has arrived is read as one batch and costs a single rebuild

Without REDIS_URL no consumer runs and the gateway falls back to calling POST /refresh.
"""
from __future__ import annotations

import asyncio
import os
import socket
from typing import Any, List, Optional

from refresher import ModelRefresher

STREAM = os.getenv("RATING_STREAM", "cinescope:ratings")
GROUP = "ml-service"
CLAIM_IDLE_MS = 60_000      # a pending event this idle belongs to a consumer that's gone
RETRY_DELAY_S = 5
MAX_RETRY_DELAY_S = 300     # failed rebuilds back off up to this, so a Mongo outage isn't hammered


class RatingEventConsumer:

    def __init__(
        self,
        redis: Any,
        refresher: ModelRefresher,
        stream: str = STREAM,
        group: str = GROUP,
        consumer: Optional[str] = None,
        block_ms: int = 5_000,
        batch_size: int = 500,
    ) -> None:
        self._redis = redis
        self._refresher = refresher
        self._stream = stream
        self._group = group
        self._consumer = consumer or os.getenv("CONSUMER_NAME") or socket.gethostname()
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._acks: set[asyncio.Task] = set()     # batches waiting for their rebuild to finish
        self._needs_recovery = False
        self._failed_rebuilds = 0                 # consecutive, for the retry backoff
        self.stats = {"events": 0, "batches": 0, "errors": 0, "last_event_id": None}

    async def run(self) -> None:
        # While not None, re-reading this consumer's pending (delivered, never acked) events
        # page by page from this id; None once caught up, then new events are read live.
        cursor: Optional[str] = "0"
        while True:
            try:
                if self._needs_recovery and cursor is None:
                    self._needs_recovery = False
                    await asyncio.sleep(self._retry_delay())
                    cursor = "0"
                if cursor == "0":
                    # Let in-flight batches finish first, or they'd be read (and rebuilt) twice
                    await asyncio.gather(*self._acks)
                    await self._ensure_group()
                    await self._claim_abandoned()

                entries = await self._read(cursor or ">")
                if cursor is not None:
                    if not entries:
                        cursor = None
                        continue
                    cursor = entries[-1][0]
                if entries:
                    self._handle(entries)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.stats["errors"] += 1
                print(f"[events] Consumer error, retrying in {RETRY_DELAY_S}s: {str(exc)[:200]}")
                cursor = "0"    # unacked events are still pending; read them again
                await asyncio.sleep(RETRY_DELAY_S)

    def _retry_delay(self) -> float:
        """Doubles with every consecutive failed rebuild: one that keeps failing (Mongo down)
        would otherwise be retried, reloading everything, every few seconds."""
        return min(RETRY_DELAY_S * 2 ** max(self._failed_rebuilds - 1, 0), MAX_RETRY_DELAY_S)

    async def _ensure_group(self) -> None:
        try:
            # id=0: a group created after events were published still reads them
            await self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _claim_abandoned(self) -> None:
        start = "0-0"
        while True:
            # Not justid=True: redis-py then returns only the ids and drops the cursor
            reply = await self._redis.xautoclaim(
                self._stream, self._group, self._consumer,
                min_idle_time=CLAIM_IDLE_MS, start_id=start, count=self._batch_size,
            )
            start = reply[0]
            if start in ("0-0", b"0-0"):
                return

    async def _read(self, start_id: str) -> List[tuple]:
        reply = await self._redis.xreadgroup(
            self._group, self._consumer, {self._stream: start_id},
            count=self._batch_size,
            block=self._block_ms if start_id == ">" else None,
        )
        return reply[0][1] if reply else []

    def _handle(self, entries: List[tuple]) -> None:
        # Mark the models stale and keep reading: events that arrive before the rebuild starts
        # join it, so a burst of ratings costs one rebuild however the reads split it up
        ids = [entry_id for entry_id, _ in entries]
        task = asyncio.create_task(self._ack_when_rebuilt(self._refresher.request(), ids))
        self._acks.add(task)
        task.add_done_callback(self._acks.discard)

    async def _ack_when_rebuilt(self, ticket: int, ids: List[str]) -> None:
        try:
            await self._refresher.wait_for(ticket)
            await self._redis.xack(self._stream, self._group, *ids)
        except Exception as exc:
            self.stats["errors"] += 1
            print(f"[events] {len(ids)} event(s) left pending for a retry: {str(exc)[:200]}")
            self._failed_rebuilds += 1
            self._needs_recovery = True
            return
        self._failed_rebuilds = 0
        self.stats["events"] += len(ids)
        self.stats["batches"] += 1
        self.stats["last_event_id"] = ids[-1]
        print(f"[events] Refreshed models for {len(ids)} rating event(s)")


def create_consumer(refresher: ModelRefresher) -> Optional[RatingEventConsumer]:
    """A consumer on REDIS_URL, or None when it isn't set. Connection errors are retried by run()."""
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    import redis.asyncio as aioredis

    client = aioredis.from_url(url, decode_responses=True, socket_connect_timeout=5)
    return RatingEventConsumer(client, refresher)
