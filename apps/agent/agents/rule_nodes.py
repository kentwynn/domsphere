"""Rule agent node implementations used in the rule generation flow."""

from __future__ import annotations

from typing import Dict, List

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES

from .rule_llm import RuleLLMToolkit, run_llm_generation
from core.logging import get_agent_logger

logger = get_agent_logger(__name__)


def rule_generation_node(context: Dict[str, str], toolkit: RuleLLMToolkit) -> Dict[str, List[Dict[str, object]]]:
    """Invoke the LLM generation step and wrap the raw trigger output."""
    site_id = context.get("siteId")
    logger.debug("rule_generation_node invoked site=%s", site_id)
    triggers = run_llm_generation(context["siteId"], context["ruleInstruction"], toolkit) or []
    logger.info("rule_generation_node produced %s trigger candidate(s) site=%s", len(triggers), site_id)
    return {"triggers": triggers}


def rule_validation_node(raw_triggers: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Filter triggers so they conform to the RuleTrigger schema expectations."""
    logger.debug("rule_validation_node validating %s candidate(s)", len(raw_triggers))
    validated: List[Dict[str, object]] = []
    dropped = 0
    for item in raw_triggers:
        try:
            if not isinstance(item, dict):
                dropped += 1
                continue
            event_type = item.get("eventType")
            when = item.get("when")
            if event_type not in DOM_EVENT_TYPES or not isinstance(when, list):
                dropped += 1
                continue

            conditions: List[Dict[str, object]] = []
            for cond in when:
                if (
                    isinstance(cond, dict)
                    and "field" in cond
                    and "op" in cond
                    and "value" in cond
                    and cond["op"] in CONDITION_OPS
                ):
                    conditions.append(cond)
            if not conditions:
                dropped += 1
                continue

            validated.append({"eventType": event_type, "when": conditions})
        except Exception:
            dropped += 1
            continue
    logger.info(
        "rule_validation_node accepted %s trigger(s) dropped=%s",
        len(validated),
        dropped,
    )
    return validated
