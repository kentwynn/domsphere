# apps/agent/routes/mock_routes.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header

from contracts.agent_api import (
    AgentRuleRequest,
    AgentRuleResponse,
    StepCondition,
    RuleStep,
    AgentStepCheckRequest,
    StepState,
    AgentStepCheckResponse,
    AgentSuggestNextRequest,
    AgentSuggestNextResponse,
    AgentHealthResponse,
)
# IMPORTANT: Turn/Action/Suggestion/UIHint must come from contracts.suggestion
# because AgentSuggestNextResponse.turn expects that exact model.
from contracts.suggestion import Turn, Action, Suggestion, CtaSpec, UIHint

router = APIRouter(prefix="/agent", tags=["agent-mock"])

# ---------------------------------------------------------------------
# /agent/rule  (compile NL rules -> deterministic RuleSet JSON)
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# /agent/step/check  (minimal evaluator for demo)
# ---------------------------------------------------------------------
def _get_path(data: Dict[str, Any], path: str):
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def _eval(cond: StepCondition, ctx: Dict[str, Any]) -> bool:
    import re
    left = _get_path(ctx, cond.field)
    op, right = cond.op, cond.value
    try:
        if op == "equals":   return left == right
        if op == "in":       return left in right if isinstance(right, (list, tuple, set)) else False
        if op == "gte":      return left >= right
        if op == "lte":      return left <= right
        if op == "contains": return (right in left) if isinstance(left, (list, str)) else False
        if op == "between":  return isinstance(right, (list, tuple)) and len(right) == 2 and right[0] <= left <= right[1]
        if op == "regex":    return bool(re.search(str(right), str(left)))
    except Exception:
        return False
    return False

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

# ---------------------------------------------------------------------
# /agent/suggest/next  (drives Turn ask→final per your schema)
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# /agent/health
# ---------------------------------------------------------------------
@router.get("/health", response_model=AgentHealthResponse)
def health() -> AgentHealthResponse:
    return {"ok": True, "version": "mock-0.1", "ts": __import__("time").time()}
