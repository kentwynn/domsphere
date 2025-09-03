from typing import Optional
from fastapi import APIRouter, Header
from contracts.agent_api import AgentRuleRequest, AgentRuleResponse

router = APIRouter(prefix="/agent", tags=["rule"])

@router.post("/rule", response_model=AgentRuleResponse)
def compile_rule(
    payload: AgentRuleRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentRuleResponse:
    return AgentRuleResponse(
        rulesJson={
            "compiledFrom": payload.nlRules,
            "dslVersion": "v1",
            "steps": [],  # stub
        },
        rulesVersion="v0.1-stub",
    )
