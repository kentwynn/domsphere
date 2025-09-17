"""RuleAgent implementation organized alongside other agents."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES

from helper.rule import build_output_schema, fetch_site_atlas, fetch_sitemap
from .rule_graph import build_rule_graph
from .rule_llm import RuleLLMToolkit
from .rule_nodes import rule_validation_node


class RuleAgent:
    """Single-agent that uses LLM tool-calling to generate rule triggers."""

    def __init__(self, api_url: Optional[str] = None, debug: bool = False) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.debug = debug
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "300"))
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "300"))

    # ------------------------------------------------------------------
    # Tool adapters
    # ------------------------------------------------------------------
    def tool_get_sitemap(self, site_id: str) -> List[Dict[str, Any]]:
        return fetch_sitemap(site_id, self.api_url, self.http_timeout)

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        return fetch_site_atlas(site_id, url, self.api_url, self.http_timeout)

    def tool_get_output_schema(self) -> Dict[str, Any]:
        return build_output_schema()

    # ------------------------------------------------------------------
    # LLM integration
    # ------------------------------------------------------------------
    def _create_toolkit(self) -> RuleLLMToolkit:
        model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano")
        return RuleLLMToolkit(
            get_output_schema=self.tool_get_output_schema,
            get_sitemap=self.tool_get_sitemap,
            get_site_atlas=self.tool_get_site_atlas,
            api_key=self.openai_token,
            model_name=model_name,
        )

    def _llm_generate(self, site_id: str, rule_instruction: str) -> Optional[List[Dict[str, Any]]]:
        graph = build_rule_graph(self._create_toolkit)
        app = graph.compile()

        state = {"context": {"siteId": site_id, "ruleInstruction": rule_instruction}}
        result = app.invoke(state)
        triggers = result.get("triggers") if isinstance(result, dict) else None
        if isinstance(triggers, list):
            return triggers
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_triggers(self, site_id: str, rule_instruction: str) -> List[Dict[str, Any]]:
        """Generate triggers for a rule instruction using LLM/tool-calling."""
        trig = self._llm_generate(site_id, rule_instruction)

        if isinstance(trig, list) and trig:
            return rule_validation_node(trig)
        return []
