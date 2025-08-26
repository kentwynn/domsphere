"""
Shared contracts (models) for API and Agent.

Import examples:
    from contracts.sdk_api import SuggestRequestV1, SuggestResponseV1
    from contracts.agent_api import AgentSuggestionRequestV1
    from contracts.version import CONTRACT_VERSION
"""
from .version import CONTRACT_VERSION

__all__ = ["CONTRACT_VERSION"]
