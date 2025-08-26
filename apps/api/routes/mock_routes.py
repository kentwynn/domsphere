from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import uuid4
from time import time

from fastapi import APIRouter, Header

from contracts.sdk_api import APIHealthResponse, Action, PageDragRequest, PageDragResponse, RuleCheckRequest, RuleCheckResponse, SuggestGetRequest, SuggestGetResponse, Turn, UrlDragRequest, UrlDragResponse
from contracts.suggestion import CtaSpec, Suggestion, UIHint


router = APIRouter(prefix="", tags=["api-mock"])

# ------------------------------------------------------------------------
# /rule/check
# ------------------------------------------------------------------------
@router.post("/rule/check", response_model=RuleCheckResponse)
def rule_check(
    payload: RuleCheckRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RuleCheckResponse:
    """
    MOCK logic:
      - shouldProceed True when event.eventType is 'add_to_cart' and count >= 2 (if present)
      - matchedRules returns a stable demo rule
    """
    evt = payload.event
    event_type = getattr(evt, "eventType", None) or getattr(evt, "type", None) or "unknown"

    # try to read a cart count if the event carries it; otherwise 0
    cart_count = 0
    try:
        details: Dict[str, Any] = getattr(evt, "details", {}) or {}
        cart_count = int(details.get("cartCount") or details.get("count") or 0)
    except Exception:
        cart_count = 0

    proceed = (str(event_type).lower() in {"add_to_cart", "cart_add"}) and (cart_count >= 2)
    return RuleCheckResponse(
        eventType=str(event_type),
        matchedRules=(["CART_COUNT_GTE_2"] if proceed else []),
        shouldProceed=proceed,
        reason=("CART_COUNT_GTE_2" if proceed else "NO_MATCH"),
    )

# ------------------------------------------------------------------------
# /suggest/get   (ask -> final)
# ------------------------------------------------------------------------
@router.post("/suggest/get", response_model=SuggestGetResponse)
def suggest_get(
    payload: SuggestGetRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    """
    MOCK policy:
      - If prevTurnId is missing -> return ASK (with actions yes/no)
      - Else, if answers.choice in {'yes','y'} -> FINAL with suggestions
      - Else -> FINAL with a single generic suggestion (contract requires >=1)
    """
    answers = payload.answers or {}
    choice = str(answers.get("choice", "")).strip().lower()

    if not payload.prevTurnId:
        ask = Turn(
            intentId=payload.intentId or "suggest-bundle",
            turnId="t-ask-1",
            status="ask",
            message="Want to see bundle suggestions?",
            actions=[
                Action(id="yes", label="Yes"),
                Action(id="no", label="No"),
            ],
            ui=UIHint(render="panel"),
            ttlSec=30,
        )
        return SuggestGetResponse(turn=ask)

    if choice in {"yes", "y"}:
        final = Turn(
            intentId=payload.intentId or "suggest-bundle",
            turnId="t-final-1",
            status="final",
            message="Here are my picks",
            suggestions=[
                Suggestion(
                    type="bundle",
                    id="s-1",
                    title="Buy 2 save 10%",
                    description="Bundle P1 + P2 with 10% off",
                    price=44.8,
                    currency="USD",
                    primaryCta=CtaSpec(label="Add bundle", kind="add_to_cart", payload={"skus": ["p1", "p2"]}),
                    meta={"original": 49.8, "tags": ["bundle", "similar"]},
                ),
                Suggestion(
                    type="upsell",
                    id="s-2",
                    title="Add P3 for free shipping",
                    description="Popular add-on for free shipping threshold",
                    price=19.9,
                    currency="USD",
                    primaryCta=CtaSpec(label="Add P3", kind="add_to_cart", payload={"skus": ["p3"]}),
                ),
            ],
            ui=UIHint(render="grid"),
        )
        return SuggestGetResponse(turn=final)

    # polite final with a single suggestion (must be non-empty for status=final)
    final_polite = Turn(
        intentId=payload.intentId or "suggest-bundle",
        turnId="t-final-2",
        status="final",
        message="No problem — here’s a popular pick if you change your mind.",
        suggestions=[
            Suggestion(
                type="popular",
                id="s-3",
                title="Top pick: P1",
                price=19.9,
                currency="USD",
                primaryCta=CtaSpec(label="Add P1", kind="add_to_cart", payload={"skus": ["p1"]}),
            )
        ],
        ui=UIHint(render="list"),
    )
    return SuggestGetResponse(turn=final_polite)

# ------------------------------------------------------------------------
# /url/drag
# ------------------------------------------------------------------------
@router.post("/url/drag", response_model=UrlDragResponse)
def url_drag(
    payload: UrlDragRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> UrlDragResponse:
    # Mock: return a queued job id
    return UrlDragResponse(jobId=f"job-{uuid4()}", queued=True)

# ------------------------------------------------------------------------
# /page/drag
# ------------------------------------------------------------------------
@router.post("/page/drag", response_model=PageDragResponse)
def page_drag(
    payload: PageDragRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> PageDragResponse:
    """
    MOCK:
      - If mode == 'atlas': return a minimal atlas-like structure in `normalized`
      - Otherwise, indicate a queued rebuild
    """
    if payload.mode == "atlas":
        # Keep it minimal; your DomAtlasSnapshot is Optional so we can omit actual atlas content
        normalized = {
            "url": payload.url,
            "scrapedAt": time(),
            "elements": [
                {"selector": "[data-testid='product-card']", "count": 3},
                {"selector": "[data-testid='add-to-cart']", "count": 3},
            ],
        }
        return PageDragResponse(atlas=None, normalized=normalized, queuedPlanRebuild=False)

    # mode == "all": pretend we queued a larger job
    return PageDragResponse(atlas=None, normalized=None, queuedPlanRebuild=True)

# ------------------------------------------------------------------------
# /health
# ------------------------------------------------------------------------
@router.get("/health", response_model=APIHealthResponse)
def health() -> APIHealthResponse:
    return {"ok": True, "version": "mock-0.1", "ts": time()}
