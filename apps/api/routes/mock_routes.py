# apps/api/routes/mock_routes.py
from __future__ import annotations
import os, re
from typing import Any, Dict, List, Optional
from time import time

import httpx
from fastapi import APIRouter, Header, HTTPException

from contracts.sdk_api import (
    APIHealthResponse,
    RuleCheckRequest,
    RuleCheckResponse,
    SuggestGetRequest,
    SuggestGetResponse,
    Turn,
    SiteMapRequest, SiteMapResponse,
    SiteInfoRequest, SiteInfoResponse,
    SiteAtlasRequest, SiteAtlasResponse,
)

router = APIRouter(prefix="", tags=["api-mock"])

# ==============================================================================
# Rule engine mock (per-site rulesets)
# ==============================================================================

# Minimal rules so POC works: trigger when cartCount >= 2
RULES_DB: Dict[str, Dict[str, Any]] = {
    "demo-site": {
        "version": "ruleset-001",
        "rules": [
            {
                "id": "cart_gte_2",
                "enabled": True,
                "eventType": ["dom_click", "add_to_cart"],
                "when": [
                    {"field": "telemetry.attributes.cartCount", "op": "gte", "value": 2}
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

# ==============================================================================
# /rule/check
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
        return RuleCheckResponse(eventType=evt_type, matchedRules=[], shouldProceed=False, reason="SITE_RULES_NOT_FOUND")

    matched = [r["id"] for r in site_rules.get("rules", []) if r.get("enabled", True) and _rule_matches(r, payload)]
    return RuleCheckResponse(
        eventType=evt_type,
        matchedRules=matched,
        shouldProceed=len(matched) > 0,
        reason=(None if matched else "NO_MATCH"),
    )

# ==============================================================================
# /suggest/get → proxy to Agent (port 5001)
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
    body = payload.model_dump()
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(f"{AGENT_URL}/agent/suggest/next", json=body, headers=_fwd_headers(x_contract_version, x_request_id))
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")
    try:
        turn = Turn.model_validate(data["turn"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent response invalid: {e}")
    return SuggestGetResponse(turn=turn)

# ==============================================================================
# /site/map
# ==============================================================================
@router.get("/site/map", response_model=SiteMapResponse)
def get_site_map(siteId: str) -> SiteMapResponse:
    return SiteMapResponse(siteId=siteId, pages=[])

@router.post("/site/map", response_model=SiteMapResponse)
def build_site_map(payload: SiteMapRequest) -> SiteMapResponse:
    return SiteMapResponse(siteId=payload.siteId, pages=[])

# ==============================================================================
# /site/info
# ==============================================================================
@router.get("/site/info", response_model=SiteInfoResponse)
def get_site_info(siteId: str, url: str) -> SiteInfoResponse:
    return SiteInfoResponse(siteId=siteId, url=url, meta=None, normalized=None)

@router.post("/site/info", response_model=SiteInfoResponse)
def drag_site_info(payload: SiteInfoRequest) -> SiteInfoResponse:
    return SiteInfoResponse(siteId=payload.siteId, url=payload.url, meta=None, normalized=None)

# ==============================================================================
# /site/atlas
# ==============================================================================
@router.get("/site/atlas", response_model=SiteAtlasResponse)
def get_site_atlas(siteId: str, url: str) -> SiteAtlasResponse:
    return SiteAtlasResponse(siteId=siteId, url=url, atlas=None, queuedPlanRebuild=None)

@router.post("/site/atlas", response_model=SiteAtlasResponse)
def drag_site_atlas(payload: SiteAtlasRequest) -> SiteAtlasResponse:
    return SiteAtlasResponse(siteId=payload.siteId, url=payload.url, atlas=None, queuedPlanRebuild=None)

# ==============================================================================
# /health
# ==============================================================================
@router.get("/health", response_model=APIHealthResponse)
def health() -> APIHealthResponse:
    return {"ok": True, "version": "mock-0.6", "ts": time()}
