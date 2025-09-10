"""
Shared contracts for API and Agent.

Usage:
    from contracts.client_api import RuleCheckRequest, SuggestGetRequest
    from contracts.agent_api import AgentStepCheckRequest, AgentSuggestionRequest
    from contracts.version import CONTRACT_VERSION
"""
from version import CONTRACT_VERSION

__all__ = ["CONTRACT_VERSION"]
