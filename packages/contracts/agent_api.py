from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from .common import PageModel, CartModel, HealthResponse

# --------- /agent/rule --------------------------------------------------------

class AgentRuleRequestV1(BaseModel):
    siteId: str
    nlRules: str                         # natural-language rules (owner input)

class AgentRuleResponseV1(BaseModel):
    rulesJson: Dict[str, Any]            # compiled checkpoint JSON
    rulesVersion: str

# --------- /agent/suggestion --------------------------------------------------

class AgentSuggestionRequestV1(BaseModel):
    siteId: str
    page: PageModel
    cart: Optional[CartModel] = None
    userInput: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None      # e.g., { matchedRules:[], eventType: "add_to_cart" }

class AgentSuggestionResponseV1(BaseModel):
    suggestions: List[Dict[str, Any]]
    trace: Optional[List[str]] = None
    ttlSec: Optional[int] = None

# --------- /agent/health ------------------------------------------------------

AgentHealthResponse = HealthResponse
