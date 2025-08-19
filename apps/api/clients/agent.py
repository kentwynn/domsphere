from typing import Dict, Any
import httpx
from config import AGENT_URL, AGENT_TOKEN

_client = httpx.Client(base_url=AGENT_URL, timeout=10.0)

def call_agent_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    r = _client.post(
        "/plan",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": AGENT_TOKEN,
        },
    )
    r.raise_for_status()
    return r.json()
