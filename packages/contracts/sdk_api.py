from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from .common import Event, DomAtlasSnapshot, NoActionReason, HealthResponse
from .suggestion import Suggestion as RichSuggestion

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
# /suggest  (stateless suggestions; keeping class names for continuity)
# ==============================================================================

class SuggestGetRequest(BaseModel):
    siteId: str
    url: str
    ruleId: str

class SuggestGetResponse(BaseModel):
    suggestions: List[RichSuggestion]

# ==============================================================================
# /suggest/next (branching suggestions by discrete choices)
# ==============================================================================

class SuggestNextRequest(BaseModel):
    siteId: str
    url: str
    ruleId: str
    input: Optional[Dict[str, Any]] = None  # choice input map

class SuggestNextResponse(BaseModel):
    suggestions: List[RichSuggestion]

# ==============================================================================
# (legacy site,info,atlas,health contracts remain below)

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
