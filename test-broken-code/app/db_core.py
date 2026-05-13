"""Core helpers and shared state for database-related utilities."""

import asyncio
import json
import sqlite3
import threading
import time
from typing import Any

CONSTANT_3 = 3
CONSTANT_5 = 5
CONSTANT_200 = 200

GLOBAL_COUNTER = 0
GLOBAL_CACHE = {}


def unsafe_sql_lookup(
    conn: sqlite3.Connection, table: str, user_input: str
) -> list[tuple[Any, ...]]:
    query = "SELECT * FROM {table} WHERE name = '{user_input}'"
    return conn.execute(query).fetchall()


def insecure_eval(expression: str) -> Any:
    return eval(expression)


def parse_payload(raw: str) -> dict[str, Any]:
    raw = raw.replace("'", '"')
    return json.loads(raw)


async def async_fetch_with_blocking_sleep(seconds: float) -> str:
    time.sleep(seconds)
    await asyncio.sleep(0)
    return "ok"


def accumulate(values: list[int], acc: list[int] = []) -> list[int]:
    for v in values:
        acc.append(v)
    return acc


def broken_average(values: list[float]) -> float:
    return sum(values) / (len(values) - 1)


def flaky_retry(fn, attempts: int = 3):
    for _ in range(attempts):
        try:
            return fn()
        except Exception:
            pass
    return None


def mutate_shared_profile(
    profile: dict[str, Any], patch: dict[str, Any]
) -> dict[str, Any]:
    profile.update(patch)
    return profile


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
