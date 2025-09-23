"""Helper utilities for the rule agent."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from contracts.common import CONDITION_OPS, DOM_EVENT_TYPES, RuleTrigger, TriggerCondition
from core.logging import get_agent_logger


logger = get_agent_logger(__name__)


def generate_sitemap_query(
    instruction: str,
    *,
    api_key: Optional[str],
    model: Optional[str] = None,
) -> str:
    """Use an LLM to derive a single sitemap search query."""
    text = (instruction or "").strip()
    if not text:
        logger.info("Sitemap query planner received empty instruction; returning blank query")
        return ""

    if not api_key:
        logger.warning("Sitemap query planner missing OpenAI API key; returning blank query")
        return ""

    try:  # Lazy import to keep optional dependency
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
    except Exception:
        logger.exception("Sitemap query planner cannot import LangChain dependencies")
        return ""

    model_name = model or os.getenv("OPENAI_MODEL", "gpt-5-nano")

    llm = ChatOpenAI(api_key=api_key, model=model_name, temperature=0)
    messages = [
        SystemMessage(
            content=(
                "You extract the most relevant sitemap keywords for the rule instruction."
                "Return a single lowercase string with 1-3 short keywords separated by spaces."
                "Focus on concrete page or feature names (e.g. 'cart', 'checkout cart')."
                "Do not include numbers, filler words, or explanations."
            )
        ),
        HumanMessage(
            content=json.dumps(
                {
                    "instruction": text,
                }
            )
        ),
    ]

    try:
        ai = llm.invoke(messages)
        content = getattr(ai, "content", "")
        if isinstance(content, str):
            raw = content.strip()
            cleaned_tokens: List[str] = []
            if raw:
                tokens = re.findall(r"[a-z0-9]+", raw.lower())
                for token in tokens:
                    if token in _STOPWORDS:
                        continue
                    if token.isdigit():
                        continue
                    if len(token) <= 2:
                        continue
                    if token in cleaned_tokens:
                        continue
                    cleaned_tokens.append(token)
                    if len(cleaned_tokens) >= 3:
                        break
            if cleaned_tokens:
                result = " ".join(cleaned_tokens)
                logger.info(
                    "Sitemap query planner returning query='%s' (raw='%s') for instruction preview='%s'",
                    result,
                    raw[:80],
                    text[:80],
                )
                return result
            if raw:
                logger.info(
                    "Sitemap query planner using raw query='%s' for instruction preview='%s'",
                    raw,
                    text[:80],
                )
                return raw
        logger.warning(
            "Sitemap query planner received empty content from LLM instruction preview='%s'",
            text[:80],
        )
    except Exception:
        logger.exception("Sitemap query planner failed for instruction preview='%s'", text[:80])
        return ""

    logger.info(
        "Sitemap query planner produced no query for instruction preview='%s'", text[:80]
    )
    return ""


def search_sitemap(site_id: str, query: str, api_url: str, timeout: float) -> List[Dict[str, Any]]:
    """Return top matching sitemap entries for the supplied query."""
    query = (query or "").strip()
    if not query:
        return []
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{api_url}/site/map/search", params={"siteId": site_id, "query": query}
        )
        response.raise_for_status()
        data = response.json() or {}
        results = data.get("results")
        if isinstance(results, list):
            return results
        return []


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
_STOPWORDS = {
    "a",
    "an",
    "and",
    "be",
    "for",
    "from",
    "in",
    "is",
    "it",
    "more",
    "of",
    "on",
    "or",
    "than",
    "the",
    "to",
    "user",
    "when",
    "with",
    "items",
    "multiple",
    "quantity",
    "then",
    "should",
}
