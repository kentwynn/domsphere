from fastapi import APIRouter, Header
from contracts.agent_api import AgentStepCheckRequest, AgentStepCheckResponse, StepState

router = APIRouter(prefix="/agent", tags=["step"])

@router.post("/step/check", response_model=AgentStepCheckResponse)
def step_check(
    payload: AgentStepCheckRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> AgentStepCheckResponse:
    # TODO: real evaluation; stub marks all failed
    states = [StepState(stepId=s.id, passed=False, explanations=["stub"]) for s in payload.steps]
    return AgentStepCheckResponse(states=states, nextStepId=None)
