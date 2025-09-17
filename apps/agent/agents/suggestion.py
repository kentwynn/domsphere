"""SuggestionAgent implementation orchestrating the suggestion workflow."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, List, Optional

import httpx

from contracts.agent_api import AgentSuggestNextRequest
from contracts.suggestion import Suggestion

from helper.suggestion import normalize_url
from agents.suggestion_nodes import (
    choice_manager_agent_node,
    planner_agent_node,
    template_agent_node,
)
from templates.suggestion import get_templates
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


class SuggestionAgent:
    """Unified suggestion agent using template-driven, multi-agent orchestration."""

    def __init__(self, api_url: Optional[str] = None) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))
        logger.debug(
            "SuggestionAgent initialized api_url=%s http_timeout=%s llm_timeout=%s",
            self.api_url,
            self.http_timeout,
            self.llm_timeout,
        )

    def _fetch_rule_info(self, site_id: str, rule_id: str) -> Dict[str, Any]:
        try:
            logger.debug("Fetching rule info site=%s rule=%s", site_id, rule_id)
            with httpx.Client(timeout=self.http_timeout) as client:
                response = client.get(
                    f"{self.api_url}/rule/{rule_id}", params={"siteId": site_id}
                )
                response.raise_for_status()
                payload = response.json() or {}
                logger.debug("Fetched rule info site=%s rule=%s", site_id, rule_id)
                return payload
        except Exception:
            logger.exception("Failed to fetch rule info site=%s rule=%s", site_id, rule_id)
            raise

    def _build_context(self, request: AgentSuggestNextRequest) -> Dict[str, Any]:
        normalized_url = normalize_url(request.url)
        context: Dict[str, Any] = {
            "url": normalized_url,
            "userChoices": request.input or {},
            "siteId": request.siteId,
        }
        rule_info = self._fetch_rule_info(request.siteId, request.ruleId)
        context["outputInstruction"] = rule_info.get("rule", {}).get("outputInstruction", "")
        logger.debug(
            "Built suggestion context site=%s rule=%s normalized_url=%s choices=%s",
            request.siteId,
            request.ruleId,
            normalized_url,
            bool(context["userChoices"]),
        )
        return context

    def generate_suggestions(self, request: AgentSuggestNextRequest) -> List[Suggestion]:
        logger.info(
            "Generating suggestions site=%s rule=%s", request.siteId, request.ruleId
        )
        context = self._build_context(request)
        planner_result = planner_agent_node(context, self.api_url, self.http_timeout)
        planner_template = planner_result.get("template_type") or "info"
        logger.info(
            "Planner selected template=%s site=%s rule=%s",
            planner_template,
            request.siteId,
            request.ruleId,
        )

        node_result = template_agent_node(context, self.api_url, self.http_timeout)
        template_type = node_result.get("template_type") or planner_template
        suggestion_data = node_result.get("suggestion_data")
        if not suggestion_data:
            logger.warning(
                "Template produced no suggestion data site=%s rule=%s template=%s",
                request.siteId,
                request.ruleId,
                template_type,
            )
            fallback = self._fallback_info_suggestion(request, context)
            logger.info(
                "Returning fallback info suggestion site=%s rule=%s",
                request.siteId,
                request.ruleId,
            )
            return [fallback]

        if template_type == "choice":
            logger.debug(
                "Routing choice manager site=%s rule=%s", request.siteId, request.ruleId
            )
            choice_result = choice_manager_agent_node(
                context, suggestion_data, self.api_url, self.http_timeout
            )
            final_raw = choice_result.get("suggestion_data")
            final_template_type = choice_result.get("template_type") or template_type
            is_final = choice_result.get("final", True)
            final_choice = (
                self._normalize_suggestion(final_raw)
                if isinstance(final_raw, dict)
                else None
            )
            logger.info(
                "Choice suggestion processed site=%s rule=%s final=%s template=%s",
                request.siteId,
                request.ruleId,
                is_final,
                final_template_type,
            )

            if not final_choice:
                ack = self._choice_acknowledgement(request, context)
                logger.info(
                    "Choice fallback generated (empty follow-up) site=%s rule=%s",
                    request.siteId,
                    request.ruleId,
                )
                return [ack]

            if (
                final_template_type == "choice"
                and context.get("userChoices")
                and choice_result.get("exhausted")
            ):
                ack = self._choice_acknowledgement(request, context)
                logger.info(
                    "Choice acknowledgement fallback site=%s rule=%s",
                    request.siteId,
                    request.ruleId,
                )
                return [ack]

            if (
                final_template_type == "choice"
                and context.get("userChoices")
                and self._extract_step(final_choice) <= 1
            ):
                final_choice.setdefault("meta", {})["step"] = "2"

            return [final_choice] if final_choice else []

        suggestion_data = self._normalize_suggestion(suggestion_data)
        logger.info(
            "Generated suggestion site=%s rule=%s template=%s",
            request.siteId,
            request.ruleId,
            template_type or "unknown",
        )
        return [suggestion_data]

    def _fallback_info_suggestion(
        self,
        request: AgentSuggestNextRequest,
        context: Dict[str, Any],
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        source: str = "fallback",
        step: int | str = 1,
        suggestion_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        templates = get_templates()
        info_template = deepcopy(templates.get("info", {}))
        if not info_template:
            info_template = {
                "type": "info",
                "id": "fallback-info",
                "title": "Suggestion Unavailable",
                "description": "We couldn't generate a suggestion right now.",
                "meta": {},
            }

        instruction = context.get("outputInstruction") or "Suggestion Unavailable"
        info_template["id"] = suggestion_id or f"fallback-info-{request.ruleId}"
        info_template["title"] = title or instruction[:120] or "Suggestion Unavailable"
        info_template["description"] = description or instruction

        meta = info_template.get("meta") or {}
        meta["source"] = source
        meta["step"] = str(step)
        info_template["meta"] = meta

        return info_template

    def _choice_acknowledgement(
        self, request: AgentSuggestNextRequest, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        user_choices = context.get("userChoices") or {}
        summary = ", ".join(
            f"{key} = {value}" for key, value in user_choices.items()
        )
        if not summary:
            summary = "your selection"

        instruction = context.get("outputInstruction") or "Selection received"
        description = (
            f"We'll tailor the next steps using {summary}."
        )

        info = self._fallback_info_suggestion(
            request,
            context,
            title=instruction[:120] or "Selection received",
            description=description,
            source="choice_ack",
            step=2,
            suggestion_id=f"choice-ack-{request.ruleId}",
        )
        # Remove any template placeholders that might remain
        info.setdefault("type", "info")
        return info

    def _extract_step(self, suggestion: Optional[Dict[str, Any]]) -> int:
        if not isinstance(suggestion, dict):
            return 1
        meta = suggestion.get("meta") or {}
        raw_step = meta.get("step", 1)
        try:
            return int(raw_step)
        except (TypeError, ValueError):
            return 1

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
