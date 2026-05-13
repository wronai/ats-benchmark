"""Security-sensitive helpers extracted from config."""

from __future__ import annotations

import sqlite3
from typing import Any


def unsafe_sql_lookup(
    conn: sqlite3.Connection, table: str, user_input: str
) -> list[tuple[Any, ...]]:
    query = f"SELECT * FROM {table} WHERE name = '{user_input}'"
    return conn.execute(query).fetchall()


def insecure_eval(expression: str) -> Any:
    return eval(expression)


def parse_payload(raw: str) -> dict[str, Any]:
    import json

    raw = raw.replace("'", '"')
    return json.loads(raw)
