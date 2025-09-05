from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Header
from helper.common import RULES_DB, _rule_matches
from contracts.sdk_api import RuleCheckRequest, RuleCheckResponse, RuleTrackRequest, RuleTrackResponse

router = APIRouter(prefix="/rule", tags=["rule"])

@router.post("/check", response_model=RuleCheckResponse)
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

@router.post("/track", response_model=RuleTrackResponse)
def rule_track_post(
    payload: RuleTrackRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> RuleTrackResponse:
    return RuleTrackResponse(
        siteId=payload.siteId,
        status=payload.status or "off",
        version=payload.version or "ruleset-001",
        updatedAt=None,
        events=payload.events or {},
    )

@router.get("/track", response_model=RuleTrackResponse)
def rule_track_get(
    siteId: str = "demo-site",
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> RuleTrackResponse:
    return RuleTrackResponse(
        siteId=siteId,
        status="on",
        version="ruleset-001",
        updatedAt=None,
        events={
            "dom_click": [
                "[data-action='add_to_cart']"
            ],
            "mutation": [
                "#cart-count",
            ],
        },
    )
