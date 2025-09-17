from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Header, HTTPException

from contracts.agent_api import AgentRuleRequest, AgentRuleResponse
from contracts.common import RuleTrigger
from agents import RuleAgent
from core.logging import get_agent_logger

router = APIRouter(prefix="/agent", tags=["rule"])

logger = get_agent_logger(__name__)

@router.post("/rule", response_model=AgentRuleResponse)
def compile_rule(
    payload: AgentRuleRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentRuleResponse:
    if not payload.ruleInstruction:
        logger.warning(
            "Missing rule instruction for site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        raise HTTPException(status_code=400, detail="RULE_INSTRUCTION_REQUIRED")
    agent = RuleAgent()
    try:
        instruction_preview = payload.ruleInstruction[:120]
        logger.info(
            "Generating rule triggers for site=%s request_id=%s instruction=%.80s",
            payload.siteId,
            x_request_id,
            instruction_preview,
        )
        triggers = agent.generate_triggers(
            site_id=payload.siteId,
            rule_instruction=payload.ruleInstruction,
        )
        logger.info(
            "Generated %s trigger(s) for site=%s request_id=%s",
            len(triggers),
            payload.siteId,
            x_request_id,
        )
    except Exception as e:
        logger.exception(
            "Trigger generation failed for site=%s request_id=%s: %s",
            payload.siteId,
            x_request_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"TRIGGER_GENERATION_FAILED: {e}")
    return AgentRuleResponse(triggers=triggers)
