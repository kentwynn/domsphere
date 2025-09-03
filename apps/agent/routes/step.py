from ast import List
from typing import Optional
from fastapi import APIRouter, Header
from helper.common import _eval
from contracts.agent_api import AgentStepCheckRequest, AgentStepCheckResponse, StepState

router = APIRouter(prefix="/agent", tags=["step"])

@router.post("/step/check", response_model=AgentStepCheckResponse)
def step_check(
    payload: AgentStepCheckRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentStepCheckResponse:
    states: List[StepState] = []
    next_id: Optional[str] = None

    for step in payload.steps:
        passed = all(_eval(c, payload.context) for c in step.when)
        states.append(StepState(
            stepId=step.id,
            passed=passed,
            explanations=[f"checked {len(step.when)} conditions; passed={passed}"],
        ))
        if next_id is None and passed:
            next_id = step.id

    return AgentStepCheckResponse(states=states, nextStepId=next_id)
