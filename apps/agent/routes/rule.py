from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header
from contracts.agent_api import AgentRuleRequest, AgentRuleResponse

router = APIRouter(prefix="/agent", tags=["rule"])

@router.post("/rule", response_model=AgentRuleResponse)
def compile_rule(
    payload: AgentRuleRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentRuleResponse:
    instr = (payload.llmInstruction or "").lower()
    path = "/"
    if "cart" in instr:
        path = "/cart"
    elif "product" in instr:
        path = "/products"

    triggers: List[Dict[str, Any]] = [
        {
            "eventType": "page_load",
            "when": [
                {"field": "telemetry.attributes.path", "op": "equals", "value": path}
            ],
        }
    ]
    return AgentRuleResponse(triggers=triggers)
