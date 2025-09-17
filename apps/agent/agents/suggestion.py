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

        suggestion_data = self._normalize_suggestion(suggestion_data)

        if template_type == "choice":
            choice_result = choice_manager_agent_node(
                context, suggestion_data, self.api_url, self.http_timeout
            )
            return [choice_result.get("suggestion_data")]

        return [suggestion_data]

    def _parse_suggestions(self, suggestions_data: List[dict], context: dict) -> List[Suggestion]:
        return suggestions_data

    def _normalize_suggestion(self, suggestion: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure generated suggestion conforms to expected action shape."""

        def _normalize_action(action: Dict[str, Any], default_prefix: str) -> Dict[str, Any]:
            if "operation" in action and "kind" not in action:
                action["kind"] = action.pop("operation")
            if "type" in action and "kind" not in action:
                action["kind"] = action.pop("type")

            payload = action.get("payload") or {}
            selector = action.get("selector")
            value = action.get("value")
            if selector is not None:
                payload.setdefault("selector", selector)
            if value is not None:
                payload.setdefault("value", value)
            if payload:
                action["payload"] = payload

            for key in ("selector", "value"):
                if key in action:
                    del action[key]

            if not action.get("label"):
                kind = action.get("kind", default_prefix)
                label = kind.replace("_", " ").title()
                action["label"] = label

            return action

        suggestion.setdefault("type", "recommendation")

        primary_cta = suggestion.get("primaryCta")
        if isinstance(primary_cta, dict):
            payload = primary_cta.get("payload")
            if payload in ("", None):
                primary_cta.pop("payload", None)
            elif not isinstance(payload, dict):
                primary_cta["payload"] = {"value": payload}

            # Remove nextStep when we do not orchestrate multi-step flows
            if "nextStep" in primary_cta:
                primary_cta.pop("nextStep", None)

        primary_actions = suggestion.get("primaryActions")
        if isinstance(primary_actions, list):
            suggestion["primaryActions"] = [
                _normalize_action(dict(action), "Action")
                if isinstance(action, dict) else action
                for action in primary_actions
            ]

        secondary_actions = suggestion.get("secondaryActions")
        if isinstance(secondary_actions, list):
            suggestion["secondaryActions"] = [
                _normalize_action(dict(action), "Secondary")
                if isinstance(action, dict) else action
                for action in secondary_actions
            ]

        links = suggestion.get("links")
        if isinstance(links, list):
            suggestion["links"] = [
                _normalize_action(dict(link), "Link")
                if isinstance(link, dict) else link
                for link in links
            ]

        actions = suggestion.get("actions")
        if isinstance(actions, list):
            suggestion["actions"] = [
                _normalize_action(dict(action), "Action")
                if isinstance(action, dict) else action
                for action in actions
            ]

        return suggestion
