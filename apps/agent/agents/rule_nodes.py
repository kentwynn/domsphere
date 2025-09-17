"""Rule agent node implementations used in the rule generation flow."""

from __future__ import annotations

from typing import Dict, List

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES

from .rule_llm import RuleLLMToolkit, run_llm_generation


def rule_generation_node(context: Dict[str, str], toolkit: RuleLLMToolkit) -> Dict[str, List[Dict[str, object]]]:
    """Invoke the LLM generation step and wrap the raw trigger output."""
    triggers = run_llm_generation(context["siteId"], context["ruleInstruction"], toolkit) or []
    return {"triggers": triggers}


def rule_validation_node(raw_triggers: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Filter triggers so they conform to the RuleTrigger schema expectations."""
    validated: List[Dict[str, object]] = []
    for item in raw_triggers:
        try:
            if not isinstance(item, dict):
                continue
            event_type = item.get("eventType")
            when = item.get("when")
            if event_type not in DOM_EVENT_TYPES or not isinstance(when, list):
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
                continue

            validated.append({"eventType": event_type, "when": conditions})
        except Exception:
            continue
    return validated
