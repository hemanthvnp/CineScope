"""
Model refresher — one rebuild at a time, however many refreshes are asked for.

Every new rating used to rebuild both models inline, blocking the event loop for the whole
rebuild, so a user rating five movies in a row froze the service five times. Now a refresh
request just marks the models stale; a single background worker waits `debounce_s` for more
requests to arrive, then rebuilds once for all of them. The data loading and fitting run in a
worker thread, and the result is swapped in back on the event loop.

`await refresh()` returns once a rebuild that started *after* the call has finished, so a
caller knows the ratings it is reporting are in the live model.
"""
from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any, Callable, Optional


class ModelRefresher:

    def __init__(
        self,
        prepare: Callable[[], Any],
        install: Callable[[Any], None],
        debounce_s: float = 2.0,
    ) -> None:
        self._prepare = prepare          # slow, thread-safe: loads data and fits models
        self._install = install          # fast, run on the loop: swaps the fitted models in
        self._debounce_s = debounce_s
        self._requested = 0              # refresh requests so far
        self._covered = 0                # requests included in the last finished rebuild
        self._wake = asyncio.Event()
        self._done = asyncio.Condition()
        self._last_error: Optional[BaseException] = None
        self.stats = {"requests": 0, "rebuilds": 0, "failures": 0, "last_rebuild_ms": None}

    def request(self) -> int:
        """Mark the models stale without waiting. Returns a ticket for wait_for()."""
        self._requested += 1
        self.stats["requests"] += 1
        self._wake.set()
        return self._requested

    async def wait_for(self, ticket: int) -> None:
        """Wait until a rebuild covering `ticket` finishes; raises if the latest rebuild failed."""
        async with self._done:
            await self._done.wait_for(lambda: self._covered >= ticket)
            if self._last_error is not None:
                raise RuntimeError("model rebuild failed") from self._last_error

    async def refresh(self) -> None:
        await self.wait_for(self.request())

    async def run(self) -> None:
        """The single rebuild worker. Runs for the lifetime of the service."""
        while True:
            await self._wake.wait()
            await asyncio.sleep(self._debounce_s)   # let a burst of ratings collapse into one rebuild
            self._wake.clear()
            covered = self._requested

            t0 = time.monotonic()
            error: Optional[BaseException] = None
            try:
                snapshot = await asyncio.to_thread(self._prepare)
                self._install(snapshot)
                self.stats["rebuilds"] += 1
            except Exception as exc:
                error = exc
                self.stats["failures"] += 1
                print(f"[refresher] Model rebuild failed: {exc}")
                traceback.print_exc()
            self.stats["last_rebuild_ms"] = int((time.monotonic() - t0) * 1000)

            async with self._done:
                self._covered = covered
                self._last_error = error
                self._done.notify_all()
