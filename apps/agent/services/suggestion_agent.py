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

    # --- Tools (sitemap, info, atlas) -------------------------------------------------
    def tool_get_sitemap(self, site_id: str) -> List[Dict[str, Any]]:
        """Fetch site's sitemap to understand available pages and structure."""
        with httpx.Client() as client:
            r = client.get(f"{self.api_url}/site/map", params={"siteId": site_id})
            r.raise_for_status()
            data = r.json() or {}
            return data.get("pages", [])

    def tool_get_site_info(self, site_id: str, url: str) -> Dict[str, Any]:
        """Fetch site metadata and business info."""
        with httpx.Client() as client:
            r = client.get(f"{self.api_url}/site/info", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        """Fetch DOM atlas snapshot for current page context."""
        with httpx.Client() as client:
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
