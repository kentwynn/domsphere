from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# ----- Enums / aliases --------------------------------------------------------

DomEventType = Literal["dom_click", "input_change", "page_load", "submit", "route_change"]
NoActionReason = Literal["no_trigger", "debounced", "budget_exceeded", "plan_missing", "unknown_selector", None]

# ----- Event & DOM telemetry --------------------------------------------------

class Telemetry(BaseModel):
    """Sanitized DOM context (PII stripped upstream)."""
    elementText: Optional[str] = None
    elementHtml: Optional[str] = None                # keep small; no raw input values
    attributes: Optional[Dict[str, Optional[str]]] = None  # id/class/role/data-*
    cssPath: Optional[str] = None
    xpath: Optional[str] = None
    nearbyText: Optional[List[str]] = None           # a few tokens near element
    ancestors: Optional[List[Dict[str, Optional[str]]]] = None  # [{tag,id?,class?}, ...]

class Event(BaseModel):
    type: DomEventType
    ts: int                                          # epoch ms
    telemetry: Telemetry

# ----- DOM Atlas (for selector learning) --------------------------------------

class DomAtlasElement(BaseModel):
    """A compact node for selector learning."""
    idx: int
    tag: str
    id: Optional[str] = None
    classList: Optional[List[str]] = None
    role: Optional[str] = None
    dataAttrs: Optional[Dict[str, str]] = None
    textSample: Optional[str] = None                 # trimmed innerText sample
    cssPath: Optional[str] = None
    parentIdx: Optional[int] = None                  # parent reference by idx

class DomAtlasSnapshot(BaseModel):
    atlasId: str
    siteId: str
    url: str
    domHash: str
    capturedAt: str                                  # ISO datetime
    elementCount: int
    elements: List[DomAtlasElement] = Field(default_factory=list)
    version: str = "atlas-v1"

# ----- URL Document (for RAG) -------------------------------------------------

class UrlDocument(BaseModel):
    """Normalized page metadata/body for RAG & DB storage."""
    id: str
    siteId: str
    url: str
    finalUrl: Optional[str] = None
    title: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)   # meta tags
    bodyText: Optional[str] = None                       # normalized text (possibly truncated)
    language: Optional[str] = None
    wordCount: Optional[int] = None
    httpStatus: Optional[int] = None
    contentType: Optional[str] = None
    contentLength: Optional[int] = None
    etag: Optional[str] = None
    contentHash: Optional[str] = None                    # sha256 of content
    fetchedAt: str                                       # ISO datetime
    createdAt: str                                       # ISO datetime (DB record)
    updatedAt: str                                       # ISO datetime
    links: List[str] = Field(default_factory=list)

# ----- Generic responses ------------------------------------------------------

class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str = "ok"
