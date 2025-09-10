import os
import re
from typing import Any, Dict, Optional, List

from contracts.client_api import (
    RuleCheckRequest,
    SiteMapResponse, SiteMapPage,
    SiteInfoResponse,
    SiteAtlasResponse,
)
from contracts.common import DomAtlasSnapshot, DomAtlasElement


AGENT_URL = os.getenv("AGENT_BASE_URL", "http://localhost:5001").rstrip("/")
AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT", "300"))

# ----------------------------------------------------------------------------
# Mock: Rules DB used by /api/rule/check (flat eventType + when conditions)
# ----------------------------------------------------------------------------

RULES_DB: Dict[str, Dict[str, Any]] = {
    "demo-site": {
        "version": "ruleset-001",
        "rulesJson": {
            "ruleset": "diverse-suggestions-demo",
            "rules": [
                {
                    "id": "promo_cart_gte_2",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Show suggestions when cart has 2 or more items",
                    "outputInstruction": "Given PromoCode SAVE10",
                    "triggers": [
                        {"eventType": "page_load", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                            {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                            {"field": "telemetry.elementText", "op": "gte", "value": 2}
                        ]},
                        {"eventType": "input_change", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                            {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                            {"field": "telemetry.elementText", "op": "gte", "value": 2}
                        ]},
                        {"eventType": "dom_click", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                            {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                            {"field": "telemetry.elementText", "op": "gte", "value": 2}
                        ]},
                    ],
                },
                {
                    "id": "promo_cart_gte_5",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Show suggestions when cart has 5 or more items",
                    "outputInstruction": "Generate premium, loyalty-focused suggestions that make customers feel valued and exclusive",
                    "triggers": [
                        {"eventType": "page_load", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                            {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                            {"field": "telemetry.elementText", "op": "gte", "value": 5}
                        ]},
                        {"eventType": "input_change", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                            {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                            {"field": "telemetry.elementText", "op": "gte", "value": 5}
                        ]},
                        {"eventType": "dom_click", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                            {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                            {"field": "telemetry.elementText", "op": "gte", "value": 5}
                        ]},
                    ],
                },
                {
                    "id": "products_birthday_20y",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Show suggestions when user visits products page",
                    "outputInstruction": "Generate celebratory, milestone-focused suggestions with historical context and special offers",
                    "triggers": [
                        {"eventType": "page_load", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/products"}
                        ]}
                    ],
                },
                {
                    "id": "home_info",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Show a welcome info on home page",
                    "outputInstruction": "Create welcoming guidance suggestions to help new visitors explore the site",
                    "triggers": [
                        {"eventType": "page_load", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/"}
                        ]}
                    ],
                },
                {
                    "id": "product_abc_10s",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Show suggestions when user visits Product ABC page",
                    "outputInstruction": "Generate product-specific recommendations and cross-sell suggestions",
                    "ttlSec": 10,
                    "triggers": [
                        {"eventType": "page_load", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/product/sku-abc"}
                        ]}
                    ],
                }
                ,
                {
                    "id": "product_def_choice",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Ask shopper a simple choice then recommend Product ABC",
                    "outputInstruction": "Create interactive choice-based suggestions that lead to Product ABC recommendations",
                    "triggers": [
                        {"eventType": "page_load", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/product/sku-def"}
                        ]}
                    ],
                },
                {
                    "id": "products_browse_help",
                    "enabled": True,
                    "tracking": True,
                    "ruleInstruction": "Help users who spend more than 10 seconds browsing products",
                    "outputInstruction": "Offer product exploration assistance and personalized recommendations",
                    "triggers": [
                        {"eventType": "time_spent", "when": [
                            {"field": "telemetry.attributes.path", "op": "equals", "value": "/products"},
                            {"field": "telemetry.attributes.timeOnPage", "op": "gt", "value": 10}
                        ]}
                    ],
                }
            ],
        },
    }
}

# ----------------------------------------------------------------------------
# Typed mocks that conform to contract interfaces
# ----------------------------------------------------------------------------

# Site info (list) – use SiteInfoResponse shape
SITE_INFO: List[SiteInfoResponse] = [
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000",
        meta={
            "title": "Demo Shop • Home",
            "description": "Welcome to Demo Shop at localhost:3000.",
            "category": "retail",
        },
        normalized=None,
    ),
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000/products",
        meta={
            "title": "All Products",
            "description": "Browse our product catalog.",
            "category": "retail",
        },
        normalized=None,
    ),
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000/product/sku-abc",
        meta={
            "title": "Product • SKU ABC",
            "description": "Details for product SKU ABC.",
            "category": "retail",
        },
        normalized=None,
    ),
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000/product/sku-def",
        meta={
            "title": "Product • SKU DEF",
            "description": "Details for product SKU DEF.",
            "category": "retail",
        },
        normalized=None,
    ),
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000/cart",
        meta={
            "title": "Your Cart",
            "description": "Items you intend to purchase.",
            "category": "retail",
        },
        normalized=None,
    ),
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000/checkout",
        meta={
            "title": "Checkout",
            "description": "Enter shipping and payment details.",
            "category": "retail",
        },
        normalized=None,
    ),
    SiteInfoResponse(
        siteId="demo-site",
        url="http://localhost:3000/success",
        meta={
            "title": "Order Success",
            "description": "Thanks for your purchase!",
            "category": "retail",
        },
        normalized=None,
    ),
]

# Site map by site – use SiteMapResponse + SiteMapPage
SITE_MAP: Dict[str, SiteMapResponse] = {
    "demo-site": SiteMapResponse(
        siteId="demo-site",
        pages=[
            SiteMapPage(url="http://localhost:3000/", meta={"title": "Home"}),
            SiteMapPage(url="http://localhost:3000/products", meta={"title": "Products"}),
            SiteMapPage(url="http://localhost:3000/product/:sku", meta={"title": "Product Detail"}),
            SiteMapPage(url="http://localhost:3000/cart", meta={"title": "Cart"}),
            SiteMapPage(url="http://localhost:3000/checkout", meta={"title": "Checkout"}),
            SiteMapPage(url="http://localhost:3000/success", meta={"title": "Order Success"}),
        ],
    )
}

# Site atlas by URL – use SiteAtlasResponse + DomAtlasSnapshot/Element
SITE_ATLAS: Dict[str, SiteAtlasResponse] = {
    # Home
    "http://localhost:3000": SiteAtlasResponse(
        siteId="demo-site",
        url="http://localhost:3000",
        atlas=DomAtlasSnapshot(
            atlasId="atlas-home",
            siteId="demo-site",
            url="http://localhost:3000",
            domHash="hash-home-1",
            capturedAt="2025-01-01T00:00:00Z",
            elementCount=2,
            elements=[
                DomAtlasElement(idx=0, tag="main", cssPath="main"),
                DomAtlasElement(idx=1, tag="a", id="shop-now", textSample="Shop now", cssPath="#shop-now", parentIdx=0),
            ],
        ),
        queuedPlanRebuild=False,
    ),
    # Products list
    "http://localhost:3000/products": SiteAtlasResponse(
        siteId="demo-site",
        url="http://localhost:3000/products",
        atlas=DomAtlasSnapshot(
            atlasId="atlas-products",
            siteId="demo-site",
            url="http://localhost:3000/products",
            domHash="hash-products-1",
            capturedAt="2025-01-01T00:00:00Z",
            elementCount=3,
            elements=[
                DomAtlasElement(idx=0, tag="main", cssPath="main"),
                DomAtlasElement(idx=1, tag="a", classList=["product-link"], dataAttrs={"sku":"sku-abc"}, textSample="View", cssPath="a.product-link", parentIdx=0),
                DomAtlasElement(idx=2, tag="a", classList=["product-link"], dataAttrs={"sku":"sku-def"}, textSample="View", cssPath="a.product-link:nth-child(2)", parentIdx=0),
            ],
        ),
        queuedPlanRebuild=False,
    ),
    # Product detail
    "http://localhost:3000/product/sku-abc": SiteAtlasResponse(
        siteId="demo-site",
        url="http://localhost:3000/product/sku-abc",
        atlas=DomAtlasSnapshot(
            atlasId="atlas-product-abc",
            siteId="demo-site",
            url="http://localhost:3000/product/sku-abc",
            domHash="hash-product-1",
            capturedAt="2025-01-01T00:00:00Z",
            elementCount=3,
            elements=[
                DomAtlasElement(idx=0, tag="main", cssPath="main"),
                DomAtlasElement(idx=1, tag="div", id="details", cssPath="#details", parentIdx=0),
                DomAtlasElement(idx=2, tag="button", id="add-to-cart", classList=["btn","primary"], textSample="Add to cart", cssPath="#add-to-cart", parentIdx=1),
            ],
        ),
        queuedPlanRebuild=False,
    ),
    # Cart
    "http://localhost:3000/cart": SiteAtlasResponse(
        siteId="demo-site",
        url="http://localhost:3000/cart",
        atlas=DomAtlasSnapshot(
            atlasId="atlas-cart",
            siteId="demo-site",
            url="http://localhost:3000/cart",
            domHash="hash-cart-1",
            capturedAt="2025-01-01T00:00:00Z",
            elementCount=5,
            elements=[
                DomAtlasElement(idx=0, tag="main", cssPath="main"),
                DomAtlasElement(idx=1, tag="span", id="cart-count", textSample="2", cssPath="#cart-count", parentIdx=0),
                DomAtlasElement(idx=2, tag="input", id="promo-code", cssPath="#promo-code", parentIdx=0),
                DomAtlasElement(idx=3, tag="button", id="apply-promo", textSample="Apply", cssPath="#apply-promo", parentIdx=0),
                DomAtlasElement(idx=4, tag="button", id="checkout", textSample="Checkout", cssPath="#checkout", parentIdx=0),
            ],
        ),
        queuedPlanRebuild=False,
    ),
    # Checkout
    "http://localhost:3000/checkout": SiteAtlasResponse(
        siteId="demo-site",
        url="http://localhost:3000/checkout",
        atlas=DomAtlasSnapshot(
            atlasId="atlas-checkout",
            siteId="demo-site",
            url="http://localhost:3000/checkout",
            domHash="hash-checkout-1",
            capturedAt="2025-01-01T00:00:00Z",
            elementCount=2,
            elements=[
                DomAtlasElement(idx=0, tag="main", cssPath="main"),
                DomAtlasElement(idx=1, tag="button", id="place-order", textSample="Place order", cssPath="#place-order", parentIdx=0),
            ],
        ),
        queuedPlanRebuild=False,
    ),
    # Success
    "http://localhost:3000/success": SiteAtlasResponse(
        siteId="demo-site",
        url="http://localhost:3000/success",
        atlas=DomAtlasSnapshot(
            atlasId="atlas-success",
            siteId="demo-site",
            url="http://localhost:3000/success",
            domHash="hash-success-1",
            capturedAt="2025-01-01T00:00:00Z",
            elementCount=2,
            elements=[
                DomAtlasElement(idx=0, tag="main", cssPath="main"),
                DomAtlasElement(idx=1, tag="span", id="order-id", textSample="#12345", cssPath="#order-id", parentIdx=0),
            ],
        ),
        queuedPlanRebuild=False,
    ),
}

# AgentRuleResponse instance not needed; RULES_DB holds agent-style rules JSON

def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if hasattr(cur, part):
            cur = getattr(cur, part)
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        return None
    return cur

def _op_eval(left: Any, op: str, right: Any) -> bool:
    try:
        if op == "equals": return left == right
        if op == "eq": return left == right
        if op == "in": return left in right if isinstance(right, (list, tuple, set)) else False
        if op == "gt": return left is not None and right is not None and left > right
        if op == "gte": return left is not None and right is not None and left >= right
        if op == "lt": return left is not None and right is not None and left < right
        if op == "lte": return left is not None and right is not None and left <= right
        if op == "contains":
            if isinstance(left, str) and isinstance(right, str):
                return right in left
            if isinstance(left, (list, tuple, set)):
                return right in left
            return False
        if op == "between":
            if isinstance(right, (list, tuple)) and len(right) == 2:
                lo, hi = right
                return left is not None and lo <= left <= hi
            return False
        if op == "regex":
            return bool(re.search(str(right), str(left)))
    except Exception:
        return False
    return False

def _rule_matches(rule: Dict[str, Any], payload: RuleCheckRequest) -> bool:
    allowed = rule.get("eventType")
    evt_type = getattr(payload.event, "type", None) or "unknown"
    if allowed and str(evt_type) not in set(map(str, allowed)):
        return False
    scope = {
        "event": payload.event,
        "telemetry": getattr(payload.event, "telemetry", None),
        "context": {},
    }
    for cond in rule.get("when", []):
        field, op, val = cond["field"], cond["op"], cond["value"]
        if field.startswith("event."):
            left = _get_path(scope, field)
        else:
            left = _get_path(scope, field) or _get_path(payload, field) or _get_path(payload.event, field)
        if isinstance(left, str) and left.isdigit():
            left = int(left)
        if _op_eval(left, op, val) is False:
            return False
    return True


def _fwd_headers(xcv: Optional[str], xrid: Optional[str]) -> Dict[str, str]:
    h: Dict[str, str] = {}
    if xcv: h["X-Contract-Version"] = xcv
    if xrid: h["X-Request-Id"] = xrid
    return h


# ----------------------------------------------------------------------------
# Rule helpers used by routes
# ----------------------------------------------------------------------------

def update_rule_fields(
    site_id: str,
    rule_id: str,
    *,
    enabled: Optional[bool] = None,
    tracking: Optional[bool] = None,
    ruleInstruction: Optional[str] = None,
    outputInstruction: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update allowed fields for a rule in RULES_DB and mirror enabled to flat rules.

    Returns the updated rich rule dict from rulesJson.rules, or None if not found.
    """
    site = RULES_DB.get(site_id)
    if not site:
        return None
    updated: Optional[Dict[str, Any]] = None
    rich_rules = (site.get("rulesJson") or {}).get("rules") or []
    for r in rich_rules:
        if r.get("id") == rule_id:
            if enabled is not None:
                r["enabled"] = enabled
            if tracking is not None:
                r["tracking"] = tracking
            if ruleInstruction is not None:
                r["ruleInstruction"] = ruleInstruction
            if outputInstruction is not None:
                r["outputInstruction"] = outputInstruction
            updated = r
            break
    # Mirror enabled to flat rules if present
    if updated and enabled is not None and isinstance(site.get("rules"), list):
        for fr in site["rules"]:
            if fr.get("id") == rule_id:
                fr["enabled"] = enabled
                break
    return updated


def list_rules(siteId: str) -> List[Dict[str, Any]]:
    """Return rules in a normalized list, prioritizing rich rulesJson.rules."""
    site = RULES_DB.get(siteId) or {}
    rj = site.get("rulesJson") or {}
    rich = rj.get("rules") or []
    if rich:
        return rich
    # fallback to flat rules; project minimal fields
    flat = site.get("rules") or []
    out: List[Dict[str, Any]] = []
    for r in flat:
        out.append({
            "id": r.get("id"),
            "enabled": r.get("enabled", True),
            "tracking": r.get("tracking", False),
            "ruleInstruction": r.get("ruleInstruction"),
            "outputInstruction": r.get("outputInstruction"),
        })
    return out


def _ensure_site(site_id: str) -> Dict[str, Any]:
    site = RULES_DB.get(site_id)
    if not site:
        site = {"version": "ruleset-local", "rulesJson": {"ruleset": "local", "rules": []}}
        RULES_DB[site_id] = site
    if "rulesJson" not in site or not isinstance(site["rulesJson"], dict):
        site["rulesJson"] = {"rules": []}
    if "rules" not in site["rulesJson"] or not isinstance(site["rulesJson"]["rules"], list):
        site["rulesJson"]["rules"] = []
    return site


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return s or "rule"


def create_rule(site_id: str, rule_instruction: str, output_instruction: Optional[str] = None) -> Dict[str, Any]:
    site = _ensure_site(site_id)
    base_id = _slugify(rule_instruction)[:24]
    rid = base_id or "rule"
    existing_ids = {r.get("id") for r in site["rulesJson"]["rules"]}
    idx = 1
    cand = rid
    while cand in existing_ids:
        idx += 1
        cand = f"{rid}_{idx}"
    rule = {
        "id": cand,
        "enabled": True,
        "tracking": True,
        "ruleInstruction": rule_instruction,
        "outputInstruction": output_instruction or "",
        "triggers": [],
    }
    site["rulesJson"]["rules"].append(rule)
    return rule


def update_rule_triggers(site_id: str, rule_id: str, triggers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    site = RULES_DB.get(site_id)
    if not site:
        return None
    rich_rules = (site.get("rulesJson") or {}).get("rules") or []
    for r in rich_rules:
        if r.get("id") == rule_id:
            r["triggers"] = triggers or []
            return r
    return None
