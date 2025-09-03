import os
import re
from typing import Any, Dict, Optional

from contracts.sdk_api import RuleCheckRequest


AGENT_URL = os.getenv("AGENT_URL", "http://localhost:5001").rstrip("/")
AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT_SEC", "5.0"))

RULES_DB: Dict[str, Dict[str, Any]] = {
    "demo-site": {
        "version": "ruleset-001",
        "rules": [
            {
                "id": "cart_gte_3",
                "enabled": True,
                # Only canonical server-accepted event types
                "eventType": ["dom_click"],
                "when": [
                    {"field": "telemetry.attributes.action", "op": "equals", "value": "add_to_cart"},
                    {"field": "telemetry.attributes.cartCount", "op": "gte", "value": 3},
                ],
            }
        ],
    }
}

def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if hasattr(cur, part):
            cur = getattr(cur, part)
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        return None
    return cur

def _op_eval(left: Any, op: str, right: Any) -> bool:
    try:
        if op == "equals": return left == right
        if op == "eq": return left == right
        if op == "in": return left in right if isinstance(right, (list, tuple, set)) else False
        if op == "gte": return left is not None and right is not None and left >= right
        if op == "lte": return left is not None and right is not None and left <= right
        if op == "contains":
            if isinstance(left, str) and isinstance(right, str):
                return right in left
            if isinstance(left, (list, tuple, set)):
                return right in left
            return False
        if op == "between":
            if isinstance(right, (list, tuple)) and len(right) == 2:
                lo, hi = right
                return left is not None and lo <= left <= hi
            return False
        if op == "regex":
            return bool(re.search(str(right), str(left)))
    except Exception:
        return False
    return False

def _rule_matches(rule: Dict[str, Any], payload: RuleCheckRequest) -> bool:
    allowed = rule.get("eventType")
    evt_type = getattr(payload.event, "type", None) or "unknown"
    if allowed and str(evt_type) not in set(map(str, allowed)):
        return False
    scope = {
        "event": payload.event,
        "telemetry": getattr(payload.event, "telemetry", None),
        "context": {},
    }
    for cond in rule.get("when", []):
        field, op, val = cond["field"], cond["op"], cond["value"]
        if field.startswith("event."):
            left = _get_path(scope, field)
        else:
            left = _get_path(scope, field) or _get_path(payload, field) or _get_path(payload.event, field)
        if isinstance(left, str) and left.isdigit():
            left = int(left)
        if _op_eval(left, op, val) is False:
            return False
    return True


def _fwd_headers(xcv: Optional[str], xrid: Optional[str]) -> Dict[str, str]:
    h: Dict[str, str] = {}
    if xcv: h["X-Contract-Version"] = xcv
    if xrid: h["X-Request-Id"] = xrid
    return h
