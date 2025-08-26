from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# ---- Enums / aliases ---------------------------------------------------------

DomEventType = Literal["dom_click", "input_change", "page_load", "submit", "route_change"]
NoActionReason = Literal["no_trigger", "debounced", "budget_exceeded", "plan_missing", "unknown_selector", None]

# ---- Core shared models ------------------------------------------------------

class TelemetryModel(BaseModel):
    """Sanitized DOM context for a user event (values/PII should already be stripped)."""
    elementText: Optional[str] = None
    elementHtml: Optional[str] = None               # keep small; avoid raw inputs
    attributes: Optional[Dict[str, Optional[str]]] = None  # id/class/role/data-*
    cssPath: Optional[str] = None
    xpath: Optional[str] = None
    nearbyText: Optional[List[str]] = None          # top 3–5 tokens near the element
    ancestors: Optional[List[Dict[str, Optional[str]]]] = None  # [{tag,id?,class?}, ...]

class EventModel(BaseModel):
    type: DomEventType
    ts: int                                         # epoch ms
    telemetry: TelemetryModel

class PageModel(BaseModel):
    url: str
    locale: Optional[str] = None
    currency: Optional[str] = None
    typeHint: Optional[str] = None                  # "product" | "cart" | etc. (optional)

class CartItem(BaseModel):
    id: str
    qty: int

class CartModel(BaseModel):
    items: List[CartItem] = Field(default_factory=list)
    total: Optional[float] = None

# ---- Generic responses -------------------------------------------------------

class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str = "ok"
