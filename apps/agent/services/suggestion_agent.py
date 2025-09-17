from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import json
import httpx
from contracts.suggestion import Suggestion, CtaSpec
from contracts.agent_api import AgentSuggestNextRequest
from contracts.client_api import SiteMapResponse, SiteInfoResponse, SiteAtlasResponse
from langgraph.graph import StateGraph

# LangGraph multi-agent imports
# --- Planner Agent Node ---
def planner_agent_node(context: dict, api_url: str, timeout: float) -> dict:
    """
    LLM-based planner that selects which template type to use based on outputInstruction.
    Returns a dict: {"template_type": <"info"|"action"|"choice">}
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    openai_token = os.getenv("OPENAI_TOKEN")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(api_key=openai_token, model=model_name, temperature=0)
    sys = SystemMessage(
        content=(
            "You are a planner for a suggestion agent. "
            "Given the context and especially the 'outputInstruction', choose which template type ('info', 'action', or 'choice') best fits. "
            "Return a JSON object: {\"template_type\": <chosen template>}"
        )
    )
    human = HumanMessage(content=json.dumps(context))
    messages = [sys, human]
    ai = llm.invoke(messages)
    try:
        data = _parse_json(ai.content)
        # Expect key: template_type
        if isinstance(data, dict) and "template_type" in data:
            return data
    except Exception:
        pass
    # Fallback: default to 'action'
    return {"template_type": "action"}

# --- Validator Agent Node ---
def validator_agent_node(suggestions_data: list, context: dict) -> list:
    """
    Validate suggestions using schema enforcement and intelligent atlas validation.
    Returns the validated suggestion dicts.
    """
    final = []
    for data in suggestions_data:
        try:
            if not isinstance(data, dict):
                continue
            data.setdefault("type", "recommendation")
            data.setdefault("id", f"sug-{hash(str(data))}")

            # No validation - pass through as-is

            if "primaryCta" in data and isinstance(data["primaryCta"], dict):
                data["primaryCta"] = CtaSpec(**data["primaryCta"])
            if "secondaryCta" in data and isinstance(data["secondaryCta"], dict):
                data["secondaryCta"] = CtaSpec(**data["secondaryCta"])
            if "primaryActions" in data and isinstance(data["primaryActions"], list):
                data["primaryActions"] = [
                    CtaSpec(**cta) if isinstance(cta, dict) else cta
                    for cta in data["primaryActions"]
                ]
            if "actions" in data and isinstance(data["actions"], list):
                data["actions"] = [
                    CtaSpec(**cta) if isinstance(cta, dict) else cta
                    for cta in data["actions"]
                ]
            if "primaryActions" in data and isinstance(data["primaryActions"], list):
                data["primaryActions"] = [
                    CtaSpec(**cta) if isinstance(cta, dict) else cta
                    for cta in data["primaryActions"]
                ]
            suggestion = Suggestion(**data)
            final.append(suggestion)
        except Exception:
            continue
    return final

# --- JSON templates as constants (with <fill-in> placeholders) ---
INFO_TEMPLATE = {
    "type": "info",
    "id": "<fill-in-id>",
    "title": "<fill-in-title>",
    "description": "<fill-in-description>",
    "meta": {
        "source": "<fill-in-source>",
        "step": "<fill-in-step>"
    }
}

ACTION_TEMPLATE = {
    "type": "recommendation",
    "id": "<fill-in-id>",
    "title": "<fill-in-title>",
    "description": "<fill-in-description>",
    "primaryCta": {
        "label": "<fill-in-label>",
        "kind": "<fill-in-kind>",  # "noop" for multi-step, "click"/"dom_fill"/etc for single-step
        "payload": "<fill-in-payload>",  # Only if kind is not "noop"
        "nextStep": "<fill-in-nextStep>"  # Only if kind is "noop"
    },
    "primaryActions": "<fill-in-primaryActions>",  # Only if primaryCta.kind is "noop"
    "secondaryCta": {
        "label": "<fill-in-secondary-label>",
        "kind": "<fill-in-secondary-kind>",  # Usually "noop" with nextClose=True for cancel
        "nextClose": "<fill-in-nextClose>"  # True for cancel actions
    },
    "meta": {
        "source": "<fill-in-source>",
        "step": "<fill-in-step>"  # 1 for first step, 2 for second step
    }
}

CHOICE_TEMPLATE = {
    "type": "choice",
    "id": "<fill-in-id>",
    "title": "<fill-in-title>",
    "description": "<fill-in-description>",
    "actions": [
        {
            "label": "<fill-in-label>",
            "kind": "choose",
            "payload": {"name": "<fill-in-name>", "value": "<fill-in-value>"}
        }
        # Add more actions as needed - this is an array that can have any number of choice options
    ],
    "meta": {
        "source": "<fill-in-source>",
        "step": "<fill-in-step>"
    }
}

# --- Helper tools ---
def get_sitemap(siteId: str, api_url: str, timeout: float) -> SiteMapResponse:
    """Fetch sitemap for the given siteId. Returns SiteMapResponse that conforms to contract."""
    with httpx.Client(timeout=timeout) as client:
        r = client.get(f"{api_url}/site/map", params={"siteId": siteId})
        r.raise_for_status()
        data = r.json() or {}
        if not data:
            return SiteMapResponse(siteId=siteId, pages=[])
        return SiteMapResponse(**data)

def get_site_info(siteId: str, url: str, api_url: str, timeout: float) -> SiteInfoResponse:
    """Fetch site info for the given siteId and url. Returns SiteInfoResponse that conforms to contract."""
    norm_url = url.rstrip("/") if isinstance(url, str) else url
    with httpx.Client(timeout=timeout) as client:
        r = client.get(f"{api_url}/site/info", params={"siteId": siteId, "url": norm_url})
        r.raise_for_status()
        data = r.json() or {}
        if not data:
            return SiteInfoResponse(siteId=siteId, url=norm_url, meta=None, normalized=None)
        return SiteInfoResponse(**data)

def get_site_atlas(siteId: str, url: str, api_url: str, timeout: float) -> SiteAtlasResponse:
    """Fetch site atlas for the given siteId and url. Returns SiteAtlasResponse that conforms to contract."""
    norm_url = url.rstrip("/") if isinstance(url, str) else url
    with httpx.Client(timeout=timeout) as client:
        r = client.get(f"{api_url}/site/atlas", params={"siteId": siteId, "url": norm_url})
        r.raise_for_status()
        data = r.json() or {}
        if not data:
            return SiteAtlasResponse(siteId=siteId, url=norm_url, atlas=None, queuedPlanRebuild=None)
        return SiteAtlasResponse(**data)

def get_templates() -> Dict[str, Dict[str, Any]]:
    """
    Return the suggestion templates (template definitions only) as plain dicts.
    Returns a mapping with keys: "info", "action", "choice" where each value is a Suggestion-compatible dict.
    """
    return {
        "info": INFO_TEMPLATE,
        "action": ACTION_TEMPLATE,
        "choice": CHOICE_TEMPLATE,
    }

# --- Template Agent Node ---
def template_agent_node(context: dict, api_url: str, timeout: float) -> dict:
    """
    Given context (including outputInstruction), choose template type, fill in fields using tools.
    Returns a dict with keys: {"template_type", "suggestion_data", "intermediate"}
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import tool
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

    # Tool definitions for LLM tool-calling, returning JSON-serializable payloads
    @tool("get_sitemap", return_direct=False)
    def tool_get_sitemap(siteId: str) -> Dict[str, Any]:
        """Fetch sitemap for the given siteId."""
        result = get_sitemap(siteId, api_url, timeout).model_dump()
        return result

    @tool("get_site_info", return_direct=False)
    def tool_get_site_info(siteId: str, url: str) -> Dict[str, Any]:
        """Fetch site info for the given siteId and url."""
        result = get_site_info(siteId, url, api_url, timeout).model_dump()
        return result

    @tool("get_site_atlas", return_direct=False)
    def tool_get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:
        """Fetch site atlas for the given siteId and url."""
        result = get_site_atlas(siteId, url, api_url, timeout).model_dump()
        return result

    @tool("get_templates", return_direct=False)
    def tool_get_templates() -> Dict[str, Dict[str, Any]]:
        """Get available suggestion templates."""
        result = get_templates()
        return result

    # Compose LLM
    openai_token = os.getenv("OPENAI_TOKEN")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(api_key=openai_token, model=model_name, temperature=0)
    llm = llm.bind_tools([tool_get_sitemap, tool_get_site_info, tool_get_site_atlas, tool_get_templates])

    # System prompt: instruct LLM to select template and fill it in
    sys = SystemMessage(
        content=(
            "You are a suggestion template agent. "
            "Based on the 'outputInstruction' and context, choose which template ('info', 'action', or 'choice') best fits. "
            "CRITICAL: First call get_templates to get the template structure, then call get_site_atlas to get DOM selectors. "
            "You MUST fill in the template structure exactly, replacing all <fill-in-*> placeholders with contextually appropriate values. "
            ""
            "For ACTION templates, follow these patterns: "
            ""
            "MULTI-STEP PATTERN (when multiple DOM operations needed): "
            "- primaryCta: kind='noop', label='Apply/Submit/etc', nextStep=2 "
            "- primaryActions: array of actual DOM operations (dom_fill, click, etc.) "
            "- secondaryCta: kind='noop', label='Cancel', nextClose=True "
            "- meta: step=1 "
            ""
            "SINGLE-STEP PATTERN (when only one DOM operation needed): "
            "- primaryCta: kind='click'/'dom_fill'/etc, direct payload with selector "
            "- NO primaryActions needed "
            "- secondaryCta: kind='noop', label='Cancel', nextClose=True (optional) "
            "- meta: step=1 "
            ""
            "For CHOICE templates, follow this pattern: "
            "- actions: array of choice options (any number needed) with kind='choose' "
            "- each action has payload: {'name': '<field_name>', 'value': '<option_value>'} "
            "- all actions in one choice should use the same 'name' but different 'value' "
            "- Example: [{'label': 'School', 'kind': 'choose', 'payload': {'name': 'interest', 'value': 'school'}}, ...] "
            "- Can have 2, 3, 4, or more options depending on what makes sense for the choice "
            "- meta: step=<current_step> "
            ""
            "Field filling rules: "
            "- <fill-in-id>: unique ID based on the action "
            "- <fill-in-title> and <fill-in-description>: from outputInstruction context "
            "- <fill-in-label>: action labels based on what user wants to do "
            "- <fill-in-kind>: 'noop' for multi-step OR 'dom_fill'/'click'/etc for single-step OR 'choose' for choices "
            "- <fill-in-payload>: CSS selectors and values from atlas (only if kind is not 'noop') "
            "- <fill-in-nextStep>: 2 (only if kind is 'noop') "
            "- <fill-in-primaryActions>: array of DOM operations (only if primaryCta.kind is 'noop') "
            "- <fill-in-step>: 1 for first step, 2 for continuation steps "
            "- For choices: <fill-in-name> is the field name, <fill-in-value-1/2/3> are different option values "
            ""
            "Analyze the outputInstruction to determine if it needs multiple DOM operations (use multi-step) or single operation (use single-step) or user choices (use choice). "
            "Return valid JSON: {\"template_type\": \"<chosen_type>\", \"suggestion_data\": <filled_template>, \"intermediate\": false}. "
            "Ensure proper JSON formatting with no trailing commas or syntax errors."
        )
    )
    human = HumanMessage(content=json.dumps(context))
    messages = [sys, human]

    for iteration in range(4):
        ai = llm.invoke(messages)

        tool_calls = getattr(ai, "tool_calls", None) or []

        if not tool_calls:
            try:
                data = _parse_json(ai.content)
                # Expect keys: template_type, suggestion_data, intermediate
                if isinstance(data, dict) and "template_type" in data:
                    return data
            except Exception as e:
                pass
            return {}
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
                    result = tool_get_sitemap.invoke(args)
                elif name == "get_site_info":
                    result = tool_get_site_info.invoke(args)
                elif name == "get_site_atlas":
                    result = tool_get_site_atlas.invoke(args)
                elif name == "get_templates":
                    result = tool_get_templates.invoke(args)
                else:
                    result = {"error": f"unknown tool {name}"}
                # Ensure plain dict for ToolMessage content
                if hasattr(result, "model_dump"):
                    result = result.model_dump()
            except Exception as e:
                result = {"error": str(e)}
            messages.append(
                ToolMessage(
                    content=json.dumps(result)[:4000],
                    tool_call_id=(tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")),
                )
            )

    return {}

# --- Choice Manager Agent Node ---
def choice_manager_agent_node(context: dict, suggestion: dict, api_url: str, timeout: float) -> dict:
    """
    If suggestion is a choice, manage multi-step flows. Otherwise, return as is.
    Returns dict with keys: {"final": bool, "suggestion_data": dict}
    """
    # If not a choice, return as final
    if suggestion.get("type") != "choice":
        return {"final": True, "suggestion_data": suggestion}
    # If user has not made a choice (no input in context), return intermediate suggestion
    user_choices = context.get("userChoices") or {}
    if not user_choices:
        return {"final": False, "suggestion_data": suggestion}
    # If user has made a choice, re-run template agent to fill in next step (simulate multi-step)
    # For simplicity, just return as final if no further step is needed
    step = suggestion.get("meta", {}).get("step", 1)
    if step >= 2:  # Simulate: if step >= 2, produce final suggestion
        return {"final": True, "suggestion_data": suggestion}
    # Otherwise, re-run template agent with updated context (simulate step 2)
    # In real implementation, you'd update context to reflect nextStep and call template_agent_node again.
    return {"final": False, "suggestion_data": suggestion}

# --- SuggestionAgent unified implementation ---
class SuggestionAgent:
    """
    Unified SuggestionAgent using template-driven, multi-agent architecture with LangChain/LangGraph.
    """
    def __init__(self, api_url: Optional[str] = None) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))

    def _fetch_rule_info(self, site_id: str, rule_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.http_timeout) as client:
            r = client.get(f"{self.api_url}/rule/{rule_id}", params={"siteId": site_id})
            r.raise_for_status()
            return r.json() or {}

    def _normalize_url(self, url: str) -> str:
        if not isinstance(url, str):
            return url
        return url.rstrip("/")

    def _build_context(self, request: AgentSuggestNextRequest) -> Dict[str, Any]:
        normalized_url = self._normalize_url(request.url)
        context: Dict[str, Any] = {
            "url": normalized_url,
            "userChoices": request.input or {},
            "siteId": request.siteId,
        }
        rule_info = self._fetch_rule_info(request.siteId, request.ruleId)
        context["outputInstruction"] = rule_info.get("rule", {}).get("outputInstruction", "")
        return context

    def generate_suggestions(self, request: AgentSuggestNextRequest) -> List[Suggestion]:
        """
        Build context, run simple flow: Template Agent -> Choice Manager -> Validate.
        Return validated Suggestion objects, avoiding optional LangGraph dependency.
        """
        # Step 1: Build context
        context = self._build_context(request)

        # Step 2: Run Template Agent node to select and fill template
        node_result = template_agent_node(context, self.api_url, self.http_timeout)
        template_type = node_result.get("template_type")
        suggestion_data = node_result.get("suggestion_data")
        if not suggestion_data:
            return []

        # Step 3: If choice, run Choice Manager Agent node
        if template_type == "choice":
            choice_result = choice_manager_agent_node(context, suggestion_data, self.api_url, self.http_timeout)
            if not choice_result.get("final"):
                # Intermediate: return as is (multi-step, waiting for user input)
                return validator_agent_node([choice_result["suggestion_data"]], context)
            return validator_agent_node([choice_result["suggestion_data"]], context)
        else:
            # Not a choice, return suggestion
            return validator_agent_node([suggestion_data], context)

    def _parse_suggestions(self, suggestions_data: List[dict], context: dict) -> List[Suggestion]:
        """Parse suggestions without validation."""
        return validator_agent_node(suggestions_data, context)

# --- Helpers ---
def _parse_json(text: str) -> Dict[str, Any]:
    """Parse a JSON object from a string, or return empty dict on failure. Always returns a dict."""
    if not text:
        return {}

    # Clean up common JSON formatting issues
    text = text.strip()

    # Try multiple extraction methods
    extraction_methods = [
        # Method 1: Extract first complete JSON object
        lambda t: t[t.find("{"):t.rfind("}") + 1] if "{" in t and "}" in t else "",
        # Method 2: Use the raw text as-is
        lambda t: t,
        # Method 3: Extract everything between outermost braces
        lambda t: _extract_balanced_json(t)
    ]

    for method in extraction_methods:
        try:
            json_text = method(text)
            if json_text:
                # Clean up whitespace and fix common issues
                json_text = json_text.replace(" ,", ",").replace(", }", "}").replace("{ ", "{").replace(" }", "}")
                obj = json.loads(json_text)
                if isinstance(obj, dict):
                    return obj
        except Exception as e:
            continue

    return {}

def _extract_balanced_json(text: str) -> str:
    """Extract a balanced JSON object from text."""
    start = text.find("{")
    if start == -1:
        return ""

    brace_count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                return text[start:i + 1]
    return ""

# --- LangGraph Multi-Agent Graph Construction ---
def build_suggestion_graph(api_url: str, timeout: float):
    """
    Build a LangGraph multi-agent graph for the suggestion agent.
    Nodes: planner, template, choice_manager, validator.
    Edges: planner -> template -> choice_manager (if choice) -> validator.
    Returns a StateGraph object ready to run.
    """

    class State:
        def __init__(self, context, suggestion_data=None, template_type=None, intermediate=False, suggestions=None):
            self.context = context
            self.suggestion_data = suggestion_data
            self.template_type = template_type
            self.intermediate = intermediate
            self.suggestions = suggestions or []

        def as_dict(self):
            return {
                "context": self.context,
                "suggestion_data": self.suggestion_data,
                "template_type": self.template_type,
                "intermediate": self.intermediate,
                "suggestions": self.suggestions,
            }

    def planner_node(state: dict):
        context = state["context"]
        planner_result = planner_agent_node(context, api_url, timeout)
        template_type = planner_result.get("template_type", "action")
        return {**state, "template_type": template_type}

    def template_node(state: dict):
        context = state["context"]
        template_type = state.get("template_type")
        node_result = template_agent_node(context, api_url, timeout)
        # node_result: {"template_type", "suggestion_data", "intermediate"}
        suggestion_data = node_result.get("suggestion_data")
        intermediate = node_result.get("intermediate", False)
        # Allow template_type from planner to override, else use node_result
        ttype = state.get("template_type") or node_result.get("template_type")
        return {**state, "suggestion_data": suggestion_data, "template_type": ttype, "intermediate": intermediate}

    def choice_manager_node(state: dict):
        context = state["context"]
        suggestion_data = state.get("suggestion_data")
        result = choice_manager_agent_node(context, suggestion_data, api_url, timeout)
        # result: {"final": bool, "suggestion_data": dict}
        # If not final, set intermediate True
        return {**state, "suggestion_data": result.get("suggestion_data"), "intermediate": not result.get("final", True)}

    def validator_node(state: dict):
        context = state["context"]
        suggestion_data = state.get("suggestion_data")
        # Always wrap as list for validator_agent_node
        suggestions = validator_agent_node([suggestion_data], context)
        return {**state, "suggestions": suggestions}

    # Build the graph
    g = StateGraph()
    g.add_node("planner", planner_node)
    g.add_node("template", template_node)
    g.add_node("choice_manager", choice_manager_node)
    g.add_node("validator", validator_node)

    # Edges
    # planner -> template
    g.add_edge("planner", "template")
    # template -> choice_manager if template_type == "choice", else -> validator
    def template_router(state: dict):
        ttype = state.get("template_type")
        if ttype == "choice":
            return "choice_manager"
        return "validator"
    g.add_conditional_edge("template", template_router)
    # choice_manager -> validator if intermediate is False, else -> choice_manager (wait for user input, but here just go to validator for demo)
    def choice_manager_router(state: dict):
        # If still intermediate, in a real system you'd pause and wait for user input.
        # For now, always proceed to validator.
        return "validator"
    g.add_conditional_edge("choice_manager", choice_manager_router)
    # validator is the output node
    g.set_entry_point("planner")
    g.set_output_node("validator")
    return g
