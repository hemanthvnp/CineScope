"""
Tests for the event-driven model refresh: the refresher's coalescing and the Redis Stream
consumer's delivery guarantees. Redis is replaced by an in-memory fake of the stream commands.

Run with:  pytest services/ml-service/tests/test_rating_events.py -v
"""
import asyncio
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from events import RatingEventConsumer
from refresher import ModelRefresher


class CountingModels:
    """Stands in for prepare_models / install_models."""

    def __init__(self, fail_times=0):
        self.prepared = 0
        self.installed = []
        self.fail_times = fail_times
        self.prepare_threads = set()

    def prepare(self):
        self.prepare_threads.add(threading.get_ident())
        self.prepared += 1
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("mongo unavailable")
        return self.prepared

    def install(self, snapshot):
        self.installed.append(snapshot)


class FakeStreamRedis:
    """The XGROUP / XREADGROUP / XACK / XAUTOCLAIM subset the consumer uses, one stream, one group."""

    def __init__(self):
        self.entries = []          # [(id, fields)]
        self.group = None          # index of the last entry delivered to the group
        self.pending = {}          # id → consumer
        self._seq = 0

    def add(self, **fields):
        self._seq += 1
        self.entries.append((f"{self._seq}-0", fields))

    async def xgroup_create(self, stream, group, id="$", mkstream=False):
        if self.group is not None:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.group = 0 if id == "0" else len(self.entries)

    async def xautoclaim(self, stream, group, consumer, min_idle_time, start_id, count):
        for entry_id in self.pending:
            self.pending[entry_id] = consumer     # every pending entry counts as idle here
        claimed = [e for e in self.entries if e[0] in self.pending]
        return ["0-0", claimed, []]               # redis-py's reply: [next cursor, entries, deleted ids]

    async def xreadgroup(self, group, consumer, streams, count, block=None):
        (stream, start), = streams.items()
        if start != ">":
            # Pending entries after `start`. Real Redis answers with the stream and an empty list, not nothing
            after = int(start.split("-")[0])
            mine = [e for e in self.entries if self.pending.get(e[0]) == consumer and int(e[0].split("-")[0]) > after]
            return [[stream, mine[:count]]]
        batch = self.entries[self.group:self.group + count]
        self.group += len(batch)
        for entry_id, _ in batch:
            self.pending[entry_id] = consumer
        if not batch:
            await asyncio.sleep(0.01)             # stands in for BLOCK
        return [[stream, batch]] if batch else []

    async def xack(self, stream, group, *ids):
        for entry_id in ids:
            self.pending.pop(entry_id, None)


async def _until(condition, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


# ── Refresher ─────────────────────────────────────────────────────────────────

class TestModelRefresher:

    def test_burst_of_requests_costs_one_rebuild(self):
        async def scenario():
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0.05)
            worker = asyncio.create_task(refresher.run())
            await asyncio.gather(*[refresher.refresh() for _ in range(10)])
            worker.cancel()
            return models, refresher

        models, refresher = asyncio.run(scenario())
        assert models.prepared == 1
        assert models.installed == [1]
        assert refresher.stats["requests"] == 10
        assert refresher.stats["rebuilds"] == 1

    def test_request_during_a_rebuild_gets_a_new_one(self):
        """A rating written after the rebuild read the data must not be reported as included."""
        async def scenario():
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0.01)
            worker = asyncio.create_task(refresher.run())
            first = refresher.request()
            await _until(lambda: models.prepared == 1)
            second = refresher.request()
            await refresher.wait_for(first)
            await refresher.wait_for(second)
            worker.cancel()
            return models

        assert asyncio.run(scenario()).prepared == 2

    def test_fitting_runs_off_the_event_loop_thread(self):
        async def scenario():
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0)
            worker = asyncio.create_task(refresher.run())
            await refresher.refresh()
            worker.cancel()
            return models

        models = asyncio.run(scenario())
        assert threading.get_ident() not in models.prepare_threads

    def test_failed_rebuild_raises_and_keeps_old_models(self):
        async def scenario():
            models = CountingModels(fail_times=1)
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0)
            worker = asyncio.create_task(refresher.run())
            with pytest.raises(RuntimeError):
                await refresher.refresh()
            assert models.installed == []
            await refresher.refresh()           # the next request rebuilds again
            worker.cancel()
            return models, refresher

        models, refresher = asyncio.run(scenario())
        assert models.installed == [2]
        assert refresher.stats["failures"] == 1


# ── Consumer ──────────────────────────────────────────────────────────────────

def _consumer(redis, refresher):
    return RatingEventConsumer(redis, refresher, consumer="ml-1", block_ms=10, batch_size=100)


class TestRatingEventConsumer:

    def test_backlog_is_read_as_one_batch_and_acked(self):
        async def scenario():
            redis = FakeStreamRedis()
            for movie_id in range(5):                    # published while the service was down
                redis.add(type="rating.created", movieId=str(movie_id))
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0)
            consumer = _consumer(redis, refresher)
            tasks = [asyncio.create_task(refresher.run()), asyncio.create_task(consumer.run())]
            await _until(lambda: consumer.stats["events"] == 5)
            for t in tasks:
                t.cancel()
            return redis, models, consumer

        redis, models, consumer = asyncio.run(scenario())
        assert models.prepared == 1
        assert consumer.stats["batches"] == 1
        assert redis.pending == {}

    def test_events_stay_pending_until_a_rebuild_succeeds(self, monkeypatch):
        monkeypatch.setattr("events.RETRY_DELAY_S", 0.01)

        async def scenario():
            redis = FakeStreamRedis()
            redis.add(type="rating.created", movieId="1")
            models = CountingModels(fail_times=1)
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0)
            consumer = _consumer(redis, refresher)
            tasks = [asyncio.create_task(refresher.run()), asyncio.create_task(consumer.run())]
            await _until(lambda: consumer.stats["errors"] == 1)
            assert redis.pending == {"1-0": "ml-1"}      # failed rebuild: not acked
            await _until(lambda: consumer.stats["events"] == 1)
            for t in tasks:
                t.cancel()
            return redis, models

        redis, models = asyncio.run(scenario())
        assert redis.pending == {}
        assert models.installed == [2]

    def test_retries_of_a_failing_rebuild_back_off(self, monkeypatch):
        monkeypatch.setattr("events.RETRY_DELAY_S", 5)
        monkeypatch.setattr("events.MAX_RETRY_DELAY_S", 300)
        consumer = _consumer(FakeStreamRedis(), ModelRefresher(lambda: None, lambda _: None))
        delays = []
        for failures in range(1, 9):
            consumer._failed_rebuilds = failures
            delays.append(consumer._retry_delay())
        assert delays == [5, 10, 20, 40, 80, 160, 300, 300]

    def test_pending_events_of_a_dead_consumer_are_claimed(self):
        async def scenario():
            redis = FakeStreamRedis()
            redis.add(type="rating.created", movieId="1")
            await redis.xgroup_create("s", "g", id="0")
            await redis.xreadgroup("g", "old-host", {"s": ">"}, count=10)   # delivered, never acked
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0)
            consumer = _consumer(redis, refresher)
            tasks = [asyncio.create_task(refresher.run()), asyncio.create_task(consumer.run())]
            await _until(lambda: consumer.stats["events"] == 1)
            for t in tasks:
                t.cancel()
            return redis

        assert asyncio.run(scenario()).pending == {}

    def test_events_read_separately_still_share_a_rebuild(self):
        """Events arriving one by one, each its own read, while a rebuild is pending, join that rebuild."""
        async def scenario():
            redis = FakeStreamRedis()
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0.2)
            consumer = _consumer(redis, refresher)
            tasks = [asyncio.create_task(refresher.run()), asyncio.create_task(consumer.run())]
            for movie_id in range(3):
                redis.add(type="rating.created", movieId=str(movie_id))
                await asyncio.sleep(0.03)
            await _until(lambda: consumer.stats["events"] == 3)
            for t in tasks:
                t.cancel()
            return models, consumer

        models, consumer = asyncio.run(scenario())
        assert consumer.stats["batches"] == 3 and models.prepared == 1

    def test_live_events_trigger_a_refresh(self):
        async def scenario():
            redis = FakeStreamRedis()
            models = CountingModels()
            refresher = ModelRefresher(models.prepare, models.install, debounce_s=0)
            consumer = _consumer(redis, refresher)
            tasks = [asyncio.create_task(refresher.run()), asyncio.create_task(consumer.run())]
            await asyncio.sleep(0.05)
            redis.add(type="rating.created", movieId="7")
            await _until(lambda: consumer.stats["events"] == 1)
            for t in tasks:
                t.cancel()
            return models

        assert asyncio.run(scenario()).prepared == 1
