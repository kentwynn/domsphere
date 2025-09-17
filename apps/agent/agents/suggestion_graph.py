"""LangGraph wiring for the suggestion agent."""

from __future__ import annotations

from typing import Any, Dict

from langgraph.graph import StateGraph

from agents.suggestion_nodes import (
    choice_manager_agent_node,
    planner_agent_node,
    template_agent_node,
)
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


def build_suggestion_graph(api_url: str, timeout: float) -> StateGraph:
    """Build a LangGraph multi-agent graph for the suggestion agent."""
    logger.debug(
        "Building suggestion graph api_url=%s timeout=%s",
        api_url,
        timeout,
    )

    class State:
        def __init__(
            self,
            context: Dict[str, Any],
            suggestion_data: Dict[str, Any] | None = None,
            template_type: str | None = None,
            intermediate: bool = False,
            suggestions: list | None = None,
        ) -> None:
            self.context = context
            self.suggestion_data = suggestion_data
            self.template_type = template_type
            self.intermediate = intermediate
            self.suggestions = suggestions or []

        def as_dict(self) -> Dict[str, Any]:
            return {
                "context": self.context,
                "suggestion_data": self.suggestion_data,
                "template_type": self.template_type,
                "intermediate": self.intermediate,
                "suggestions": self.suggestions,
            }

    def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
        context = state["context"]
        logger.debug(
            "Suggestion graph planner node site=%s",
            context.get("siteId"),
        )
        planner_result = planner_agent_node(context, api_url, timeout)
        template_type = planner_result.get("template_type", "action")
        logger.info(
            "Suggestion graph planner chose template=%s site=%s",
            template_type,
            context.get("siteId"),
        )
        return {**state, "template_type": template_type}

    def template_node(state: Dict[str, Any]) -> Dict[str, Any]:
        context = state["context"]
        template_type = state.get("template_type")
        logger.debug(
            "Suggestion graph template node running site=%s template_hint=%s",
            context.get("siteId"),
            template_type,
        )
        node_result = template_agent_node(context, api_url, timeout)
        suggestion_data = node_result.get("suggestion_data")
        intermediate = node_result.get("intermediate", False)
        ttype = template_type or node_result.get("template_type")
        logger.info(
            "Suggestion graph template node produced data=%s intermediate=%s",
            bool(suggestion_data),
            intermediate,
        )
        return {
            **state,
            "suggestion_data": suggestion_data,
            "template_type": ttype,
            "intermediate": intermediate,
        }

    def choice_manager_node(state: Dict[str, Any]) -> Dict[str, Any]:
        context = state["context"]
        suggestion_data = state.get("suggestion_data")
        logger.debug(
            "Suggestion graph choice manager evaluating site=%s",
            context.get("siteId"),
        )
        result = choice_manager_agent_node(context, suggestion_data, api_url, timeout)
        logger.info(
            "Suggestion graph choice manager final=%s",
            result.get("final", True),
        )
        return {
            **state,
            "suggestion_data": result.get("suggestion_data"),
            "intermediate": not result.get("final", True),
        }

    def validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
        suggestion_data = state.get("suggestion_data")
        logger.debug(
            "Suggestion graph validator consolidating suggestions present=%s",
            bool(suggestion_data),
        )
        suggestions = [suggestion_data] if suggestion_data else []
        logger.info(
            "Suggestion graph validator emitting %s suggestion(s)",
            len(suggestions),
        )
        return {**state, "suggestions": suggestions}

    graph = StateGraph()
    graph.add_node("planner", planner_node)
    graph.add_node("template", template_node)
    graph.add_node("choice_manager", choice_manager_node)
    graph.add_node("validator", validator_node)


    graph.add_edge("planner", "template")

    def template_router(state: Dict[str, Any]) -> str:
        ttype = state.get("template_type")
        if ttype == "choice":
            return "choice_manager"
        return "validator"

    graph.add_conditional_edge("template", template_router)

    def choice_manager_router(state: Dict[str, Any]) -> str:
        return "validator"

    graph.add_conditional_edge("choice_manager", choice_manager_router)

    graph.set_entry_point("planner")
    graph.set_finish_point("validator")
    return graph
