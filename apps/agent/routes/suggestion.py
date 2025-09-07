from typing import Optional
from fastapi import APIRouter, Header
from contracts.agent_api import AgentSuggestNextRequest, AgentSuggestNextResponse
from contracts.suggestion import CtaSpec, Suggestion

router = APIRouter(prefix="/agent", tags=["suggestion"])


@router.post("/suggest", response_model=AgentSuggestNextResponse)
def suggest(
    payload: AgentSuggestNextRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentSuggestNextResponse:
    """Stateless mock suggestions based on ruleId, aligned with common.py data."""
    rid = (payload.ruleId or "").strip()
    url = (payload.url or "").strip()

    # CART promo rule: fill promo code and click apply
    if rid == "promo_cart_gte_2" and url.endswith("/cart"):
        s = Suggestion(
            type="coupon",
            id=f"coupon-{rid}",
            title="Apply coupon?",
            description="We found a coupon code for your cart.",
            primaryCta=CtaSpec(
                label="Apply",
                kind="dom_fill",
                payload={"selector": "#promo-code", "value": "SAVE10"},
            ),
            actions=[
                CtaSpec(label="Fill Code", kind="dom_fill", payload={"selector": "#promo-code", "value": "SAVE10"}),
                CtaSpec(label="Submit", kind="click", payload={"selector": "#apply-promo"}),
            ],
            meta={"code": "SAVE10", "step": 1},
        )
        s2 = Suggestion(
            type="checkout",
            id=f"checkout-{rid}",
            title="Proceed to checkout?",
            description="You're all set. Continue to checkout.",
            primaryCta=CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"}),
            actions=[CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"})],
            meta={"step": 2},
        )
        return AgentSuggestNextResponse(suggestions=[s, s2])

    # CART special promo for 5+ items
    if rid == "promo_cart_gte_5" and url.endswith("/cart"):
        s = Suggestion(
            type="coupon",
            id=f"coupon-{rid}",
            title="Special offer!",
            description="You qualify for a special promo.",
            primaryCta=CtaSpec(
                label="Apply YYY",
                kind="dom_fill",
                payload={"selector": "#promo-code", "value": "YYY"},
            ),
            actions=[
                CtaSpec(label="Fill YYY", kind="dom_fill", payload={"selector": "#promo-code", "value": "YYY"}),
                CtaSpec(label="Submit", kind="click", payload={"selector": "#apply-promo"}),
            ],
            meta={"code": "YYY", "step": 1},
        )
        s2 = Suggestion(
            type="checkout",
            id=f"checkout-{rid}",
            title="Proceed to checkout?",
            primaryCta=CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"}),
            actions=[CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"})],
            meta={"step": 2},
        )
        return AgentSuggestNextResponse(suggestions=[s, s2])

    # PRODUCTS page: celebratory banner/CTA
    if rid == "products_birthday_20y" and url.endswith("/products"):
        s = Suggestion(
            type="banner",
            id=f"birthday-{rid}",
            title="Happy 20th Anniversary!",
            description="Enjoy free shipping today only.",
            primaryCta=CtaSpec(label="Shop now", kind="open", url="/products"),
        )
        return AgentSuggestNextResponse(suggestions=[s])

    # PRODUCT detail (sku-abc): prompt add-to-cart
    if rid == "product_abc_10s" and "/product/sku-abc" in url:
        s = Suggestion(
            type="upsell",
            id=f"upsell-{rid}",
            title="Add this to your cart",
            description="Popular pick with great reviews.",
            primaryCta=CtaSpec(label="Add to cart", kind="click", payload={"selector": "#add-to-cart"}),
        )
        return AgentSuggestNextResponse(suggestions=[s])

    # Fallback generic suggestion
    s = Suggestion(
        type="recommendation",
        id=f"rec-{rid or 'default'}",
        title="Check our latest deals",
        primaryCta=CtaSpec(label="View deals", kind="open", url="/products"),
    )
    return AgentSuggestNextResponse(suggestions=[s])
