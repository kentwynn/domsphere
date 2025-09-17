"""LangGraph agent node implementations used by the suggestion agent."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from helper.suggestion import (
    get_site_atlas,
    get_site_info,
    get_sitemap,
    parse_json_object,
)
from templates.suggestion import get_templates
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


def planner_agent_node(context: dict, api_url: str, timeout: float) -> dict:
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


def template_agent_node(context: dict, api_url: str, timeout: float) -> dict:
    """Choose a template and fill in fields using available tools."""
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    @tool("get_sitemap", return_direct=False)
    def tool_get_sitemap(siteId: str) -> Dict[str, Any]:
        """Fetch the sitemap for the provided site identifier."""
        return get_sitemap(siteId, api_url, timeout).model_dump()

    @tool("get_site_info", return_direct=False)
    def tool_get_site_info(siteId: str, url: str) -> Dict[str, Any]:
        """Fetch site info for a given site identifier and URL."""
        return get_site_info(siteId, url, api_url, timeout).model_dump()

    @tool("get_site_atlas", return_direct=False)
    def tool_get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:
        """Fetch the site atlas containing DOM selectors for the page."""
        return get_site_atlas(siteId, url, api_url, timeout).model_dump()

    @tool("get_templates", return_direct=False)
    def tool_get_templates() -> Dict[str, Dict[str, Any]]:
        """Return the available suggestion templates keyed by type."""
        return get_templates()

    openai_token = os.getenv("OPENAI_TOKEN")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(api_key=openai_token, model=model_name, temperature=0)
    llm = llm.bind_tools(
        [tool_get_sitemap, tool_get_site_info, tool_get_site_atlas, tool_get_templates]
    )

    sys = SystemMessage(
        content=(
            "You are a suggestion template agent. "
            "Based on the 'outputInstruction' and context, choose which template ('info', 'action', or 'choice') best fits. "
            "CRITICAL: First call get_templates to get the template structure, then call get_site_atlas to get DOM selectors. "
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


def choice_manager_agent_node(context: dict, suggestion: dict, api_url: str, timeout: float) -> dict:
    """Manage multi-step flows for choice suggestions."""
    if suggestion.get("type") != "choice":
        return {"final": True, "suggestion_data": suggestion}

    user_choices = context.get("userChoices") or {}
    if not user_choices:
        logger.debug(
            "Choice manager awaiting user input site=%s",
            context.get("siteId"),
        )
        return {"final": False, "suggestion_data": suggestion}

    step = suggestion.get("meta", {}).get("step", 1)
    if step >= 2:
        logger.info(
            "Choice manager finalizing suggestion site=%s step=%s",
            context.get("siteId"),
            step,
        )
        return {"final": True, "suggestion_data": suggestion}

    logger.debug(
        "Choice manager continuing flow site=%s step=%s",
        context.get("siteId"),
        step,
    )
    return {"final": False, "suggestion_data": suggestion}
