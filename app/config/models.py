from typing import Any

GLOBAL_COUNTER = 0
GLOBAL_CACHE = {}


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
