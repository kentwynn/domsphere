"""LangGraph wiring for the rule agent."""

from __future__ import annotations

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph

from .rule_llm import RuleLLMToolkit
from .rule_nodes import rule_generation_node, rule_validation_node


def build_rule_graph(toolkit_factory: Callable[[], RuleLLMToolkit]) -> StateGraph:
    """Build a simple graph to run the LLM generation followed by validation."""

    def generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
        toolkit = toolkit_factory()
        result = rule_generation_node(state["context"], toolkit)
        return {**state, "triggers": result.get("triggers", [])}

    def validation_node(state: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = rule_validation_node(state.get("triggers", []) or [])
        return {**state, "triggers": cleaned}

    graph = StateGraph(dict)
    graph.add_node("generate", generation_node)
    graph.add_node("validate", validation_node)
    graph.add_edge("generate", "validate")
    graph.set_entry_point("generate")
    graph.set_finish_point("validate")
    return graph
