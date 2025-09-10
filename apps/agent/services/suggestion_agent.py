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

    def __init__(self, api_url: Optional[str] = None) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))

    # --- Tools (sitemap, info, atlas) -------------------------------------------------
    def tool_get_sitemap(self, site_id: str) -> List[Dict[str, Any]]:
        """Fetch site's sitemap to understand available pages and structure."""
        with httpx.Client(timeout=self.http_timeout) as client:
            r = client.get(f"{self.api_url}/site/map", params={"siteId": site_id})
            r.raise_for_status()
            data = r.json() or {}
            return data.get("pages", [])

    def tool_get_site_info(self, site_id: str, url: str) -> Dict[str, Any]:
        """Fetch site metadata and business info."""
        with httpx.Client(timeout=self.http_timeout) as client:
            r = client.get(f"{self.api_url}/site/info", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        """Fetch DOM atlas snapshot for current page context."""
        with httpx.Client(timeout=self.http_timeout) as client:
            r = client.get(f"{self.api_url}/site/atlas", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    def tool_get_rule_info(self, site_id: str, rule_id: str) -> Dict[str, Any]:
        """Fetch rule information including output instructions."""
        with httpx.Client(timeout=self.http_timeout) as client:
            r = client.get(f"{self.api_url}/rule/{rule_id}", params={"siteId": site_id})
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
            return None

        if not self.openai_token:
            return None        # Define tools bound to this instance
        agent_self = self

        @tool("get_sitemap", return_direct=False)
        def get_sitemap(siteId: str) -> List[Dict[str, Any]]:  # type: ignore[override]
            """Fetch the site's sitemap pages array for the given siteId."""
            return agent_self.tool_get_sitemap(siteId)

        @tool("get_site_info", return_direct=False)
        def get_site_info(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch site metadata and business information."""
            return agent_self.tool_get_site_info(siteId, url)

        @tool("get_site_atlas", return_direct=False)
        def get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch DOM atlas snapshot for a specific URL."""
            return agent_self.tool_get_site_atlas(siteId, url)

        @tool("get_rule_info", return_direct=False)
        def get_rule_info(siteId: str, ruleId: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch rule's output instruction to determine what type of suggestions to generate."""
            rule_data = agent_self.tool_get_rule_info(siteId, ruleId)
            # Extract only the outputInstruction to keep context clean and focused
            output_instruction = rule_data.get("outputInstruction", "")
            return {
                "outputInstruction": output_instruction,
                "ruleId": ruleId
            }

        model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano")  # Good balance of cost/capability
        llm = ChatOpenAI(api_key=self.openai_token, model=model_name, temperature=0.7)  # Bit more creative
        llm_tools = [get_sitemap, get_site_info, get_site_atlas, get_rule_info]
        llm = llm.bind_tools(llm_tools)

        sys = SystemMessage(
            content=(
                "Generate contextual suggestions based on REAL site data and the specific rule's outputInstruction.\n\n"
                "CRITICAL RULES:\n"
                "- ALWAYS call get_rule_info first to get the outputInstruction for this specific rule\n"
                "- ALWAYS call get_sitemap second to see ALL available pages and URLs\n"
                "- FOLLOW the rule's outputInstruction exactly - this determines the TYPE and CONTENT of suggestions\n"
                "- ONLY use URLs that exist in the sitemap - NEVER invent URLs or add query parameters\n"
                "- Call get_site_info to understand the business context\n"
                "- Call get_site_atlas if you need DOM context for the current page\n"
                "- Handle userChoices for multi-step flows properly\n"
                "- Use the actual site structure from sitemap, not assumptions\n\n"
                "EXACT OUTPUT FORMAT (strict JSON):\n"
                '{"suggestions": [{\n'
                '  "type": "recommendation|upsell|info|promotion|guidance|choice|banner|coupon|checkout",\n'
                '  "id": "unique-id",\n'
                '  "title": "Engaging title",\n'
                '  "description": "Helpful description based on rule outputInstruction",\n'
                '  "primaryCta": {"label": "Action", "kind": "open|click|choose|dom_fill|add_to_cart|noop", "url": "/exact-sitemap-url", "payload": {"selector": "#id", "value": "data"}},\n'
                '  "secondaryCtas": [{"label": "Alt action", "kind": "open", "url": "/another-exact-sitemap-url"}],\n'
                '  "actions": [{"label": "Choice", "kind": "choose", "payload": {"name": "fieldName", "value": "choiceValue"}}],\n'
                '  "primaryActions": [{"label": "Fill Code", "kind": "dom_fill", "payload": {"selector": "#promo-code", "value": "SAVE10"}}],\n'
                '  "meta": {"step": 1, "context": "current_page_context"}\n'
                '}]}\n\n'
                "SUGGESTION TYPES:\n"
                "- recommendation: Product/content recommendations\n"
                "- upsell: Cross-sell or upgrade suggestions\n"
                "- info: Informational content\n"
                "- promotion: Discounts, offers, deals\n"
                "- guidance: Help user navigate or complete tasks\n"
                "- choice: Interactive multi-step flows (handle userChoices to determine step)\n"
                "- banner: Celebratory or promotional banners\n"
                "- coupon: Promo code applications\n"
                "- checkout: Checkout flow suggestions\n\n"
                "CTA KINDS:\n"
                "- open: Navigate to URL (MUST be exact URL from sitemap)\n"
                "- click: Click DOM element (use selector in payload: {'selector': '#button-id'})\n"
                "- choose: Make selection in multi-step flow (payload: {'name': 'field', 'value': 'choice'})\n"
                "- dom_fill: Fill form field (payload: {'selector': '#input', 'value': 'text'})\n"
                "- add_to_cart: Add product to cart\n"
                "- noop: No operation, just a label (can have nextStep, nextClose)\n"
                "- route: SPA navigation\n"
                "- copy: Copy text to clipboard\n\n"
                "MULTI-STEP CHOICE FLOWS:\n"
                "- Check userChoices to determine current step\n"
                "- For choice type, use 'actions' array with 'choose' kind\n"
                "- Include step number in meta: {'step': 1}\n"
                "- Progress through choices until all collected, then provide final recommendation\n"
                "- Example: interest -> ageGroup -> color -> final recommendation\n\n"
                "SMART PATTERNS:\n"
                "- Cart promotions: Use 'coupon' type with dom_fill + click actions for promo codes\n"
                "- Product pages: Use 'upsell' type with add_to_cart or navigation\n"
                "- Home page: Use 'info' or 'banner' types for welcomes/announcements\n"
                "- Time-based: Use 'guidance' for helping users who've been browsing\n\n"
                "MANDATORY PROCESS:\n"
                "1. get_rule_info → Get the outputInstruction (REQUIRED FIRST)\n"
                "2. get_sitemap → Get ALL available URLs (REQUIRED SECOND)\n"
                "3. get_site_info → Get business context\n"
                "4. get_site_atlas → Get page context if needed\n"
                "5. Check userChoices for multi-step flows\n"
                "6. Generate suggestions following outputInstruction exactly\n"
                "7. Use ONLY exact URLs from the sitemap list\n\n"
                "URL RULES:\n"
                "- Use exact URLs from sitemap (e.g., '/products', '/cart', '/product/sku-abc')\n"
                "- NEVER add query parameters like '?sort=best_sellers'\n"
                "- NEVER invent URLs not in the sitemap\n"
                "- If you need a specific page type, find the closest match in sitemap\n\n"
                "KEY FOCUS:\n"
                "- The rule's outputInstruction is MANDATORY - follow it exactly\n"
                "- Handle multi-step flows intelligently using userChoices\n"
                "- Use appropriate suggestion types and CTA kinds\n"
                "- Only use real URLs that exist in the sitemap\n"
                "- Be contextual and relevant to the current page\n"
                "- Include proper meta data with step numbers for flows"
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
                    data = _parse_json(ai.content)
                    suggestions = data.get("suggestions")
                    if isinstance(suggestions, list):
                        return suggestions
                except Exception as e:
                    pass
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

                try:
                    if name == "get_sitemap":
                        result = get_sitemap.invoke(args)
                    elif name == "get_site_info":
                        result = get_site_info.invoke(args)
                    elif name == "get_site_atlas":
                        result = get_site_atlas.invoke(args)
                    elif name == "get_rule_info":
                        result = get_rule_info.invoke(args)
                    else:
                        result = {"error": f"unknown tool {name}"}
                except Exception as e:
                    result = {"error": str(e)}

                messages.append(
                    ToolMessage(
                        content=json.dumps(result)[:4000],
                        tool_call_id=(tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")),
                    )
                )
        return []

    # --- Public API ------------------------------------------------------------------
    def generate_suggestions(self, request: AgentSuggestNextRequest) -> List[Suggestion]:
        """Public API: Generate suggestions for the given request context.

        Returns a list of Suggestion objects that can be directly used in responses.
        """
        # Generate suggestions using LLM
        suggestions_data = self._llm_generate_suggestions(request)

        # Return empty list if no suggestions generated
        if not suggestions_data:
            return []

        # Convert to Suggestion objects
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
                continue

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
