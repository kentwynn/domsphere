from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from .common import HealthResponse, ConditionOp, RuleTrigger
from .suggestion import Suggestion

# ==============================================================================
# /agent/rule  (compile NL rules -> deterministic RuleSet JSON)
# ==============================================================================

class AgentRuleRequest(BaseModel):
    siteId: str
    ruleInstruction: str

class AgentRuleResponse(BaseModel):
    triggers: List[RuleTrigger]

# ==============================================================================
# /agent/step/check  (reason about multi-step rule flows)
# ==============================================================================

class StepCondition(BaseModel):
    field: str  # e.g., "eventType", "session.cartItems", "context.lastEventTs"
    op: ConditionOp
    value: Any

class RuleStep(BaseModel):
    id: str
    when: List[StepCondition]  # all conditions must pass
    description: Optional[str] = None
    withinMsOf: Optional[Dict[str, Any]] = None  # {"stepId":"A","ms":30000}

class AgentStepCheckRequest(BaseModel):
    siteId: str
    context: Dict[str, Any]  # prior events, matchedRules, timers, pageKind, etc.
    steps: List[RuleStep]

class StepState(BaseModel):
    stepId: str
    passed: bool
    explanations: Optional[List[str]] = None

class AgentStepCheckResponse(BaseModel):
    states: List[StepState]
    nextStepId: Optional[str] = None

# ==============================================================================
# /agent/suggest  (stateless full suggestions; model names kept for continuity)
# ==============================================================================

class AgentSuggestNextRequest(BaseModel):
    siteId: str
    url: str
    ruleId: str
    input: Optional[Dict[str, Any]] = None  # choice input map for next-step branching

class AgentSuggestNextResponse(BaseModel):
    suggestions: List[Suggestion]

# ==============================================================================
# /agent/health
# ==============================================================================

AgentHealthResponse = HealthResponse

__all__ = [
    # rule
    "AgentRuleRequest",
    "AgentRuleResponse",
    # step
    "StepCondition",
    "RuleStep",
    "AgentStepCheckRequest",
    "StepState",
    "AgentStepCheckResponse",
    # suggest (stateless)
    "AgentSuggestNextRequest",
    "AgentSuggestNextResponse",
    # health
    "AgentHealthResponse",
]
