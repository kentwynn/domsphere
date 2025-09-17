"""Template exports for agent workflows."""

from .suggestion import get_templates
from .rule import RULE_GENERATION_TEMPLATE

__all__ = [
    "get_templates",
    "RULE_GENERATION_TEMPLATE",
]
