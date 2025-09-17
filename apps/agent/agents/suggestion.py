"""SuggestionAgent implementation orchestrating the suggestion workflow."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from contracts.agent_api import AgentSuggestNextRequest
from contracts.suggestion import Suggestion

from helper.suggestion import normalize_url
from agents.suggestion_nodes import (
    choice_manager_agent_node,
    template_agent_node,
    validator_agent_node,
)


class SuggestionAgent:
    """Unified suggestion agent using template-driven, multi-agent orchestration."""

    def __init__(self, api_url: Optional[str] = None) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))

    def _fetch_rule_info(self, site_id: str, rule_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.http_timeout) as client:
            response = client.get(f"{self.api_url}/rule/{rule_id}", params={"siteId": site_id})
            response.raise_for_status()
            return response.json() or {}

    def _build_context(self, request: AgentSuggestNextRequest) -> Dict[str, Any]:
        normalized_url = normalize_url(request.url)
        context: Dict[str, Any] = {
            "url": normalized_url,
            "userChoices": request.input or {},
            "siteId": request.siteId,
        }
        rule_info = self._fetch_rule_info(request.siteId, request.ruleId)
        context["outputInstruction"] = rule_info.get("rule", {}).get("outputInstruction", "")
        return context

    def generate_suggestions(self, request: AgentSuggestNextRequest) -> List[Suggestion]:
        context = self._build_context(request)
        node_result = template_agent_node(context, self.api_url, self.http_timeout)
        template_type = node_result.get("template_type")
        suggestion_data = node_result.get("suggestion_data")
        if not suggestion_data:
            return []

        if template_type == "choice":
            choice_result = choice_manager_agent_node(
                context, suggestion_data, self.api_url, self.http_timeout
            )
            if not choice_result.get("final"):
                return validator_agent_node([choice_result["suggestion_data"]], context)
            return validator_agent_node([choice_result["suggestion_data"]], context)

        return validator_agent_node([suggestion_data], context)

    def _parse_suggestions(self, suggestions_data: List[dict], context: dict) -> List[Suggestion]:
        return validator_agent_node(suggestions_data, context)
