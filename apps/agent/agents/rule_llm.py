"""LLM generation utilities for the rule agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES
from helper.suggestion import parse_json_object
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


@dataclass
class RuleLLMToolkit:
    """Dependencies required for LLM-based trigger generation."""

    get_output_schema: Callable[[], Dict[str, Any]]
    plan_sitemap_query: Callable[[str], str]
    search_sitemap: Callable[[str, str], List[Dict[str, Any]]]
    get_site_atlas: Callable[[str, str], Dict[str, Any]]
    api_key: Optional[str]
    model_name: str


def run_llm_generation(
    site_id: str,
    rule_instruction: str,
    toolkit: RuleLLMToolkit,
) -> Optional[List[Dict[str, Any]]]:
    """Invoke the LLM toolchain to generate triggers."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.tools import tool
        from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
    except Exception:
        logger.warning("LangChain not available for rule generation site=%s", site_id)
        return None

    if not toolkit.api_key:
        logger.warning("Missing OpenAI API key for rule generation site=%s", site_id)
        return None

    @tool("get_output_schema", return_direct=False)
    def tool_get_output_schema() -> Dict[str, Any]:  # type: ignore[override]
        """Return the contract schema reference for triggers and conditions."""
        return toolkit.get_output_schema()

    @tool("plan_sitemap_query", return_direct=False)
    def tool_plan_sitemap_query(ruleInstruction: str) -> str:  # type: ignore[override]
        """Suggest a focused sitemap search query derived from the rule instruction."""
        return toolkit.plan_sitemap_query(ruleInstruction)

    @tool("search_sitemap", return_direct=False)
    def tool_search_sitemap(siteId: str, query: str) -> List[Dict[str, Any]]:  # type: ignore[override]
        """Search the site's sitemap for pages relevant to the query."""
        return toolkit.search_sitemap(siteId, query)

    @tool("get_site_atlas", return_direct=False)
    def tool_get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
        """Fetch DOM atlas selectors for the given site URL."""
        return toolkit.get_site_atlas(siteId, url)

    llm = ChatOpenAI(api_key=toolkit.api_key, model=toolkit.model_name, temperature=0)
    llm = llm.bind_tools(
        [
            tool_get_output_schema,
            tool_plan_sitemap_query,
            tool_search_sitemap,
            tool_get_site_atlas,
        ]
    )

    sys = SystemMessage(
        content=(
            "Generate rule triggers using real DOM data and schema-defined patterns.\n\n"
            "PROCESS:\n"
            "1. get_output_schema → understand exact trigger interface\n"
            "2. plan_sitemap_query → extract concise search keywords\n"
            "3. search_sitemap → locate the most relevant pages\n"
            "4. get_site_atlas → fetch DOM details for the selected URLs\n"
            "5. Generate triggers using schema fields and real DOM data\n\n"
            "RULES:\n"
            "- Use schema to understand available eventTypes and operators\n"
            "- Use ONLY real IDs/paths from site atlas\n"
            "- Follow schema field requirements exactly\n"
            "- Return: {\"triggers\": [...]}\n\n"
            "FIELD REFERENCE:\n"
            "- Page: telemetry.attributes.path\n"
            "- Element ID: telemetry.attributes.id\n"
            "- Element text: telemetry.elementText\n"
            "- Time on page: telemetry.attributes.timeOnPage\n\n"
            "Think about what conditions are actually needed for the rule. Use minimal, relevant conditions only."
        )
    )

    human = HumanMessage(
        content=json.dumps(
            {
                "siteId": site_id,
                "ruleInstruction": rule_instruction,
                "events": DOM_EVENT_TYPES,
                "ops": CONDITION_OPS,
            }
        )
    )

    logger.info(
        "Running rule LLM generation site=%s model=%s",
        site_id,
        toolkit.model_name,
    )

    messages: List[Any] = [sys, human]
    for _ in range(6):
        ai = llm.invoke(messages)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            data = parse_json_object(getattr(ai, "content", ""))
            triggers = data.get("triggers")
            if isinstance(triggers, list) and all(isinstance(item, dict) for item in triggers):
                logger.info(
                    "Rule LLM generation succeeded site=%s count=%s",
                    site_id,
                    len(triggers),
                )
                return triggers
            logger.warning(
                "Rule LLM generation returned unexpected payload site=%s",
                site_id,
            )
            return []

        messages.append(ai)
        for tc in tool_calls:
            name = tc["name"] if isinstance(tc, dict) else getattr(tc, "name", None)
            args = tc["args"] if isinstance(tc, dict) else getattr(tc, "args", {})
            if isinstance(args, str):
                try:
                    parsed_args = json.loads(args)
                    if isinstance(parsed_args, dict):
                        args = parsed_args
                except Exception:
                    logger.debug("Tool argument parse failed name=%s site=%s", name, site_id)
            try:
                if name == "get_output_schema":
                    result = tool_get_output_schema.invoke(args)
                elif name == "plan_sitemap_query":
                    result = tool_plan_sitemap_query.invoke(args)
                elif name == "search_sitemap":
                    result = tool_search_sitemap.invoke(args)
                elif name == "get_site_atlas":
                    result = tool_get_site_atlas.invoke(args)
                else:
                    result = {"error": f"unknown tool {name}"}
            except Exception as exc:  # noqa: F841 - preserve behaviour
                logger.exception(
                    "Rule LLM tool call failed name=%s site=%s",
                    name,
                    site_id,
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

    logger.warning("Rule LLM generation exhausted attempts site=%s", site_id)
    return []
