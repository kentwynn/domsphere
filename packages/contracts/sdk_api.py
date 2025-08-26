from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from .common import Event, DomAtlasSnapshot, NoActionReason, HealthResponse

# ==============================================================================
# /rule/check  (called on EVERY user event; API resolves context internally)
# ==============================================================================

class RuleCheckRequest(BaseModel):
    siteId: str
    sessionId: str
    event: Event

class RuleCheckResponse(BaseModel):
    eventType: str
    matchedRules: List[str]
    shouldProceed: bool
    reason: Optional[str] = None

# ==============================================================================
# /suggest/get  (agent-driven ask/final loop)
# ==============================================================================

TurnStatus = Literal["ask", "final"]

class Action(BaseModel):
    id: str
    label: str
    value: Optional[Any] = None

FieldType = Literal["text","number","select","radio","checkbox","textarea","range","toggle"]

class InputOption(BaseModel):
    value: Any
    label: str

class FieldSpec(BaseModel):
    key: str
    type: FieldType
    label: str
    required: bool = False
    options: Optional[List[InputOption]] = None
    validation: Optional[Dict[str, Any]] = None

class FormSpec(BaseModel):
    title: Optional[str] = None
    fields: List[FieldSpec] = Field(default_factory=list)
    submitLabel: Optional[str] = "Continue"

class CtaSpec(BaseModel):
    label: str
    kind: str = "link"
    url: Optional[str] = None
    sku: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

class Suggestion(BaseModel):
    type: str
    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    primaryCta: Optional[CtaSpec] = None
    actions: Optional[List[CtaSpec]] = None
    meta: Optional[Dict[str, Any]] = None

class UIHint(BaseModel):
    render: Optional[str] = None

class Turn(BaseModel):
    intentId: str
    turnId: str
    status: TurnStatus
    message: Optional[str] = None
    actions: Optional[List[Action]] = None
    form: Optional[FormSpec] = None
    suggestions: Optional[List[Suggestion]] = None
    ui: Optional[UIHint] = None
    ttlSec: Optional[int] = None

    @model_validator(mode="after")
    def _check_valid(self):
        if self.status == "ask":
            if not self.actions and not self.form:
                raise ValueError("ask turn requires actions or form")
            if self.suggestions:
                raise ValueError("ask turn cannot include suggestions")
        elif self.status == "final":
            if not self.suggestions:
                raise ValueError("final turn requires suggestions")
        return self

class SuggestGetRequest(BaseModel):
    siteId: str
    sessionId: str
    intentId: Optional[str] = None
    prevTurnId: Optional[str] = None
    answers: Optional[Dict[str, Any]] = None
    context: Dict[str, Any]

class SuggestGetResponse(BaseModel):
    turn: Turn

# ==============================================================================
# /url/drag
# ==============================================================================

class UrlDragOptions(BaseModel):
    depth: Optional[int] = None
    followRobotsTxt: bool = True
    maxBytes: Optional[int] = 2_000_000
    timeoutSec: Optional[int] = 20

class UrlDragRequest(BaseModel):
    siteId: str
    urls: Optional[List[str]] = None
    domain: Optional[str] = None
    mode: Literal["info", "all"] = "all"
    options: Optional[UrlDragOptions] = None

class UrlDragResponse(BaseModel):
    jobId: str
    queued: bool = True

# ==============================================================================
# /page/drag
# ==============================================================================

class PageDragRequest(BaseModel):
    siteId: str
    url: str
    mode: Literal["atlas", "all"] = "atlas"
    force: bool = False

class PageDragResponse(BaseModel):
    atlas: Optional[DomAtlasSnapshot] = None
    normalized: Optional[Dict[str, Any]] = None
    queuedPlanRebuild: Optional[bool] = None

# ==============================================================================
# /health
# ==============================================================================

APIHealthResponse = HealthResponse
