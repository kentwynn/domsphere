"""Agent implementations exposed by the agent service layer."""

from core.logging import get_agent_logger

from .rule import RuleAgent
from .rule_graph import build_rule_graph
from .rule_nodes import rule_generation_node, rule_validation_node
from .suggestion import SuggestionAgent
from .suggestion_graph import build_suggestion_graph
from .suggestion_nodes import (
    planner_agent_node,
    template_agent_node,
    choice_manager_agent_node,
)

logger = get_agent_logger(__name__)

__all__ = [
    "RuleAgent",
    "build_rule_graph",
    "rule_generation_node",
    "rule_validation_node",
    "SuggestionAgent",
    "build_suggestion_graph",
    "planner_agent_node",
    "template_agent_node",
    "choice_manager_agent_node",
]

logger.debug("Agent package loaded exports=%s", __all__)
