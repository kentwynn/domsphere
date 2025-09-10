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

    def tool_get_output_schema(self) -> Dict[str, Any]:
        """Extract the actual output schema from Suggestion and CtaSpec contracts."""
        try:
            # Get the Pydantic model schema
            suggestion_schema = Suggestion.model_json_schema()
            cta_schema = CtaSpec.model_json_schema()

            # Extract useful information for the LLM
            suggestion_props = suggestion_schema.get("properties", {})
            cta_props = cta_schema.get("properties", {})

            # Extract enum values for specific fields
            type_field = suggestion_props.get("type", {})
            kind_field = cta_props.get("kind", {})

            return {
                "suggestion_fields": {
                    field: {
                        "type": info.get("type"),
                        "description": info.get("description"),
                        "enum": info.get("enum"),
                        "default": info.get("default")
                    }
                    for field, info in suggestion_props.items()
                },
                "cta_fields": {
                    field: {
                        "type": info.get("type"),
                        "description": info.get("description"),
                        "enum": info.get("enum"),
                        "default": info.get("default")
                    }
                    for field, info in cta_props.items()
                },
                "suggestion_required": suggestion_schema.get("required", []),
                "cta_required": cta_schema.get("required", [])
            }
        except Exception as e:
            # Fallback to basic structure if schema extraction fails
            return {
                "suggestion_fields": {
                    "type": {"type": "string", "description": "Type of suggestion"},
                    "id": {"type": "string", "description": "Unique identifier"},
                    "title": {"type": "string", "description": "Main title"},
                    "description": {"type": "string", "description": "Description text"},
                    "primaryCta": {"type": "object", "description": "Primary action button"},
                    "secondaryCtas": {"type": "array", "description": "Secondary action buttons"},
                    "actions": {"type": "array", "description": "Choice actions for multi-step flows"},
                    "primaryActions": {"type": "array", "description": "Sequential primary actions"},
                    "meta": {"type": "object", "description": "Metadata including step info"}
                },
                "cta_fields": {
                    "label": {"type": "string", "description": "Button label"},
                    "kind": {"type": "string", "description": "Action type"},
                    "url": {"type": "string", "description": "Target URL"},
                    "payload": {"type": "object", "description": "Action payload data"},
                    "nextStep": {"type": "integer", "description": "Next step number"},
                    "nextClose": {"type": "boolean", "description": "Close after action"}
                }
            }

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

        @tool("get_output_schema", return_direct=False)
        def get_output_schema() -> Dict[str, Any]:  # type: ignore[override]
            """Get the actual output schema for Suggestion and CtaSpec objects."""
            return agent_self.tool_get_output_schema()

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
        llm_tools = [get_output_schema, get_sitemap, get_site_info, get_site_atlas, get_rule_info]
        llm = llm.bind_tools(llm_tools)

        sys = SystemMessage(
            content=(
                "Generate actionable suggestions using ONLY real data from tools. NO hallucination.\n\n"
                "PROCESS:\n"
                "1. get_output_schema → understand interface\n"
                "2. get_rule_info → get outputInstruction\n"
                "3. get_sitemap → get valid URLs\n"
                "4. Generate suggestions using ONLY data from tools\n\n"
                "STRICT RULES:\n"
                "- Follow outputInstruction EXACTLY\n"
                "- Use ONLY URLs from sitemap - never invent\n"
                "- Use ONLY data from rule/site info - never invent codes/content\n"
                "- If rule has couponCode, use it. If not, don't add promo actions\n"
                "- Include actionable CTAs (primaryCta, secondaryCtas, actions)\n"
                "- For choice type: use actions array with choose kind\n"
                "- Return: {\"suggestions\": [...]}\n\n"
                "NO HALLUCINATION. Stick to facts from tools only."
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
                    if name == "get_output_schema":
                        result = get_output_schema.invoke(args)
                    elif name == "get_sitemap":
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
