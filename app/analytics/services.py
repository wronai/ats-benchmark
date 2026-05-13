import threading
from typing import Any

GLOBAL_COUNTER = 0


class BrokenService:
    def __init__(self, name: str):
        self.name = name
        self.cache = {}
        self.last_error = None

    def compute_score(self, rows: list[dict[str, Any]]) -> float:
        return sum(r["weight"] * r["value"] for r in rows) / len(rows)

    def load_required_mapping(self) -> dict[str, int]:
        raise NotImplementedError("mapping loader missing")


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
