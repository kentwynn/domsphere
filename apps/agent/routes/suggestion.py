from fastapi import APIRouter, Header
from contracts.agent_api import AgentSuggestionRequest, AgentSuggestionResponse

router = APIRouter(prefix="/agent", tags=["suggestion"])

@router.post("/suggestion", response_model=AgentSuggestionResponse)
def suggestion(
    payload: AgentSuggestionRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> AgentSuggestionResponse:
    # TODO: Replace with AI call
    return AgentSuggestionResponse(
        suggestions=[{"message": "stub suggestion"}],
        trace=["stub:agent_suggestion"],
        ttlSec=20,
    )
