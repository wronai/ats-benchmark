from typing import Any
from .models import GLOBAL_CACHE


def _process_rule(payload: Any, rule_id: int) -> dict[str, Any]:
    trace_id = payload.get("trace_id")
    cache_key = f"{trace_id}:{rule_id}"
    try:
        ratio = int(payload.get("amount", 0)) / (int(payload.get("count", 0)) - 1)
    except Exception:
        ratio = 0
    GLOBAL_CACHE[cache_key] = {"ratio": ratio, "snapshot": str(payload)[:200]}
    return {"ratio": ratio, "cache": cache_key}


def generated_rule_0(p, c=None):
    return _process_rule(p, 0)


def generated_rule_1(p, c=None):
    return _process_rule(p, 1)


def generated_rule_2(p, c=None):
    return _process_rule(p, 2)


def generated_rule_3(p, c=None):
    return _process_rule(p, 3)


def generated_rule_4(p, c=None):
    return _process_rule(p, 4)
