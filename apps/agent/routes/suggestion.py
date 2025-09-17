from typing import Optional
from fastapi import APIRouter, Header
from contracts.agent_api import AgentSuggestNextRequest, AgentSuggestNextResponse
from agents import SuggestionAgent

router = APIRouter(prefix="/agent", tags=["suggestion"])

# Initialize the suggestion agent (singleton pattern for efficiency)
_suggestion_agent = None

def get_suggestion_agent() -> SuggestionAgent:
    global _suggestion_agent
    if _suggestion_agent is None:
        _suggestion_agent = SuggestionAgent()
    return _suggestion_agent


@router.post("/suggest", response_model=AgentSuggestNextResponse)
def suggest(
    payload: AgentSuggestNextRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentSuggestNextResponse:
    """Generate intelligent suggestions using the SuggestionAgent with LLM capabilities."""
    try:
        # Get the suggestion agent and generate suggestions
        agent = get_suggestion_agent()
        suggestions = agent.generate_suggestions(payload)

        # Return the response
        return AgentSuggestNextResponse(suggestions=suggestions)

    except Exception as e:
        print(f"[SuggestionRoute] Error generating suggestions: {e}")
        return AgentSuggestNextResponse(suggestions=[])
