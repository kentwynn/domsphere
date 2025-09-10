from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import json
import httpx
from contracts.suggestion import Suggestion, CtaSpec
from contracts.agent_api import AgentSuggestNextRequest


class SuggestionAgent:
    """Intelligent suggestion agent that uses LLM tool-calling to generate contextual suggestions.

    The agent analyzes page context, user behavior, and site data to generate personalized
    suggestions with appropriate CTAs and actions. Falls back to deterministic suggestions
    when LLM is unavailable.
    """

    def __init__(self, api_url: Optional[str] = None, timeout_sec: float = 5.0, debug: bool = False) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.timeout = float(os.getenv("AGENT_TIMEOUT_SEC", str(timeout_sec)))
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.debug = debug

    # --- Tools (sitemap, info, atlas) -------------------------------------------------
    def tool_get_sitemap(self, site_id: str) -> List[Dict[str, Any]]:
        """Fetch site's sitemap to understand available pages and structure."""
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/map", params={"siteId": site_id})
            r.raise_for_status()
            data = r.json() or {}
            return data.get("pages", [])

    def tool_get_site_info(self, site_id: str) -> Dict[str, Any]:
        """Fetch site metadata and business info."""
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/info", params={"siteId": site_id})
            r.raise_for_status()
            return r.json() or {}

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        """Fetch DOM atlas snapshot for current page context."""
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/atlas", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    # --- LLM path --------------------------------------------------------------------
    def _llm_generate_suggestions(self, request: AgentSuggestNextRequest) -> Optional[List[Dict[str, Any]]]:
        """Use LLM with tool calling to generate contextual suggestions."""
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.tools import tool
            from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
        except Exception:
            if self.debug:
                print("[SuggestionAgent] LangChain/OpenAI not available; skipping LLM path")
            return None

        if not self.openai_token:
            if self.debug:
                print("[SuggestionAgent] OPENAI_TOKEN missing; skipping LLM path")
            return None

        # Define tools bound to this instance
        agent_self = self

        @tool("get_sitemap", return_direct=False)
        def get_sitemap(siteId: str) -> List[Dict[str, Any]]:  # type: ignore[override]
            """Fetch the site's sitemap pages array for the given siteId."""
            return agent_self.tool_get_sitemap(siteId)

        @tool("get_site_info", return_direct=False)
        def get_site_info(siteId: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch site metadata and business information."""
            return agent_self.tool_get_site_info(siteId)

        @tool("get_site_atlas", return_direct=False)
        def get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch DOM atlas snapshot for a specific URL."""
            return agent_self.tool_get_site_atlas(siteId, url)

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Good balance of cost/capability
        llm = ChatOpenAI(api_key=self.openai_token, model=model_name, temperature=0.7)  # Bit more creative
        llm_tools = [get_sitemap, get_site_info, get_site_atlas]
        llm = llm.bind_tools(llm_tools)

        sys = SystemMessage(
            content=(
                "Generate contextual suggestions for users based on their current page and behavior.\n\n"
                "EXACT OUTPUT FORMAT (strict JSON):\n"
                '{"suggestions": [{\n'
                '  "type": "recommendation",\n'
                '  "id": "unique-id",\n'
                '  "title": "Engaging title",\n'
                '  "description": "Helpful description",\n'
                '  "primaryCta": {"label": "Action", "kind": "link", "url": "/target"},\n'
                '  "secondaryCtas": [{"label": "Alt action", "kind": "link", "url": "/alt"}],\n'
                '  "meta": {"context": "page_specific"}\n'
                '}]}\n\n'
                "SUGGESTION TYPES:\n"
                "- recommendation: Product/content recommendations\n"
                "- upsell: Cross-sell or upgrade suggestions\n"
                "- info: Informational content\n"
                "- promotion: Discounts, offers, deals\n"
                "- guidance: Help user navigate or complete tasks\n"
                "- choice: Interactive multi-step flows\n\n"
                "CTA KINDS:\n"
                "- link/open: Navigate to URL\n"
                "- click: Click DOM element (selector in payload)\n"
                "- add_to_cart: Add product to cart\n"
                "- choose: Make selection in multi-step flow\n"
                "- dom_fill: Fill form field (selector + value in payload)\n"
                "- route: SPA navigation\n"
                "- copy: Copy text to clipboard\n\n"
                "CONTEXT ANALYSIS:\n"
                "1. Current page type (product, cart, checkout, etc.)\n"
                "2. User choices/input from previous steps\n"
                "3. Available site pages and structure\n"
                "4. DOM elements and data attributes\n"
                "5. Business context from site info\n\n"
                "PERSONALIZATION:\n"
                "- Use user's previous choices to tailor suggestions\n"
                "- Consider page context and available actions\n"
                "- Suggest logical next steps in user journey\n"
                "- Create multi-step flows for complex decisions\n\n"
                "STEPS:\n"
                "1. get_site_info → understand business context\n"
                "2. get_sitemap → see available pages/products\n"
                "3. get_site_atlas → analyze current page DOM\n"
                "4. Generate 1-3 relevant suggestions with actionable CTAs"
            )
        )

        human = HumanMessage(
            content=json.dumps({
                "siteId": request.siteId,
                "url": request.url,
                "ruleId": request.ruleId,
                "userChoices": request.input or {},
                "context": "Generate suggestions for this page and user state"
            })
        )

        messages = [sys, human]
        for turn in range(4):  # Allow tool calls + final response
            ai = llm.invoke(messages)
            tool_calls = getattr(ai, "tool_calls", None) or []

            if not tool_calls:
                # Expect final JSON content
                try:
                    if self.debug:
                        print(f"[SuggestionAgent] Final AI content (turn={turn}): {ai.content}")
                    data = _parse_json(ai.content)
                    suggestions = data.get("suggestions")
                    if isinstance(suggestions, list):
                        return suggestions
                except Exception as e:
                    if self.debug:
                        print(f"[SuggestionAgent] Failed to parse final response: {e}")
                return []

            messages.append(ai)
            for tc in tool_calls:
                name = tc["name"] if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc["args"] if isinstance(tc, dict) else getattr(tc, "args", {})
                if isinstance(args, str):
                    try:
                        parsed = json.loads(args)
                        if isinstance(parsed, dict):
                            args = parsed
                    except Exception:
                        pass

                if self.debug:
                    print(f"[SuggestionAgent] Tool call -> name={name}, args={args}")

                try:
                    if name == "get_sitemap":
                        result = get_sitemap.invoke(args)
                    elif name == "get_site_info":
                        result = get_site_info.invoke(args)
                    elif name == "get_site_atlas":
                        result = get_site_atlas.invoke(args)
                    else:
                        result = {"error": f"unknown tool {name}"}
                except Exception as e:
                    result = {"error": str(e)}

                if self.debug:
                    preview = result if isinstance(result, (dict, list)) else str(result)
                    print(f"[SuggestionAgent] Tool result for {name}: {str(preview)[:200]}")

                messages.append(
                    ToolMessage(
                        content=json.dumps(result)[:4000],
                        tool_call_id=(tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")),
                    )
                )
        return []

    def _fallback_suggestions(self, request: AgentSuggestNextRequest) -> List[Dict[str, Any]]:
        """Generate fallback suggestions using deterministic rules when LLM unavailable."""
        url = request.url or ""
        rule_id = request.ruleId or ""
        choices = request.input or {}

        suggestions = []

        # Product page suggestions
        if "/product/" in url:
            if "sku-abc" in url:
                suggestions.append({
                    "type": "upsell",
                    "id": f"upsell-{rule_id}",
                    "title": "Add this to your cart",
                    "description": "Popular item with great reviews",
                    "primaryCta": {"label": "Add to cart", "kind": "click", "payload": {"selector": "#add-to-cart"}},
                    "secondaryCtas": [{"label": "View details", "kind": "link", "url": url}]
                })
            else:
                suggestions.append({
                    "type": "recommendation",
                    "id": f"rec-{rule_id}",
                    "title": "You might also like",
                    "description": "Similar products to consider",
                    "primaryCta": {"label": "Browse similar", "kind": "link", "url": "/products"},
                    "secondaryCtas": [{"label": "Add to wishlist", "kind": "click", "payload": {"selector": ".wishlist-btn"}}]
                })

        # Cart page suggestions
        elif "/cart" in url:
            suggestions.append({
                "type": "promotion",
                "id": f"promo-{rule_id}",
                "title": "Free shipping available",
                "description": "Add $25 more for free shipping",
                "primaryCta": {"label": "Continue shopping", "kind": "link", "url": "/products"},
                "secondaryCtas": [{"label": "Proceed to checkout", "kind": "click", "payload": {"selector": "#checkout"}}]
            })

        # Checkout page suggestions
        elif "/checkout" in url:
            suggestions.append({
                "type": "guidance",
                "id": f"help-{rule_id}",
                "title": "Need help with checkout?",
                "description": "Contact support if you have questions",
                "primaryCta": {"label": "Continue", "kind": "click", "payload": {"selector": "#continue-checkout"}},
                "secondaryCtas": [{"label": "Contact support", "kind": "link", "url": "/support"}]
            })

        # Products/browse page
        elif "/products" in url:
            suggestions.append({
                "type": "guidance",
                "id": f"browse-{rule_id}",
                "title": "Browse by category",
                "description": "Find exactly what you're looking for",
                "primaryCta": {"label": "View categories", "kind": "link", "url": "/products?category=all"},
                "secondaryCtas": [
                    {"label": "Featured items", "kind": "link", "url": "/products?featured=true"},
                    {"label": "New arrivals", "kind": "link", "url": "/products?new=true"}
                ]
            })

        # Home page
        elif url.endswith("/") or "index.html" in url:
            suggestions.append({
                "type": "info",
                "id": f"welcome-{rule_id}",
                "title": "Welcome to our store",
                "description": "Discover our latest products and deals",
                "primaryCta": {"label": "Start shopping", "kind": "link", "url": "/products"},
                "secondaryCtas": [{"label": "View deals", "kind": "link", "url": "/products?sale=true"}]
            })

        # Default suggestion
        if not suggestions:
            suggestions.append({
                "type": "recommendation",
                "id": f"default-{rule_id}",
                "title": "Explore our products",
                "description": "Check out what we have to offer",
                "primaryCta": {"label": "Browse products", "kind": "link", "url": "/products"}
            })

        return suggestions

    # --- Public API ------------------------------------------------------------------
    def generate_suggestions(self, request: AgentSuggestNextRequest) -> List[Suggestion]:
        """Public API: Generate suggestions for the given request context.

        Returns a list of Suggestion objects that can be directly used in responses.
        """
        # Try LLM path first
        suggestions_data = self._llm_generate_suggestions(request)

        # Fall back to deterministic suggestions if LLM fails
        if not suggestions_data:
            if self.debug:
                print("[SuggestionAgent] Using fallback suggestions")
            suggestions_data = self._fallback_suggestions(request)

        # Convert to Suggestion objects and validate
        validated_suggestions = []
        for data in suggestions_data:
            try:
                # Ensure required fields
                if not isinstance(data, dict):
                    continue

                # Set defaults for required fields
                data.setdefault("type", "recommendation")
                data.setdefault("id", f"sug-{hash(str(data))}")

                # Convert CTA dicts to CtaSpec objects
                if "primaryCta" in data and isinstance(data["primaryCta"], dict):
                    data["primaryCta"] = CtaSpec(**data["primaryCta"])

                if "secondaryCtas" in data and isinstance(data["secondaryCtas"], list):
                    data["secondaryCtas"] = [
                        CtaSpec(**cta) if isinstance(cta, dict) else cta
                        for cta in data["secondaryCtas"]
                    ]

                if "actions" in data and isinstance(data["actions"], list):
                    data["actions"] = [
                        CtaSpec(**cta) if isinstance(cta, dict) else cta
                        for cta in data["actions"]
                    ]

                # Create Suggestion object
                suggestion = Suggestion(**data)
                validated_suggestions.append(suggestion)

            except Exception as e:
                if self.debug:
                    print(f"[SuggestionAgent] Failed to validate suggestion: {e}, data: {data}")
                continue

        if self.debug:
            print(f"[SuggestionAgent] Generated {len(validated_suggestions)} suggestions")

        return validated_suggestions


# --- Helpers --------------------------------------------------------------------
def _parse_json(text: str) -> Dict[str, Any]:
    """Parse a JSON object from a string, or return empty dict on failure."""
    try:
        # Try to find JSON in the response (sometimes LLM adds extra text)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            json_text = text[start:end]
            obj = json.loads(json_text)
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass

    # Fallback: try the entire text
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    return {}
