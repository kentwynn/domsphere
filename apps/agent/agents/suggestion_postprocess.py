"""Suggestion post-processing utilities shared by the agent and graph."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Optional


def _extract_step(suggestion: Optional[Dict[str, Any]]) -> int:
    if not isinstance(suggestion, dict):
        return 1
    meta = suggestion.get("meta") or {}
    raw_step = meta.get("step", 1)
    try:
        return int(raw_step)
    except (TypeError, ValueError):
        return 1


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


def normalize_suggestion(suggestion: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure the suggestion structure is consistent for downstream consumers."""

    suggestion = deepcopy(suggestion)
    suggestion.setdefault("type", "recommendation")

    primary_cta = suggestion.get("primaryCta")
    if isinstance(primary_cta, dict):
        payload = primary_cta.get("payload")
        if payload in ("", None):
            primary_cta.pop("payload", None)
        elif not isinstance(payload, dict):
            primary_cta["payload"] = {"value": payload}
        if "nextStep" in primary_cta:
            primary_cta.pop("nextStep", None)

    for key, default_prefix in (
        ("primaryActions", "Action"),
        ("secondaryActions", "Secondary"),
        ("links", "Link"),
        ("actions", "Action"),
    ):
        value = suggestion.get(key)
        if isinstance(value, list):
            suggestion[key] = [
                _normalize_action(dict(item), default_prefix)
                if isinstance(item, dict)
                else item
                for item in value
            ]

    return suggestion


def fallback_info_suggestion(
    request_meta: Dict[str, Any],
    context: Dict[str, Any],
    get_templates: Callable[[], Dict[str, Dict[str, Any]]],
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
    rule_id = request_meta.get("ruleId", "unknown")
    info_template["id"] = suggestion_id or f"fallback-info-{rule_id}"
    info_template["title"] = title or instruction[:120] or "Suggestion Unavailable"
    info_template["description"] = description or instruction

    meta = info_template.get("meta") or {}
    meta["source"] = source
    meta["step"] = str(step)
    info_template["meta"] = meta

    return info_template


def choice_acknowledgement(
    request_meta: Dict[str, Any],
    context: Dict[str, Any],
    get_templates: Callable[[], Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    user_choices = context.get("userChoices") or {}
    summary = ", ".join(f"{key} = {value}" for key, value in user_choices.items())
    if not summary:
        summary = "your selection"

    instruction = context.get("outputInstruction") or "Selection received"
    description = f"We'll tailor the next steps using {summary}."

    return fallback_info_suggestion(
        request_meta,
        context,
        get_templates,
        title=instruction[:120] or "Selection received",
        description=description,
        source="choice_ack",
        step=2,
        suggestion_id=f"choice-ack-{request_meta.get('ruleId', 'unknown')}",
    )


def finalize_suggestion_state(
    state: Dict[str, Any],
    request_meta: Dict[str, Any],
    get_templates: Callable[[], Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    """Apply fallback, choice handling, and normalization to the graph state."""

    context = state.get("context") or {}
    suggestion_data = state.get("suggestion_data")
    template_type = state.get("template_type") or "info"
    choice_result = state.get("choice_result") if isinstance(state, dict) else None
    choice_result = choice_result if isinstance(choice_result, dict) else {}

    def _wrap(result: Dict[str, Any], final_type: str) -> Dict[str, Any]:
        normalized = normalize_suggestion(result)
        return {
            **state,
            "suggestion_data": normalized,
            "template_type": final_type,
            "suggestions": [normalized],
        }

    if not isinstance(suggestion_data, dict):
        fallback = fallback_info_suggestion(request_meta, context, get_templates)
        return _wrap(fallback, "info")

    if choice_result:
        final_template_type = choice_result.get("template_type") or template_type
        final_raw = choice_result.get("suggestion_data") or suggestion_data
        final_choice = final_raw if isinstance(final_raw, dict) else None

        if not final_choice:
            ack = choice_acknowledgement(request_meta, context, get_templates)
            return _wrap(ack, "info")

        if (
            final_template_type == "choice"
            and context.get("userChoices")
            and choice_result.get("exhausted")
        ):
            ack = choice_acknowledgement(request_meta, context, get_templates)
            return _wrap(ack, "info")

        if (
            final_template_type == "choice"
            and context.get("userChoices")
            and _extract_step(final_choice) <= 1
        ):
            final_choice.setdefault("meta", {})["step"] = "2"

        return _wrap(final_choice, final_template_type)

    return _wrap(suggestion_data, template_type)
