"""SuggestionAgent implementation orchestrating the suggestion workflow."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from contracts.agent_api import AgentSuggestNextRequest
from contracts.suggestion import Suggestion

from helper.suggestion import get_site_atlas, get_site_info, normalize_url
from helper.site_search import generate_sitemap_query, search_sitemap
from agents.suggestion_graph import build_suggestion_graph
from agents.suggestion_llm import SuggestionLLMToolkit
from templates.suggestion import get_templates
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


class SuggestionAgent:
    """Unified suggestion agent using template-driven, multi-agent orchestration."""

    def __init__(self, api_url: Optional[str] = None) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")

        raw_model = os.getenv("LLM_MODEL")
        self.llm_model = (raw_model.strip() if isinstance(raw_model, str) else None) or "gpt-4.1-mini"

        raw_embedding_model = os.getenv("LLM_EMBEDDING_MODEL")
        self.llm_embedding_model = (
            raw_embedding_model.strip()
            if isinstance(raw_embedding_model, str) and raw_embedding_model.strip()
            else None
        )

        raw_key = os.getenv("LLM_API_KEY")
        self.llm_api_key = (
            raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        )

        raw_base_url = os.getenv("LLM_BASE_URL")
        if isinstance(raw_base_url, str):
            raw_base_url = raw_base_url.strip()
        self.llm_base_url = raw_base_url.rstrip("/") if raw_base_url else None

        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))
        logger.debug(
            "SuggestionAgent initialized api_url=%s llm_model=%s llm_base_url=%s http_timeout=%s llm_timeout=%s",
            self.api_url,
            self.llm_model,
            self.llm_base_url,
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
        graph_result = self._run_suggestion_graph(request, context)

        if not isinstance(graph_result, dict):
            logger.warning(
                "Suggestion graph returned empty state site=%s rule=%s",
                request.siteId,
                request.ruleId,
            )
            return []

        suggestions = graph_result.get("suggestions") if isinstance(graph_result, dict) else None
        if not isinstance(suggestions, list) or not suggestions:
            logger.warning(
                "Suggestion graph produced no suggestions site=%s rule=%s",
                request.siteId,
                request.ruleId,
            )
            return []

        logger.info(
            "Suggestion graph generated %s suggestion(s) site=%s rule=%s",
            len(suggestions),
            request.siteId,
            request.ruleId,
        )
        return suggestions

    def _run_suggestion_graph(
        self,
        request: AgentSuggestNextRequest,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            request_meta = {
                "siteId": request.siteId,
                "ruleId": request.ruleId,
                "url": request.url,
                "input": request.input or {},
            }
            graph = build_suggestion_graph(self._create_toolkit, request_meta)
            app = graph.compile()
            state = {"context": context, "request": request_meta}
            result = app.invoke(state)
            if not isinstance(result, dict):
                logger.warning(
                    "Suggestion graph returned non-dict state site=%s",
                    context.get("siteId"),
                )
                return {}
            return result
        except Exception:
            logger.exception(
                "Suggestion graph invocation failed site=%s",
                context.get("siteId"),
            )
            raise

    def _create_toolkit(self) -> SuggestionLLMToolkit:
        return SuggestionLLMToolkit(
            plan_sitemap_query=self.tool_plan_sitemap_query,
            search_sitemap=self.tool_search_sitemap,
            get_site_info=self.tool_get_site_info,
            get_site_atlas=self.tool_get_site_atlas,
            get_templates=self.tool_get_templates,
            api_key=self.llm_api_key,
            model_name=self.llm_model,
            base_url=self.llm_base_url,
            timeout=self.http_timeout,
        )

    def tool_plan_sitemap_query(self, payload: str) -> str:
        return generate_sitemap_query(
            payload,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.llm_model,
        )

    def tool_search_sitemap(self, site_id: str, query: str) -> List[Dict[str, Any]]:
        return search_sitemap(site_id, query, self.api_url, self.http_timeout)

    def tool_get_site_info(self, site_id: str, url: str) -> Any:
        return get_site_info(site_id, url, self.api_url, self.http_timeout)

    def tool_get_site_atlas(self, site_id: str, url: str) -> Any:
        return get_site_atlas(site_id, url, self.api_url, self.http_timeout)

    def tool_get_templates(self) -> Dict[str, Dict[str, Any]]:
        return get_templates()
