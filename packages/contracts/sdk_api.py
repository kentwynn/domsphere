from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel
from .common import (
    Event,
    DomAtlasSnapshot,
    NoActionReason,
    HealthResponse,
)

# ==============================================================================
# /rule/check  (called on EVERY user event; API resolves context internally)
# ==============================================================================

class RuleCheckRequest(BaseModel):
    siteId: str
    sessionId: str
    event: Event

class RuleCheckResponse(BaseModel):
    eventType: str                      # e.g., "add_to_cart" | "variant_change" | "unknown"
    matchedRules: List[str]             # []
    shouldProceed: bool
    reason: Optional[str] = None        # "no_rule" | "debounced" | "budget" | "plan_missing" | ...

# ==============================================================================
# /suggest/get  (only when shouldProceed==true)
# ==============================================================================

class SuggestionAction(BaseModel):
    type: str
    label: str
    payload: Optional[Dict[str, Any]] = None

class Suggestion(BaseModel):
    id: Optional[str] = None
    type: str                           # "size_fit" | "cross_sell" | "upsell" | "promo" | ...
    message: str
    actions: Optional[List[SuggestionAction]] = None
    meta: Optional[Dict[str, Any]] = None

class SuggestGetContext(BaseModel):
    matchedRules: List[str]
    eventType: str

class SuggestGetRequest(BaseModel):
    siteId: str
    sessionId: str
    context: SuggestGetContext
    userInput: Optional[Dict[str, Any]] = None       # shopper-provided inputs (e.g., heightCm)

class SuggestGetResponse(BaseModel):
    suggestions: List[Suggestion]
    trace: Optional[List[str]] = None
    ttlSec: Optional[int] = None
    planVersion: Optional[str] = None
    noActionReason: NoActionReason = None

# ==============================================================================
# /url/drag  (RAG: crawl URL(s), extract/stash metadata in DB)
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
    mode: Literal["info", "all"] = "all"   # URL RAG collects info/body/meta
    options: Optional[UrlDragOptions] = None

class UrlDragResponse(BaseModel):
    jobId: str
    queued: bool = True

# ==============================================================================
# /page/drag  (DOM Atlas snapshot for selector learning)
# ==============================================================================

class PageDragRequest(BaseModel):
    siteId: str
    url: str
    mode: Literal["atlas", "all"] = "atlas"
    force: bool = False

class PageDragResponse(BaseModel):
    atlas: Optional[DomAtlasSnapshot] = None
    normalized: Optional[Dict[str, Any]] = None      # optional normalized page data
    queuedPlanRebuild: Optional[bool] = None

# ==============================================================================
# /health
# ==============================================================================

APIHealthResponse = HealthResponse
