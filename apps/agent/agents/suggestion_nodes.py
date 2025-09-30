"""LangGraph agent node implementations used by the suggestion agent."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from helper.suggestion import parse_json_object
from core.logging import get_agent_logger
from .suggestion_llm import SuggestionLLMToolkit

logger = get_agent_logger(__name__)


def _coerce_step(raw: Any) -> int:
    try:
        step = int(raw)
    except (TypeError, ValueError):
        return 1
    return step if step > 0 else 1


def planner_agent_node(context: dict) -> dict:
    """LLM-based planner that selects which template type to use."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

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

    logger.debug(
        "Planner evaluating template type site=%s url=%s",
        context.get("siteId"),
        context.get("url"),
    )
    ai = llm.invoke([sys, human])

    try:
        data = parse_json_object(ai.content)
        if isinstance(data, dict) and "template_type" in data:
            logger.info(
                "Planner selected template=%s site=%s",
                data.get("template_type"),
                context.get("siteId"),
            )
            return data
    except Exception:
        logger.warning(
            "Planner response parse failed site=%s",
            context.get("siteId"),
        )

    logger.info("Planner defaulted to action template site=%s", context.get("siteId"))
    return {"template_type": "action"}


def template_agent_node(context: dict, toolkit: SuggestionLLMToolkit) -> dict:
    """Choose a template and fill in fields using available tools."""
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    @tool("plan_sitemap_query", return_direct=False)
    def tool_plan_sitemap_query(  # type: ignore[override]
        instruction: Optional[str] = None,
        outputInstruction: Optional[str] = None,
        ruleInstruction: Optional[str] = None,
    ) -> str:
        """Generate a focused sitemap search query driven by the suggestion's output instruction."""
        path_hint = None
        url_hint = context.get("url") or context.get("pageUrl")
        if isinstance(url_hint, str) and url_hint:
            parsed = urlparse(url_hint)
            path_hint = parsed.path or url_hint
        else:
            telemetry = context.get("telemetry") if isinstance(context, dict) else None
            attrs = telemetry.get("attributes") if isinstance(telemetry, dict) else None
            path_hint = attrs.get("path") if isinstance(attrs, dict) else None

        payload: Dict[str, Optional[str]] = {
            "output_instruction": (
                outputInstruction
                or context.get("outputInstruction")
                or instruction
            ),
            "page_hint": path_hint,
            "site_id": context.get("siteId"),
        }

        condensed_payload = {k: v for k, v in payload.items() if isinstance(v, str) and v.strip()}
        if not condensed_payload and isinstance(path_hint, str) and path_hint.strip():
            condensed_payload = {"page_hint": path_hint, "site_id": context.get("siteId")}

        payload_for_tool = json.dumps(condensed_payload) if condensed_payload else ""
        return toolkit.plan_sitemap_query(payload_for_tool)

    @tool("search_sitemap", return_direct=False)
    def tool_search_sitemap(siteId: str, query: str) -> Dict[str, Any]:  # type: ignore[override]
        """Search the sitemap for pages relevant to the provided query."""
        results = toolkit.search_sitemap(siteId, query)
        pages = [
            {
                "url": item.get("url"),
                "meta": item.get("meta") or {},
                "score": item.get("score"),
            }
            for item in results
            if isinstance(item, dict)
        ]
        top_url = pages[0]["url"] if pages and isinstance(pages[0].get("url"), str) else None
        top_info = None
        top_atlas = None
        if top_url:
            try:
                raw_info = toolkit.get_site_info(siteId, top_url)
                top_info = raw_info.model_dump() if hasattr(raw_info, "model_dump") else raw_info
            except Exception:
                logger.debug("search_sitemap top_url info fetch failed site=%s", siteId)
            try:
                raw_atlas = toolkit.get_site_atlas(siteId, top_url)
                top_atlas = raw_atlas.model_dump() if hasattr(raw_atlas, "model_dump") else raw_atlas
            except Exception:
                logger.debug("search_sitemap top_url atlas fetch failed site=%s", siteId)
        return {
            "results": results,
            "pages": pages,
            "top_url": top_url,
            "top_site_info": top_info,
            "top_site_atlas": top_atlas,
        }

    @tool("get_site_info", return_direct=False)
    def tool_get_site_info(siteId: str, url: str) -> Dict[str, Any]:
        """Fetch site info for a given site identifier and URL."""
        result = toolkit.get_site_info(siteId, url)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @tool("get_site_atlas", return_direct=False)
    def tool_get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:
        """Fetch the site atlas containing DOM selectors for the page."""
        result = toolkit.get_site_atlas(siteId, url)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @tool("get_templates", return_direct=False)
    def tool_get_templates() -> Dict[str, Dict[str, Any]]:
        """Return the available suggestion templates keyed by type."""
        return toolkit.get_templates()

    openai_token = toolkit.api_key or os.getenv("OPENAI_TOKEN")
    model_name = toolkit.model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(api_key=openai_token, model=model_name, temperature=0)
    llm = llm.bind_tools(
        [
            tool_plan_sitemap_query,
            tool_search_sitemap,
            tool_get_site_info,
            tool_get_site_atlas,
            tool_get_templates,
        ]
    )

    sys = SystemMessage(
        content=(
            "You are a suggestion template agent. "
            "Based on the 'outputInstruction' and context, choose which template ('info', 'action', or 'choice') best fits. "
            "CRITICAL: Start by calling plan_sitemap_query to extract concise keywords, then use search_sitemap "
            "to locate relevant pages (inspect the returned 'pages', 'top_url', 'top_site_info', and 'top_site_atlas'). "
            "The tool already fetches the top page's info/atlas for you—use them directly or fetch additional data if required. "
            "If you need a different page, call search_sitemap again with a refined query. Next, call get_templates to load template structures "
            "and use the atlas data to fill selectors before returning the final template. "
            "You MUST fill in the template structure exactly, replacing all <fill-in-*> placeholders with contextually appropriate values. "
            "For ACTION templates, follow these patterns: "
            "MULTI-STEP PATTERN (when multiple DOM operations needed): "
            "- primaryCta: kind='noop', label='Apply/Submit/etc', nextStep=2 "
            "- primaryActions: array of actual DOM operations (dom_fill, click, etc.) "
            "- secondaryCta: kind='noop', label='Cancel', nextClose=True "
            "- meta: step=1 "
            "SINGLE-STEP PATTERN (when only one DOM operation needed): "
            "- primaryCta: kind='click'/'dom_fill'/etc, direct payload with selector "
            "- NO primaryActions needed "
            "- secondaryCta: kind='noop', label='Cancel', nextClose=True (optional) "
            "- meta: step=1 "
            "If you cannot identify a reliable DOM selector, do NOT fabricate one. Instead set primaryCta.kind='open' and provide the navigation URL via 'url' or payload.url so the SDK can navigate directly. "
            "For CHOICE templates, follow this pattern: "
            "- actions: array of choice options (any number needed) with kind='choose' "
            "- each action has payload: {'name': '<field_name>', 'value': '<option_value>'} "
            "- Example: [{'label': 'School', 'kind': 'choose', 'payload': {'name': 'interest', 'value': 'school'}}, ...] "
            "- Can have 2, 3, 4, or more options depending on what makes sense for the choice "
            "- meta: step=<current_step> "
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
            "STATE RULES: "
            "- meta.step MUST be a string (\"1\", \"2\", ...) and increase as the flow progresses. "
            "- When context['userChoices'] is non-empty, treat them as confirmed selections and produce a final recommendation (type 'info' or 'action') unless absolutely necessary to ask again. "
            "- If you do need another choice step, increment meta.step and explain clearly what additional input is required. "
            "Analyze the outputInstruction to determine if it needs multiple DOM operations (use multi-step) or single operation (use single-step) or user choices (use choice). "
            "Return valid JSON: {\"template_type\": \"<chosen_type>\", \"suggestion_data\": <filled_template>, \"intermediate\": false}. "
            "Ensure proper JSON formatting with no trailing commas or syntax errors."
        )
    )

    human = HumanMessage(content=json.dumps(context))
    messages: List[Any] = [sys, human]

    logger.debug(
        "Template agent invoked site=%s url=%s",
        context.get("siteId"),
        context.get("url"),
    )

    for _ in range(4):
        ai = llm.invoke(messages)
        tool_calls = getattr(ai, "tool_calls", None) or []

        if not tool_calls:
            try:
                data = parse_json_object(ai.content)
                if isinstance(data, dict) and "template_type" in data:
                    logger.info(
                        "Template agent produced template=%s site=%s",
                        data.get("template_type"),
                        context.get("siteId"),
                    )
                    return data
            except Exception:
                logger.warning(
                    "Template agent parse failed site=%s",
                    context.get("siteId"),
                )
            logger.warning(
                "Template agent returned empty response site=%s",
                context.get("siteId"),
            )
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
                    logger.debug("Tool args parse failed name=%s", name)
            try:
                if name == "plan_sitemap_query":
                    result = tool_plan_sitemap_query.invoke(args)
                elif name == "search_sitemap":
                    result = tool_search_sitemap.invoke(args)
                elif name == "get_site_info":
                    result = tool_get_site_info.invoke(args)
                elif name == "get_site_atlas":
                    result = tool_get_site_atlas.invoke(args)
                elif name == "get_templates":
                    result = tool_get_templates.invoke(args)
                else:
                    result = {"error": f"unknown tool {name}"}
                if hasattr(result, "model_dump"):
                    result = result.model_dump()
            except Exception as exc:
                logger.exception(
                    "Template agent tool call failed name=%s site=%s",
                    name,
                    context.get("siteId"),
                )
                result = {"error": str(exc)}
            messages.append(
                ToolMessage(
                    content=json.dumps(result)[:4000],
                    tool_call_id=(
                        tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")
                    ),
                )
            )

    logger.warning("Template agent exhausted attempts site=%s", context.get("siteId"))
    return {}


def choice_manager_agent_node(
    context: dict,
    suggestion: dict,
    toolkit_factory: Callable[[], SuggestionLLMToolkit],
) -> dict:
    """Manage multi-step flows for choice suggestions."""

    if not isinstance(suggestion, dict):
        return {"final": True, "suggestion_data": suggestion, "template_type": "choice"}

    suggestion.setdefault("meta", {})
    suggestion["meta"]["step"] = str(_coerce_step(suggestion["meta"].get("step", 1)))

    if suggestion.get("type") != "choice":
        return {
            "final": True,
            "suggestion_data": suggestion,
            "template_type": suggestion.get("type"),
        }

    user_choices = context.get("userChoices") or {}
    if not user_choices:
        logger.debug(
            "Choice manager awaiting user input site=%s",
            context.get("siteId"),
        )
        return {
            "final": False,
            "suggestion_data": suggestion,
            "template_type": "choice",
        }

    max_rounds = int(os.getenv("CHOICE_FLOW_MAX_ROUNDS", "3"))
    current = suggestion
    current_step = _coerce_step(current["meta"].get("step", 1))
    history: List[Dict[str, Any]] = [current]

    if current_step >= 2:
        logger.info(
            "Choice manager finalizing existing step site=%s step=%s",
            context.get("siteId"),
            current_step,
        )
        return {
            "final": True,
            "suggestion_data": current,
            "template_type": "choice",
        }

    for attempt in range(max_rounds):
        logger.debug(
            "Choice manager requesting follow-up suggestion site=%s attempt=%s",
            context.get("siteId"),
            attempt + 1,
        )
        attempt_context = dict(context)
        attempt_context["choiceHistory"] = history[:]
        attempt_context["previousSuggestion"] = current
        next_toolkit = toolkit_factory()
        next_result = template_agent_node(attempt_context, next_toolkit)
        next_type = next_result.get("template_type") or current.get("type", "choice")
        next_data = next_result.get("suggestion_data")

        if not isinstance(next_data, dict):
            logger.warning(
                "Choice manager received empty follow-up site=%s attempt=%s",
                context.get("siteId"),
                attempt + 1,
            )
            return {
                "final": True,
                "suggestion_data": current,
                "template_type": next_type,
                "exhausted": True,
            }

        next_data.setdefault("meta", {})
        next_step = _coerce_step(next_data["meta"].get("step", current_step + 1))
        if next_step <= current_step:
            next_step = current_step + 1
        next_data["meta"]["step"] = str(next_step)

        history.append(next_data)
        current = next_data
        current_step = next_step

        if next_type != "choice":
            logger.info(
                "Choice manager resolved flow site=%s final_type=%s step=%s",
                context.get("siteId"),
                next_type,
                current_step,
            )
            return {
                "final": True,
                "suggestion_data": current,
                "template_type": next_type,
            }

        if current_step >= 2 and not next_result.get("intermediate", False):
            logger.debug(
                "Choice manager stopping after reaching step=%s site=%s",
                current_step,
                context.get("siteId"),
            )
            break

    return {
        "final": True,
        "suggestion_data": current,
        "template_type": current.get("type", "choice"),
        "exhausted": True,
    }
