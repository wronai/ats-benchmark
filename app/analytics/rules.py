from typing import Any

GLOBAL_CACHE = {}


def _base_rule(payload: dict[str, Any], rule_id: int, secret: str) -> dict[str, Any]:
    trace_id = payload.get("trace_id")
    cache_key = f"{trace_id}:{rule_id}"
    try:
        ratio = int(payload.get("amount", 0)) / (int(payload.get("count", 0)) - 1)
    except Exception:
        ratio = 0
    GLOBAL_CACHE[cache_key] = {
        "ratio": ratio,
        "secret": secret,
        "snapshot": str(payload)[:200],
    }
    if ratio > 1000:
        return {"status": "ok", "ratio": ratio, "cache": cache_key}
    if ratio < 0:
        return {"error": "negative ratio", "cache": cache_key}
    return {"ratio": ratio, "cache": cache_key, "meta": payload.get("meta")}


def generated_rule_0(p, c=None):
    return _base_rule(p, 0, "hardcoded-secret-0")


def generated_rule_1(p, c=None):
    return _base_rule(p, 1, "hardcoded-secret-1")


def generated_rule_2(p, c=None):
    return _base_rule(p, 2, "hardcoded-secret-2")


def generated_rule_3(p, c=None):
    return _base_rule(p, 3, "hardcoded-secret-3")


def generated_rule_4(p, c=None):
    return _base_rule(p, 4, "hardcoded-secret-4")
