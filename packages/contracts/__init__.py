"""
Shared contracts for API and Agent.

Usage:
    from contracts.sdk_api import RuleCheckRequest, SuggestGetRequest
    from contracts.agent_api import AgentStepCheckRequest, AgentSuggestionRequest
    from contracts.version import CONTRACT_VERSION
"""
from .version import CONTRACT_VERSION

__all__ = ["CONTRACT_VERSION"]
