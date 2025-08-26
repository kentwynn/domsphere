from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator

TurnStatus = Literal["ask", "final"]

# ==============================================================================
# Actions for "ask" turns (quick chips/buttons)
# ==============================================================================

class Action(BaseModel):
    id: str
    label: str
    value: Optional[Any] = None
    icon: Optional[str] = None
    style: Optional[Dict[str, Any]] = None  # e.g., {"variant": "primary"}

# ==============================================================================
# CTA (links, deep actions, add-to-cart, etc.)
# ==============================================================================

class CtaSpec(BaseModel):
    label: str
    kind: str = "link"               # "link","open","add_to_cart","route","copy",...
    href: Optional[str] = None       # absolute/relative URL
    url: Optional[str] = None        # alias of href
    route: Optional[str] = None      # internal SPA route
    sku: Optional[str] = None        # for commerce
    payload: Optional[Dict[str, Any]] = None
    target: Optional[str] = None     # "_self","_blank",...
    confirm: Optional[bool] = None
    meta: Optional[Dict[str, Any]] = None

# ==============================================================================
# Form specs (for collecting structured inputs from shopper)
# ==============================================================================

FieldType = Literal[
    "text", "number", "select", "radio", "checkbox",
    "textarea", "range", "toggle"
]

class InputOption(BaseModel):
    value: Any
    label: str

class FieldSpec(BaseModel):
    key: str
    type: FieldType
    label: str
    required: bool = False
    placeholder: Optional[str] = None
    options: Optional[List[InputOption]] = None
    validation: Optional[Dict[str, Any]] = None
    ui: Optional[Dict[str, Any]] = None

class FormSpec(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    fields: List[FieldSpec] = Field(default_factory=list)
    submitLabel: Optional[str] = "Continue"
    cancelLabel: Optional[str] = None

# ==============================================================================
# Suggestion card (flexible, agent-defined type)
# ==============================================================================

class Suggestion(BaseModel):
    type: str                                # agent chooses any string
    id: Optional[str] = None
    score: Optional[float] = None
    tracking: Optional[Dict[str, Any]] = None

    # Display fields
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None

    # Media
    image: Optional[str] = None
    gallery: Optional[List[str]] = None
    alt: Optional[str] = None

    # Commerce-ish
    price: Optional[float] = None
    currency: Optional[str] = None
    rating: Optional[float] = None

    # Attributes / meta
    attributes: Optional[Dict[str, Any]] = None

    # CTAs
    primaryCta: Optional[CtaSpec] = None
    secondaryCtas: Optional[List[CtaSpec]] = None
    links: Optional[List[CtaSpec]] = None
    actions: Optional[List[CtaSpec]] = None

    # Freeform extension
    meta: Optional[Dict[str, Any]] = None

# ==============================================================================
# Turn (single unit the agent returns per call)
# ==============================================================================

class UIHint(BaseModel):
    render: Optional[Literal[
        "card", "grid", "list", "hero", "panel", "modal", "toast", "banner"
    ]] = None
    layout: Optional[str] = None
    columns: Optional[int] = None

class Turn(BaseModel):
    intentId: str
    turnId: str
    status: TurnStatus
    message: Optional[str] = None

    # When asking
    actions: Optional[List[Action]] = None
    form: Optional[FormSpec] = None

    # When finalizing
    suggestions: Optional[List[Suggestion]] = None

    # Extra hints
    ui: Optional[UIHint] = None
    ttlSec: Optional[int] = None
    hints: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _check_contract(self):
        if self.status == "ask":
            if not self.actions and not self.form:
                raise ValueError("status=ask requires actions or form")
            if self.suggestions:
                raise ValueError("status=ask must not include suggestions")
        elif self.status == "final":
            if not self.suggestions or len(self.suggestions) == 0:
                raise ValueError("status=final requires suggestions")
        return self

__all__ = [
    "TurnStatus",
    "Action",
    "CtaSpec",
    "FieldType",
    "InputOption",
    "FieldSpec",
    "FormSpec",
    "Suggestion",
    "UIHint",
    "Turn",
]
