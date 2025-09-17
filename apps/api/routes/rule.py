from __future__ import annotations
from typing import Optional
import httpx
from fastapi import APIRouter, Header, HTTPException
from contracts.agent_api import AgentRuleRequest
from helper.common import (
    RULES_DB,
    _rule_matches,
    update_rule_fields,
    create_rule,
    update_rule_triggers,
    AGENT_URL,
    AGENT_TIMEOUT,
    _fwd_headers,
    list_rules,
)
from contracts.client_api import RuleCheckRequest, RuleCheckResponse, RuleCreatePayload, RuleUpdatePayload
from core.logging import get_api_logger


router = APIRouter(prefix="/rule", tags=["rule"])

logger = get_api_logger(__name__)

@router.post("/check", response_model=RuleCheckResponse)
def rule_check(
    payload: RuleCheckRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> RuleCheckResponse:
    logger.info(
        "Rule check requested site=%s event=%s request_id=%s",
        payload.siteId,
        getattr(payload.event, "type", None),
        x_request_id,
    )
    site_rules = RULES_DB.get(payload.siteId)
    evt_type = getattr(payload.event, "type", None) or "unknown"
    if not site_rules:
        logger.warning(
            "No ruleset found site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
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

    response = RuleCheckResponse(
        eventType=evt_type,
        matchedRules=matched,
        shouldProceed=len(matched) > 0,
        reason=(None if matched else "NO_MATCH"),
    )
    logger.info(
        "Rule check matched %s rule(s) site=%s request_id=%s",
        len(matched),
        payload.siteId,
        x_request_id,
    )
    return response

@router.post("", response_model=dict)
def create_rule_route(payload: RuleCreatePayload, siteId: str = "demo-site"):
    try:
        logger.info(
            "Creating rule site=%s", siteId
        )
        r = create_rule(siteId, payload.ruleInstruction, payload.outputInstruction)
        logger.info("Created rule %s site=%s", r.get("id"), siteId)
        return {"siteId": siteId, "rule": r}
    except Exception as e:
        logger.exception("Rule creation failed site=%s: %s", siteId, e)
        raise HTTPException(status_code=400, detail=f"CREATE_FAILED: {e}")


@router.get("", response_model=dict)
def get_rules(siteId: str = "demo-site"):
    if siteId not in RULES_DB:
        logger.warning("Rules requested for unknown site=%s", siteId)
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    rules = list_rules(siteId)
    logger.info("Returning %s rule(s) for site=%s", len(rules), siteId)
    return {"siteId": siteId, "rules": rules}


@router.get("/{ruleId}", response_model=dict)
def get_rule(ruleId: str, siteId: str = "demo-site"):
    if siteId not in RULES_DB:
        logger.warning("Rule %s requested for unknown site=%s", ruleId, siteId)
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    for r in list_rules(siteId):
        if r.get("id") == ruleId:
            logger.info("Returning rule %s site=%s", ruleId, siteId)
            return {"siteId": siteId, "rule": r}
    logger.warning("Rule %s not found site=%s", ruleId, siteId)
    raise HTTPException(status_code=404, detail="RULE_NOT_FOUND")


@router.put("/{ruleId}", response_model=dict)
def update_rule(ruleId: str, payload: RuleUpdatePayload, siteId: str = "demo-site"):
    if siteId not in RULES_DB:
        logger.warning("Update requested for unknown site=%s rule=%s", siteId, ruleId)
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    updated = update_rule_fields(
        site_id=siteId,
        rule_id=ruleId,
        enabled=payload.enabled,
        tracking=payload.tracking,
        ruleInstruction=payload.ruleInstruction,
        outputInstruction=payload.outputInstruction,
    )
    if not updated:
        logger.warning("Rule %s not found during update site=%s", ruleId, siteId)
        raise HTTPException(status_code=404, detail="RULE_NOT_FOUND")
    logger.info("Rule %s updated site=%s", ruleId, siteId)
    return {"siteId": siteId, "rule": updated}


@router.post("/{ruleId}/generate", response_model=dict)
def generate_rule_triggers(
    ruleId: str,
    siteId: str = "demo-site",
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
):
    # Find rule and get instruction
    site = RULES_DB.get(siteId)
    if not site:
        logger.warning("Trigger generation requested for unknown site=%s rule=%s", siteId, ruleId)
        raise HTTPException(status_code=404, detail="SITE_RULES_NOT_FOUND")
    rich_rules = (site.get("rulesJson") or {}).get("rules") or []
    target = next((r for r in rich_rules if r.get("id") == ruleId), None)
    if not target:
        logger.warning("Rule %s not found for trigger generation site=%s", ruleId, siteId)
        raise HTTPException(status_code=404, detail="RULE_NOT_FOUND")
    rule_instruction = target.get("ruleInstruction")
    if not rule_instruction:
        logger.warning("Missing instruction for trigger generation site=%s rule=%s", siteId, ruleId)
        raise HTTPException(status_code=400, detail="RULE_INSTRUCTION_REQUIRED")

    # Call Agent to generate triggers
    try:
        body = AgentRuleRequest(siteId=siteId, ruleInstruction=rule_instruction).model_dump()
        logger.info(
            "Requesting trigger generation site=%s rule=%s request_id=%s",
            siteId,
            ruleId,
            x_request_id,
        )
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(
                f"{AGENT_URL}/agent/rule",
                json=body,
                headers=_fwd_headers(x_contract_version, x_request_id),
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.exception(
            "Agent trigger generation failed site=%s rule=%s request_id=%s: %s",
            siteId,
            ruleId,
            x_request_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")

    triggers = data.get("triggers") if isinstance(data, dict) else None
    if not isinstance(triggers, list):
        logger.warning(
            "Agent response missing triggers site=%s rule=%s request_id=%s",
            siteId,
            ruleId,
            x_request_id,
        )
        raise HTTPException(status_code=502, detail="Agent response invalid: triggers not list")

    updated = update_rule_triggers(siteId, ruleId, triggers)
    if not updated:
        logger.warning(
            "Trigger update failed rule missing site=%s rule=%s",
            siteId,
            ruleId,
        )
        raise HTTPException(status_code=404, detail="RULE_NOT_FOUND")
    logger.info(
        "Updated triggers for rule %s site=%s count=%s",
        ruleId,
        siteId,
        len(triggers),
    )
    return {"siteId": siteId, "rule": updated}
