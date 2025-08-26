from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import (
    EventModel,
    PageModel,
    CartModel,
    NoActionReason,
    HealthResponse,
)

# --------- /suggest (hot path) -----------------------------------------------

class SuggestRequestV1(BaseModel):
    siteId: str
    sessionId: str
    idempotencyKey: Optional[str] = None
    sdkVersion: Optional[str] = None
    page: PageModel
    cart: Optional[CartModel] = None
    userInput: Optional[Dict[str, Any]] = None
    event: EventModel

class SuggestionAction(BaseModel):
    type: str
    label: str
    payload: Optional[Dict[str, Any]] = None

class Suggestion(BaseModel):
    id: Optional[str] = None
    type: str                       # "size_fit" | "cross_sell" | "upsell" | "promo" | ...
    message: str
    actions: Optional[List[SuggestionAction]] = None
    meta: Optional[Dict[str, Any]] = None

class SuggestResponseV1(BaseModel):
    eventType: str                  # e.g., "add_to_cart" | "variant_change" | "unknown"
    matchedTriggers: List[str]      # trigger IDs from plan; [] if none
    suggestions: List[Suggestion]
    planVersion: Optional[str] = None
    trace: Optional[List[str]] = None
    noActionReason: NoActionReason = None
    ttlSec: Optional[int] = None

# --------- /page/drag ---------------------------------------------------------

class PageDragRequestV1(BaseModel):
    siteId: str
    url: str
    mode: str                       # "info" | "atlas" | "all"
    force: bool = False

class PageDragResponseV1(BaseModel):
    atlasId: Optional[str] = None
    normalized: Optional[Dict[str, Any]] = None
    queuedPlanRebuild: Optional[bool] = None

# --------- /url/drag (bulk) ---------------------------------------------------

class UrlDragRequestV1(BaseModel):
    siteId: str
    urls: Optional[List[str]] = None
    domain: Optional[str] = None
    depth: Optional[int] = None
    mode: str = "all"               # "info" | "atlas" | "all"

class UrlDragResponseV1(BaseModel):
    jobId: str
    queued: bool = True

# --------- /rule/check (optional separate pre-check) --------------------------

class RuleCheckRequestV1(BaseModel):
    siteId: str
    sessionId: str
    page: PageModel
    cart: Optional[CartModel] = None
    userInput: Optional[Dict[str, Any]] = None
    event: EventModel

class RuleCheckResponseV1(BaseModel):
    eventType: str
    matchedRules: List[str]
    shouldProceed: bool
    reason: Optional[str] = None

# --------- /health ------------------------------------------------------------

# Re-export for convenience:
SDKHealthResponse = HealthResponse
