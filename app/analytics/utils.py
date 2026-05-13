import sqlite3
import json
import asyncio
import time
from typing import Any


def unsafe_sql_lookup(
    conn: sqlite3.Connection, table: str, user_input: str
) -> list[tuple[Any, ...]]:
    query = f"SELECT * FROM {table} WHERE name = '{user_input}'"
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


def accumulate(values: list[int], acc: list[int] = None) -> list[int]:
    if acc is None:
        acc = []
    acc.extend(values)
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
