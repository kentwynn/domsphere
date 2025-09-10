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
                "Generate contextual suggestions based on REAL site data. You MUST use tools to gather actual site information.\n\n"
                "CRITICAL RULES:\n"
                "- ALWAYS call get_sitemap first to see real available pages\n"
                "- ALWAYS call get_site_info to understand the business\n"
                "- ONLY use URLs that exist in the sitemap - never invent URLs or query parameters\n"
                "- Use the actual site structure, not generic e-commerce assumptions\n"
                "- If current page isn't in sitemap, call get_site_atlas for DOM context\n\n"
                "EXACT OUTPUT FORMAT (strict JSON):\n"
                '{"suggestions": [{\n'
                '  "type": "recommendation",\n'
                '  "id": "unique-id",\n'
                '  "title": "Engaging title",\n'
                '  "description": "Helpful description based on REAL site data",\n'
                '  "primaryCta": {"label": "Action", "kind": "link", "url": "/real-sitemap-url"},\n'
                '  "secondaryCtas": [{"label": "Alt action", "kind": "link", "url": "/another-real-url"}],\n'
                '  "meta": {"context": "actual_page_context"}\n'
                '}]}\n\n'
                "SUGGESTION TYPES:\n"
                "- recommendation: Product/content recommendations\n"
                "- upsell: Cross-sell or upgrade suggestions\n"
                "- info: Informational content\n"
                "- promotion: Discounts, offers, deals\n"
                "- guidance: Help user navigate or complete tasks\n"
                "- choice: Interactive multi-step flows\n\n"
                "CTA KINDS:\n"
                "- link/open: Navigate to URL (MUST be from sitemap)\n"
                "- click: Click DOM element (selector in payload)\n"
                "- add_to_cart: Add product to cart\n"
                "- choose: Make selection in multi-step flow\n"
                "- dom_fill: Fill form field (selector + value in payload)\n"
                "- route: SPA navigation\n"
                "- copy: Copy text to clipboard\n\n"
                "MANDATORY PROCESS:\n"
                "1. get_sitemap → Get actual available pages (REQUIRED)\n"
                "2. get_site_info → Get business context (REQUIRED)\n"
                "3. get_site_atlas → Analyze current page DOM if needed\n"
                "4. Generate suggestions using ONLY real URLs from sitemap\n"
                "5. Base suggestions on actual site structure, not assumptions\n\n"
                "FORBIDDEN:\n"
                "- Never invent URLs like '/products?sort=new' if not in sitemap\n"
                "- Never use generic e-commerce URLs without checking sitemap\n"
                "- Never skip tool calls - always gather real data first"
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
        # Get sitemap for URL validation
        try:
            sitemap_pages = self.tool_get_sitemap(request.siteId)
        except Exception:
            sitemap_pages = []

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

                # Validate URLs against sitemap
                data = self._validate_suggestion_urls(data, sitemap_pages)

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

    def _validate_suggestion_urls(self, suggestion_data: Dict[str, Any], sitemap_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate that suggestion URLs exist in the sitemap and fix invalid ones."""
        # Extract valid URLs from sitemap
        valid_urls = set()
        for page in sitemap_pages:
            if isinstance(page, dict) and "url" in page:
                valid_urls.add(page["url"])
            elif isinstance(page, dict) and "path" in page:
                valid_urls.add(page["path"])

        # Helper to validate and fix a CTA
        def fix_cta_url(cta: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(cta, dict) or "url" not in cta:
                return cta

            url = cta["url"]
            # Remove query parameters and fragments for validation
            clean_url = url.split("?")[0].split("#")[0]

            if clean_url not in valid_urls:
                # Try to find a similar URL or default to home
                fallback_url = "/" if "/" in valid_urls else (list(valid_urls)[0] if valid_urls else "/")
                cta["url"] = fallback_url

            return cta

        # Validate primary CTA
        if "primaryCta" in suggestion_data and isinstance(suggestion_data["primaryCta"], dict):
            suggestion_data["primaryCta"] = fix_cta_url(suggestion_data["primaryCta"])

        # Validate secondary CTAs
        if "secondaryCtas" in suggestion_data and isinstance(suggestion_data["secondaryCtas"], list):
            suggestion_data["secondaryCtas"] = [
                fix_cta_url(cta) if isinstance(cta, dict) else cta
                for cta in suggestion_data["secondaryCtas"]
            ]

        # Validate actions
        if "actions" in suggestion_data and isinstance(suggestion_data["actions"], list):
            suggestion_data["actions"] = [
                fix_cta_url(action) if isinstance(action, dict) else action
                for action in suggestion_data["actions"]
            ]

        return suggestion_data


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
