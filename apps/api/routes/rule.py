from __future__ import annotations
from typing import Optional, Any, Dict, List
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from helper.common import RULES_DB, _rule_matches, update_rule_fields
from contracts.sdk_api import RuleCheckRequest, RuleCheckResponse

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

    matched: list[str] = []

    # Prefer flat rules if present
    flat_rules = site_rules.get("rules", [])
    if flat_rules:
        matched = [
            r["id"]
            for r in flat_rules
            if r.get("enabled", True) and _rule_matches(r, payload)
        ]
    else:
        # Fallback: evaluate compiled-style rulesJson with triggers
        rj = (site_rules or {}).get("rulesJson", {})
        for r in rj.get("rules", []):
            if not r.get("enabled", True):
                continue
            for trg in r.get("triggers", []):
                trg_rule = {
                    "eventType": [trg.get("eventType")],
                    "when": trg.get("when", []),
                }
                if _rule_matches(trg_rule, payload):
                    matched.append(r.get("id"))
                    break

    return RuleCheckResponse(
        eventType=evt_type,
        matchedRules=matched,
        shouldProceed=len(matched) > 0,
        reason=(None if matched else "NO_MATCH"),
    )

class RuleUpdatePayload(BaseModel):
    enabled: Optional[bool] = None
    tracking: Optional[bool] = None
    llmInstruction: Optional[str] = None


def _list_rules(siteId: str) -> List[Dict[str, Any]]:
    site = RULES_DB.get(siteId) or {}
    rj = site.get("rulesJson") or {}
    rich = rj.get("rules") or []
    if rich:
        return rich
    # fallback to flat rules; project minimal fields
    flat = site.get("rules") or []
    out: List[Dict[str, Any]] = []
    for r in flat:
        out.append({
            "id": r.get("id"),
            "enabled": r.get("enabled", True),
            "tracking": r.get("tracking", False),
            "llmInstruction": r.get("llmInstruction"),
        })
    return out


@router.get("", response_model=dict)
def get_rules(siteId: str = "demo-site"):
    if siteId not in RULES_DB:
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    return {"siteId": siteId, "rules": _list_rules(siteId)}


@router.get("/{ruleId}", response_model=dict)
def get_rule(ruleId: str, siteId: str = "demo-site"):
    if siteId not in RULES_DB:
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    for r in _list_rules(siteId):
        if r.get("id") == ruleId:
            return {"siteId": siteId, "rule": r}
    raise HTTPException(status_code=404, detail="RULE_NOT_FOUND")


@router.put("/{ruleId}", response_model=dict)
def update_rule(ruleId: str, payload: RuleUpdatePayload, siteId: str = "demo-site"):
    if siteId not in RULES_DB:
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    updated = update_rule_fields(
        site_id=siteId,
        rule_id=ruleId,
        enabled=payload.enabled,
        tracking=payload.tracking,
        llmInstruction=payload.llmInstruction,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="RULE_NOT_FOUND")
    return {"siteId": siteId, "rule": updated}
