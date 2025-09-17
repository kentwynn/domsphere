"""Helper utilities for the rule agent."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES, RuleTrigger, TriggerCondition


def fetch_sitemap(site_id: str, api_url: str, timeout: float) -> List[Dict[str, Any]]:
    """Return the sitemap pages for the given site."""
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{api_url}/site/map", params={"siteId": site_id})
        response.raise_for_status()
        data = response.json() or {}
        return data.get("pages", [])


def fetch_site_atlas(site_id: str, url: str, api_url: str, timeout: float) -> Dict[str, Any]:
    """Return the atlas snapshot for the provided site and url."""
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{api_url}/site/atlas", params={"siteId": site_id, "url": url}
        )
        response.raise_for_status()
        return response.json() or {}


def build_output_schema() -> Dict[str, Any]:
    """Construct a schema summary from the RuleTrigger contracts."""
    try:
        trigger_schema = RuleTrigger.model_json_schema()
        condition_schema = TriggerCondition.model_json_schema()

        trigger_props = trigger_schema.get("properties", {})
        condition_props = condition_schema.get("properties", {})

        return {
            "trigger_fields": {
                field: {
                    "type": info.get("type"),
                    "description": info.get("description"),
                    "enum": info.get("enum"),
                    "default": info.get("default"),
                }
                for field, info in trigger_props.items()
            },
            "condition_fields": {
                field: {
                    "type": info.get("type"),
                    "description": info.get("description"),
                    "enum": info.get("enum"),
                    "default": info.get("default"),
                }
                for field, info in condition_props.items()
            },
            "trigger_required": trigger_schema.get("required", []),
            "condition_required": condition_schema.get("required", []),
            "available_event_types": DOM_EVENT_TYPES,
            "available_operators": CONDITION_OPS,
        }
    except Exception:
        return {
            "trigger_fields": {
                "eventType": {
                    "type": "string",
                    "description": "DOM event type",
                    "enum": DOM_EVENT_TYPES,
                },
                "when": {"type": "array", "description": "Array of conditions"},
            },
            "condition_fields": {
                "field": {"type": "string", "description": "Telemetry field path"},
                "op": {
                    "type": "string",
                    "description": "Comparison operator",
                    "enum": CONDITION_OPS,
                },
                "value": {"type": "any", "description": "Value to compare against"},
            },
            "available_event_types": DOM_EVENT_TYPES,
            "available_operators": CONDITION_OPS,
        }
