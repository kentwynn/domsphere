"""RuleAgent implementation organized alongside other agents."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES

from helper.rule import build_output_schema, fetch_site_atlas, fetch_sitemap
from .rule_llm import RuleLLMToolkit, run_llm_generation


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
        return run_llm_generation(site_id, rule_instruction, self._create_toolkit())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_triggers(self, site_id: str, rule_instruction: str) -> List[Dict[str, Any]]:
        """Generate triggers for a rule instruction using LLM/tool-calling."""
        trig = self._llm_generate(site_id, rule_instruction)

        if isinstance(trig, list) and trig:
            validated_triggers: List[Dict[str, Any]] = []
            for item in trig:
                try:
                    if not isinstance(item, dict):
                        continue
                    if "eventType" not in item or "when" not in item:
                        continue
                    if item["eventType"] not in DOM_EVENT_TYPES:
                        continue

                    when_conditions = item.get("when", [])
                    if not isinstance(when_conditions, list):
                        continue

                    valid_conditions = []
                    for cond in when_conditions:
                        if (
                            isinstance(cond, dict)
                            and "field" in cond
                            and "op" in cond
                            and "value" in cond
                            and cond["op"] in CONDITION_OPS
                        ):
                            valid_conditions.append(cond)

                    if valid_conditions:
                        validated_triggers.append(
                            {"eventType": item["eventType"], "when": valid_conditions}
                        )
                except Exception:
                    continue
            return validated_triggers
        return []
