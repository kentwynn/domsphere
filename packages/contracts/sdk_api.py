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
# /rule/track  (control plane for SDK tracking behavior)
# ==============================================================================

class RuleTrackRequest(BaseModel):
    siteId: str
    status: Literal["on", "off"] = "off"   # on = SDK tracks only specified events, off = SDK tracks everything
    version: Optional[str] = None            # optional ruleset version
    events: Optional[Dict[str, List[str]]] = None  # mapping from eventType to list of selectors

class RuleTrackResponse(BaseModel):
    siteId: str
    status: Literal["on", "off"]
    version: Optional[str] = None
    updatedAt: Optional[str] = None
    events: Optional[Dict[str, List[str]]] = None

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
    attributes: Optional[Dict[str, Any]] = None
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
# /site/register
# ==============================================================================

class SiteRegisterRequest(BaseModel):
    siteId: Optional[str] = None   # if not provided, backend generates
    parentUrl: str                 # root URL to crawl from
    meta: Optional[Dict[str, Any]] = None


class SiteRegisterResponse(BaseModel):
    siteId: str
    parentUrl: str
    meta: Optional[Dict[str, Any]] = None


# ==============================================================================
# /site/map
# ==============================================================================

class SiteMapPage(BaseModel):
    url: str
    meta: Optional[Dict[str, Any]] = None

class SiteMapRequest(BaseModel):
    siteId: str
    url: Optional[str] = None
    depth: Optional[int] = 1
    force: bool = False

class SiteMapResponse(BaseModel):
    siteId: str
    pages: List[SiteMapPage]


# ==============================================================================
# /site/info
# ==============================================================================

class SiteInfoRequest(BaseModel):
    siteId: str
    path: Optional[str] = None
    url: Optional[str] = None
    force: bool = False


class SiteInfoResponse(BaseModel):
    siteId: str
    url: str
    meta: Optional[Dict[str, Any]] = None
    normalized: Optional[Dict[str, Any]] = None


# ==============================================================================
# /site/atlas
# ==============================================================================

class SiteAtlasRequest(BaseModel):
    siteId: str
    url: str
    force: bool = False


class SiteAtlasResponse(BaseModel):
    siteId: str
    url: str
    atlas: Optional[DomAtlasSnapshot] = None
    queuedPlanRebuild: Optional[bool] = None

# ==============================================================================
# /health
# ==============================================================================

APIHealthResponse = HealthResponse
