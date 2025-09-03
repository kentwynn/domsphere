from typing import Optional
from fastapi import APIRouter, Header
from contracts.agent_api import AgentSuggestNextRequest, AgentSuggestNextResponse
from contracts.suggestion import Action, CtaSpec, Turn, Suggestion, UIHint

router = APIRouter(prefix="/agent", tags=["suggestion"])

@router.post("/suggest/next", response_model=AgentSuggestNextResponse)
def suggest_next(
    payload: AgentSuggestNextRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentSuggestNextResponse:
    answers = payload.answers or {}
    choice = str(answers.get("choice", "")).strip().lower()

    # Start a fresh micro-convo with an ASK turn if no previous turn
    if not payload.prevTurnId:
        ask = Turn(
            intentId=payload.intentId or "suggest-bundle",
            turnId="t-ask-1",
            status="ask",
            message="Want to see bundle suggestions?",
            actions=[
                Action(id="yes", label="Yes"),
                Action(id="no", label="No"),
            ],
            ui=UIHint(render="panel"),
            ttlSec=30,
        )
        return AgentSuggestNextResponse(turn=ask)

    # If user accepted, return FINAL with non-empty suggestions
    if choice in {"yes", "y"}:
        final = Turn(
            intentId=payload.intentId or "suggest-bundle",
            turnId="t-final-1",
            status="final",
            message="Here are my picks",
            suggestions=[
                Suggestion(
                    type="bundle",
                    id="s-1",
                    score=0.82,
                    title="Buy 2 save 10%",
                    subtitle="P1 + P2",
                    price=44.8,
                    currency="USD",
                    primaryCta=CtaSpec(
                        label="Add bundle",
                        kind="add_to_cart",
                        payload={"skus": ["p1", "p2"]},
                    ),
                    meta={"original": 49.8, "tags": ["bundle", "similar"]},
                ),
                Suggestion(
                    type="upsell",
                    id="s-2",
                    title="Add P3 for free ship",
                    price=19.9,
                    currency="USD",
                    primaryCta=CtaSpec(
                        label="Add P3",
                        kind="add_to_cart",
                        payload={"skus": ["p3"]},
                    ),
                ),
            ],
            ui=UIHint(render="grid", columns=2),
        )
        return AgentSuggestNextResponse(turn=final)

    # Otherwise, FINAL with at least 1 suggestion to satisfy contract
    final_polite = Turn(
        intentId=payload.intentId or "suggest-bundle",
        turnId="t-final-2",
        status="final",
        message="No worries — here’s a popular pick if you change your mind.",
        suggestions=[
            Suggestion(
                type="popular",
                id="s-3",
                title="Top pick: P1",
                price=19.9,
                currency="USD",
                primaryCta=CtaSpec(
                    label="Add P1",
                    kind="add_to_cart",
                    payload={"skus": ["p1"]},
                ),
            )
        ],
        ui=UIHint(render="list"),
    )
    return AgentSuggestNextResponse(turn=final_polite)
