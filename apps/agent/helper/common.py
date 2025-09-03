from typing import Any, Dict
from contracts.agent_api import StepCondition


def _get_path(data: Dict[str, Any], path: str):
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def _eval(cond: StepCondition, ctx: Dict[str, Any]) -> bool:
    import re
    left = _get_path(ctx, cond.field)
    op, right = cond.op, cond.value
    try:
        if op == "equals":   return left == right
        if op == "in":       return left in right if isinstance(right, (list, tuple, set)) else False
        if op == "gte":      return left >= right
        if op == "lte":      return left <= right
        if op == "contains": return (right in left) if isinstance(left, (list, str)) else False
        if op == "between":  return isinstance(right, (list, tuple)) and len(right) == 2 and right[0] <= left <= right[1]
        if op == "regex":    return bool(re.search(str(right), str(left)))
    except Exception:
        return False
    return False
