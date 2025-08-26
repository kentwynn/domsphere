# apps/api/routes/mock_routes.py
from __future__ import annotations
import os, re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from time import time

import httpx
from fastapi import APIRouter, Header, HTTPException

from contracts.sdk_api import (
    APIHealthResponse,
    PageDragRequest,
    PageDragResponse,
    RuleCheckRequest,
    RuleCheckResponse,
    SuggestGetRequest,
    SuggestGetResponse,
    Turn,
    UrlDragRequest,
    UrlDragResponse,
)

router = APIRouter(prefix="", tags=["api-mock"])

# ==============================================================================
# Mock “DB” — per-site rule sets
# Structure:
#   rulesets[siteId] = {
#     "version": "...",
#     "rules": [
#       {
#         "id": "rule-id",
#         "enabled": true,
#         "eventType": ["add_to_cart","dom_click"],  # optional; match any if omitted
#         "when": [
#           {"field":"telemetry.attributes.cartCount", "op":"gte", "value":2}
#         ]
#       },
#       ...
#     ]
#   }
# ==============================================================================
RULES_DB: Dict[str, Dict[str, Any]] = {
    "demo-site": {
        "version": "ruleset-001",
        "rules": [
            {
                "id": "cart_gte_2",
                "enabled": True,
                "eventType": ["dom_click", "add_to_cart"],  # optional; omit to match any
                "when": [
                    {"field": "telemetry.attributes.cartCount", "op": "gte", "value": 2}
                ],
            },
            {
                "id": "free_ship_threshold",
                "enabled": True,
                # no eventType filter = matches any event type
                "when": [
                    {"field": "context.cartSubtotal", "op": "gte", "value": 49}
                ],
            },
        ],
    },
    # add more sites if needed
}

# Helper: dot-path getter for dict-like objects (pydantic models OK)
def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        # Handle pydantic models or attribute access
        if hasattr(cur, part):
            cur = getattr(cur, part)
            continue
        # Fallback to dict-like
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        return None
    return cur

def _op_eval(left: Any, op: str, right: Any) -> bool:
    try:
        if op == "equals":
            return left == right
        if op == "in":
            return left in right if isinstance(right, (list, tuple, set)) else False
        if op == "gte":
            return left is not None and right is not None and left >= right
        if op == "lte":
            return left is not None and right is not None and left <= right
        if op == "contains":
            if isinstance(left, str) and isinstance(right, str):
                return right in left
            if isinstance(left, (list, tuple, set)):
                return right in left
            return False
        if op == "between":
            # right expected as [lo, hi]
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
    # eventType filter (optional)
    allowed = rule.get("eventType")
    evt_type = getattr(payload.event, "type", None) or "unknown"
    if allowed and str(evt_type) not in set(map(str, allowed)):
        return False

    # Build a merged context space to allow rules to reference both event.* and context.* (if you pass it)
    # Our openapi model has no top-level context in RuleCheckRequest, so we only expose event.*
    # But we still support "context.*" to future-proof.
    scope = {
        "event": payload.event,
        "telemetry": getattr(payload.event, "telemetry", None),
        "context": {},  # put extra derived data here if you want
    }

    # Evaluate all conditions in "when"
    whens: List[Dict[str, Any]] = rule.get("when", [])
    for cond in whens:
        field = cond.get("field")
        op = cond.get("op")
        val = cond.get("value")
        # Field may be "telemetry.attributes.cartCount" (direct)
        # or "event.telemetry.attributes.cartCount" (fully-qualified)
        if field.startswith("event."):
            left = _get_path(scope, field)
        else:
            left = _get_path(scope, field) or _get_path(payload, field) or _get_path(payload.event, field)
        # Coerce numeric strings
        if isinstance(left, str) and left.isdigit():
            left = int(left)
        if _op_eval(left, op, val) is False:
            return False
    return True

# ==============================================================================
# /rule/check — evaluate against RULES_DB by siteId
# ==============================================================================
@router.post("/rule/check", response_model=RuleCheckResponse)
def rule_check(
    payload: RuleCheckRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> RuleCheckResponse:
    site_rules = RULES_DB.get(payload.siteId)
    evt_type = getattr(payload.event, "type", None) or "unknown"

    if not site_rules:
        # No rules found for site
        return RuleCheckResponse(
            eventType=str(evt_type),
            matchedRules=[],
            shouldProceed=False,
            reason="SITE_RULES_NOT_FOUND",
        )

    active_rules = [r for r in site_rules.get("rules", []) if r.get("enabled", True)]
    matched: List[str] = []
    for r in active_rules:
        if _rule_matches(r, payload):
            matched.append(r.get("id", "unnamed"))

    should_proceed = len(matched) > 0
    return RuleCheckResponse(
        eventType=str(evt_type),
        matchedRules=matched,
        shouldProceed=should_proceed,
        reason=(None if should_proceed else "NO_MATCH"),
    )

# ==============================================================================
# /suggest/get — STRICT PROXY to Agent on port 5001
# ==============================================================================
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:5001").rstrip("/")
AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT_SEC", "5.0"))

def _fwd_headers(xcv: Optional[str], xrid: Optional[str]) -> Dict[str, str]:
    h: Dict[str, str] = {}
    if xcv: h["X-Contract-Version"] = xcv
    if xrid: h["X-Request-Id"] = xrid
    return h

@router.post("/suggest/get", response_model=SuggestGetResponse)
def suggest_get(
    payload: SuggestGetRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    body = {
        "siteId": payload.siteId,
        "sessionId": payload.sessionId,
        "intentId": getattr(payload, "intentId", None),
        "prevTurnId": getattr(payload, "prevTurnId", None),
        "answers": getattr(payload, "answers", None),
        "context": payload.context,
    }
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(
                f"{AGENT_URL}/agent/suggest/next",
                json=body,
                headers=_fwd_headers(x_contract_version, x_request_id),
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")

    # validate shape; field names match
    try:
        turn = Turn.model_validate(data["turn"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent response invalid: {e}")

    return SuggestGetResponse(turn=turn)

# ==============================================================================
# /url/drag (mock)
# ==============================================================================
@router.post("/url/drag", response_model=UrlDragResponse)
def url_drag(
    payload: UrlDragRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> UrlDragResponse:
    return UrlDragResponse(jobId=f"job-{uuid4()}", queued=True)

# ==============================================================================
# /page/drag (mock)
# ==============================================================================
@router.post("/page/drag", response_model=PageDragResponse)
def page_drag(
    payload: PageDragRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> PageDragResponse:
    if payload.mode == "atlas":
        normalized = {
            "url": payload.url,
            "scrapedAt": time(),
            "elements": [
                {"selector": "[data-testid='product-card']", "count": 3},
                {"selector": "[data-testid='add']", "count": 3},
            ],
        }
        return PageDragResponse(atlas=None, normalized=normalized, queuedPlanRebuild=False)
    return PageDragResponse(atlas=None, normalized=None, queuedPlanRebuild=True)

# ==============================================================================
# /health
# ==============================================================================
@router.get("/health", response_model=APIHealthResponse)
def health() -> APIHealthResponse:
    return {"ok": True, "version": "mock-0.4", "ts": time()}
