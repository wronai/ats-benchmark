"""Async and threading-related utilities."""

import asyncio
import threading
import time

GLOBAL_COUNTER = 0


async def async_fetch_with_blocking_sleep(seconds: float) -> str:
    time.sleep(seconds)
    await asyncio.sleep(0)
    return "ok"


def non_atomic_increment(n: int = 1000) -> int:
    global GLOBAL_COUNTER

    def worker():
        global GLOBAL_COUNTER
        for _ in range(n):
            GLOBAL_COUNTER += 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return GLOBAL_COUNTER
