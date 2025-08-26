from fastapi import APIRouter, Header
from contracts.agent_api import AgentSuggestNextRequest, AgentSuggestNextResponse
from contracts.suggestion import Turn, Suggestion

router = APIRouter(prefix="/agent", tags=["suggestion"])

@router.post("/suggest/next", response_model=AgentSuggestNextResponse)
def suggest_next(
    payload: AgentSuggestNextRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> AgentSuggestNextResponse:
    # TODO: Replace with AI-driven suggestion logic
    turn = Turn(
        intentId="stub-intent",
        turnId="turn-1",
        status="final",
        message="Here’s a sample suggestion",
        suggestions=[
            Suggestion(
                type="promo",
                title="10% off shoes",
                description="Upgrade your look with discounted sneakers",
                meta={"code": "SAVE10"}
            )
        ],
        ttlSec=30,
    )
    return AgentSuggestNextResponse(turn=turn)
