"""Suggestion templates used by suggestion workflows."""

from typing import Any, Dict

INFO_TEMPLATE = {
    "type": "info",
    "id": "<fill-in-id>",
    "title": "<fill-in-title>",
    "description": "<fill-in-description>",
    "meta": {
        "source": "<fill-in-source>",
        "step": "<fill-in-step>",
    },
}

ACTION_TEMPLATE = {
    "type": "recommendation",
    "id": "<fill-in-id>",
    "title": "<fill-in-title>",
    "description": "<fill-in-description>",
    "primaryCta": {
        "label": "<fill-in-label>",
        "kind": "<fill-in-kind>",
        "payload": "<fill-in-payload>",
        "nextStep": "<fill-in-nextStep>",
    },
    "primaryActions": "<fill-in-primaryActions>",
    "secondaryCta": {
        "label": "<fill-in-secondary-label>",
        "kind": "<fill-in-secondary-kind>",
        "nextClose": "<fill-in-nextClose>",
    },
    "meta": {
        "source": "<fill-in-source>",
        "step": "<fill-in-step>",
    },
}

CHOICE_TEMPLATE = {
    "type": "choice",
    "id": "<fill-in-id>",
    "title": "<fill-in-title>",
    "description": "<fill-in-description>",
    "actions": [
        {
            "label": "<fill-in-label>",
            "kind": "choose",
            "payload": {"name": "<fill-in-name>", "value": "<fill-in-value>"},
        }
    ],
    "meta": {
        "source": "<fill-in-source>",
        "step": "<fill-in-step>",
    },
}


def get_templates() -> Dict[str, Dict[str, Any]]:
    """Return available templates keyed by their type."""
    return {
        "info": INFO_TEMPLATE,
        "action": ACTION_TEMPLATE,
        "choice": CHOICE_TEMPLATE,
    }
