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
    choice = (payload.input or {}) if payload.input else {}

    # CART promo rule: apply code then submit (no choice step here)
    if rid == "promo_cart_gte_2":
        s = Suggestion(
            type="coupon",
            id=f"coupon-{rid}",
            title="Apply coupon?",
            description="We found a coupon code for your cart.",
            # Primary is a label-only CTA; pipeline below performs the actual steps
            primaryCta=CtaSpec(label="Apply", kind="noop"),
            primaryActions=[
                CtaSpec(label="Fill Code", kind="dom_fill", payload={"selector": "#promo-code", "value": "SAVE10"}),
                CtaSpec(label="Submit", kind="click", payload={"selector": "#apply-promo"}),
            ],
            secondaryCtas=[CtaSpec(label="Cancel", kind="noop")],
            meta={"code": "SAVE10", "step": 1},
        )
        s2 = Suggestion(
            type="checkout",
            id=f"checkout-{rid}",
            title="Proceed to checkout?",
            description="You're all set. Continue to checkout.",
            primaryCta=CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"}),
            secondaryCtas=[CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"})],
            meta={"step": 2},
        )
        return AgentSuggestNextResponse(suggestions=[s, s2])

    # CART special promo for 5+ items
    if rid == "promo_cart_gte_5":
        s = Suggestion(
            type="coupon",
            id=f"coupon-{rid}",
            title="Special offer!",
            description="You qualify for a special promo.",
            # Primary is a label-only CTA; pipeline below performs the actual steps
            primaryCta=CtaSpec(label="Apply YYY", kind="noop"),
            primaryActions=[
                CtaSpec(label="Fill YYY", kind="dom_fill", payload={"selector": "#promo-code", "value": "YYY"}),
                CtaSpec(label="Submit", kind="click", payload={"selector": "#apply-promo"}),
            ],
            secondaryCtas=[CtaSpec(label="Cancel", kind="noop")],
            meta={"code": "YYY", "step": 1},
        )
        s2 = Suggestion(
            type="checkout",
            id=f"checkout-{rid}",
            title="Proceed to checkout?",
            primaryCta=CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"}),
            secondaryCtas=[CtaSpec(label="Checkout", kind="click", payload={"selector": "#checkout"})],
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

    # HOME page: info-only suggestion
    if rid == "home_info" and (url.endswith("/") or url.endswith("/index.html")):
        s = Suggestion(
            type="info",
            id=f"info-{rid}",
            title="Welcome to Demo Shop",
            description="Browse products and enjoy your visit!",
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

    # PRODUCT DEF: demonstrate a multi-step choice flow that ends with a link to Product ABC
    if rid == "product_def_choice" and "/product/sku-def" in url:
        # Multi-step discrete choices: interest -> ageGroup -> color -> final
        interest = choice.get("interest")
        age_group = choice.get("ageGroup")
        color = choice.get("color")

        if not interest:
            s_interest = Suggestion(
                type="choice",
                id=f"choice-interest-{rid}",
                title="What are you shopping for?",
                description="Pick one to tailor the recommendation",
                actions=[
                    CtaSpec(label="School", kind="choose", payload={"name": "interest", "value": "school"}),
                    CtaSpec(label="Sports", kind="choose", payload={"name": "interest", "value": "sports"}),
                    CtaSpec(label="Travel", kind="choose", payload={"name": "interest", "value": "travel"}),
                ],
                meta={"step": 1},
            )
            return AgentSuggestNextResponse(suggestions=[s_interest])

        if not age_group:
            s_age = Suggestion(
                type="choice",
                id=f"choice-age-{rid}",
                title="Age group?",
                description="Select an age range",
                actions=[
                    CtaSpec(label="Under 5", kind="choose", payload={"name": "ageGroup", "value": "u5"}),
                    CtaSpec(label="5–12", kind="choose", payload={"name": "ageGroup", "value": "5_12"}),
                    CtaSpec(label="13–17", kind="choose", payload={"name": "ageGroup", "value": "13_17"}),
                ],
                meta={"step": 2},
            )
            return AgentSuggestNextResponse(suggestions=[s_age])

        if not color:
            s_color = Suggestion(
                type="choice",
                id=f"choice-color-{rid}",
                title="Pick a color",
                actions=[
                    CtaSpec(label="Red", kind="choose", payload={"name": "color", "value": "red"}),
                    CtaSpec(label="Blue", kind="choose", payload={"name": "color", "value": "blue"}),
                    CtaSpec(label="Green", kind="choose", payload={"name": "color", "value": "green"}),
                ],
                meta={"step": 3},
            )
            return AgentSuggestNextResponse(suggestions=[s_color])

        # All choices provided: finalize
        s_final = Suggestion(
            type="recommendation",
            id=f"rec-abc-{rid}",
            title="We recommend Product ABC",
            description=f"For {interest}, ages {age_group}, color {color}",
            primaryCta=CtaSpec(label="View ABC", kind="open", url="/product/sku-abc"),
            secondaryCtas=[CtaSpec(label="View ABC", kind="open", url="/product/sku-abc")],
            meta={"step": 4},
        )
        return AgentSuggestNextResponse(suggestions=[s_final])

    # Fallback generic suggestion
    s = Suggestion(
        type="recommendation",
        id=f"rec-{rid or 'default'}",
        title="Check our latest deals",
        primaryCta=CtaSpec(label="View deals", kind="open", url="/products"),
    )
    return AgentSuggestNextResponse(suggestions=[s])
