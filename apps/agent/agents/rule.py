"""RuleAgent implementation organized alongside other agents."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


from helper.rule import (
    build_output_schema,
    fetch_site_atlas,
    generate_sitemap_query,
    search_sitemap,
)
from .rule_graph import build_rule_graph
from .rule_llm import RuleLLMToolkit
from .rule_nodes import rule_validation_node
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


class RuleAgent:
    """Single-agent that uses LLM tool-calling to generate rule triggers."""

    def __init__(self, api_url: Optional[str] = None, debug: bool = False) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")

        raw_model = os.getenv("LLM_MODEL")
        self.llm_model = (raw_model.strip() if isinstance(raw_model, str) else None) or "gpt-4.1-mini"

        raw_key = os.getenv("LLM_API_KEY")
        self.llm_api_key = (
            raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        )

        raw_base_url = os.getenv("LLM_BASE_URL")
        if isinstance(raw_base_url, str):
            raw_base_url = raw_base_url.strip()
        self.llm_base_url = raw_base_url.rstrip("/") if raw_base_url else None

        self.debug = debug
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))
        logger.debug(
            "RuleAgent initialized api_url=%s llm_model=%s llm_base_url=%s debug=%s http_timeout=%s llm_timeout=%s",
            self.api_url,
            self.llm_model,
            self.llm_base_url,
            self.debug,
            self.http_timeout,
            self.llm_timeout,
        )

    # ------------------------------------------------------------------
    # Tool adapters
    # ------------------------------------------------------------------
    def tool_search_sitemap(self, site_id: str, query: str) -> List[Dict[str, Any]]:
        return search_sitemap(site_id, query, self.api_url, self.http_timeout)

    def tool_plan_sitemap_query(self, instruction: str) -> str:
        return generate_sitemap_query(
            instruction,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.llm_model,
        )

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        return fetch_site_atlas(site_id, url, self.api_url, self.http_timeout)

    def tool_get_output_schema(self) -> Dict[str, Any]:
        return build_output_schema()

    # ------------------------------------------------------------------
    # LLM integration
    # ------------------------------------------------------------------
    def _create_toolkit(self) -> RuleLLMToolkit:
        return RuleLLMToolkit(
            get_output_schema=self.tool_get_output_schema,
            plan_sitemap_query=self.tool_plan_sitemap_query,
            search_sitemap=self.tool_search_sitemap,
            get_site_atlas=self.tool_get_site_atlas,
            api_key=self.llm_api_key,
            model_name=self.llm_model,
            base_url=self.llm_base_url,
        )

    def _llm_generate(self, site_id: str, rule_instruction: str) -> Optional[List[Dict[str, Any]]]:
        try:
            logger.info("Invoking rule graph site=%s", site_id)
            graph = build_rule_graph(self._create_toolkit)
            app = graph.compile()

            state = {"context": {"siteId": site_id, "ruleInstruction": rule_instruction}}
            result = app.invoke(state)
            triggers = result.get("triggers") if isinstance(result, dict) else None
            count = len(triggers) if isinstance(triggers, list) else 0
            logger.debug("Rule graph returned %s trigger candidate(s) site=%s", count, site_id)
            if isinstance(triggers, list):
                return triggers
            return None
        except Exception:
            logger.exception("Rule graph invocation failed site=%s", site_id)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_triggers(self, site_id: str, rule_instruction: str) -> List[Dict[str, Any]]:
        """Generate triggers for a rule instruction using LLM/tool-calling."""
        logger.info("Generating triggers site=%s", site_id)
        trig = self._llm_generate(site_id, rule_instruction)

        if isinstance(trig, list) and trig:
            validated = rule_validation_node(trig)
            logger.info(
                "Validated %s trigger(s) site=%s",
                len(validated),
                site_id,
            )
            return validated

        logger.warning("No triggers generated site=%s", site_id)
        return []
