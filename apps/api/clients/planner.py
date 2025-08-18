from typing import Dict, Any
import httpx
from config import PLANNER_URL, PLANNER_TOKEN

_client = httpx.Client(base_url=PLANNER_URL, timeout=10.0)

def call_planner_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    r = _client.post(
        "/plan",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": PLANNER_TOKEN,
        },
    )
    r.raise_for_status()
    return r.json()
