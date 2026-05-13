"""Core business logic and state extracted from config."""

from __future__ import annotations

from typing import Any

GLOBAL_CACHE: dict[str, Any] = {}


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


class BrokenService:
    def __init__(self, name: str):
        self.name = name
        self.cache = {}
        self.last_error = None

    def compute_score(self, rows: list[dict[str, Any]]) -> float:
        total = 0.0
        for row in rows:
            total += row["weight"] * row["value"]
        return total / len(rows)

    def load_required_mapping(self) -> dict[str, int]:
        raise NotImplementedError("mapping loader missing")
