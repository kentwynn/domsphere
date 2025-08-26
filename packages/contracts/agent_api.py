from __future__ import annotations
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel
from .common import HealthResponse

# ==============================================================================
# /agent/rule  (compile NL rules -> deterministic RuleSet JSON)
# ==============================================================================

class AgentRuleRequest(BaseModel):
    siteId: str
    nlRules: str                             # owner-provided natural language

class AgentRuleResponse(BaseModel):
    rulesJson: Dict[str, Any]                # compiled checkpoint JSON (DSL)
    rulesVersion: str

# ==============================================================================
# /agent/step/check  (reason about multi-step rule flows)
# ==============================================================================

class StepCondition(BaseModel):
    field: str                               # e.g., "eventType", "session.cartItems", "context.lastEventTs"
    op: Literal["equals","in","gte","lte","contains","between","regex"]
    value: Any

class RuleStep(BaseModel):
    id: str
    when: List[StepCondition]                # all conditions must pass
    description: Optional[str] = None
    withinMsOf: Optional[Dict[str, Any]] = None   # {"stepId":"A","ms":30000}

class AgentStepCheckRequest(BaseModel):
    siteId: str
    context: Dict[str, Any]                  # prior events, matchedRules, timers, pageKind, etc.
    steps: List[RuleStep]

class StepState(BaseModel):
    stepId: str
    passed: bool
    explanations: Optional[List[str]] = None

class AgentStepCheckResponse(BaseModel):
    states: List[StepState]
    nextStepId: Optional[str] = None

# ==============================================================================
# /agent/suggestion  (produce suggestions when templates aren’t enough)
# ==============================================================================

class AgentSuggestionRequest(BaseModel):
    siteId: str
    userInput: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None        # e.g., { matchedRules:[], eventType:"add_to_cart", url:"..." }

class AgentSuggestionResponse(BaseModel):
    suggestions: List[Dict[str, Any]]
    trace: Optional[List[str]] = None
    ttlSec: Optional[int] = None

# ==============================================================================
# /agent/health
# ==============================================================================

AgentHealthResponse = HealthResponse
