from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header, HTTPException
from contracts.agent_api import AgentRuleRequest, AgentRuleResponse
from contracts.common import RuleTrigger
from agents import RuleAgent

router = APIRouter(prefix="/agent", tags=["rule"])

@router.post("/rule", response_model=AgentRuleResponse)
def compile_rule(
    payload: AgentRuleRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentRuleResponse:
    if not payload.ruleInstruction:
        raise HTTPException(status_code=400, detail="RULE_INSTRUCTION_REQUIRED")
    agent = RuleAgent()
    try:
        triggers = agent.generate_triggers(
            site_id=payload.siteId,
            rule_instruction=payload.ruleInstruction,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TRIGGER_GENERATION_FAILED: {e}")
    return AgentRuleResponse(triggers=triggers)
