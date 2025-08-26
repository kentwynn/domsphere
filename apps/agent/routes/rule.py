from fastapi import APIRouter, Header
from contracts.agent_api import AgentRuleRequest, AgentRuleResponse

router = APIRouter(prefix="/agent", tags=["rule"])

@router.post("/rule", response_model=AgentRuleResponse)
def compile_rule(
    payload: AgentRuleRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> AgentRuleResponse:
    # TODO: Replace with LLM call
    return AgentRuleResponse(
        rulesJson={"compiledFrom": payload.nlRules, "steps": []},
        rulesVersion="v0.1-stub",
    )
