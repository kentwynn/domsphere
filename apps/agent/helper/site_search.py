"""Shared helpers for generating and executing sitemap searches."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx

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

    try:  # Lazy import to keep optional dependency optional
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
    except Exception:
        logger.exception("Sitemap query planner cannot import LangChain dependencies")
        return ""

    model_name = model or os.getenv("OPENAI_MODEL", "gpt-5-nano")

    llm = ChatOpenAI(api_key=api_key, model=model_name, temperature=0)
    messages = [
        SystemMessage(
            content=(
                "You extract the most relevant sitemap keywords for the instruction provided. "
                "Return exactly one lowercase string containing 1-3 short keywords separated by single spaces. "
                "Only include concrete page or feature names (e.g. 'cart', 'checkout cart', 'checkout confirmation'). "
                "Do not include filler words, numbers, or explanations. Respond with keywords only."
            )
        ),
        HumanMessage(content=json.dumps({"instruction": text})),
    ]

    try:
        ai = llm.invoke(messages)
        content = getattr(ai, "content", "")
        if isinstance(content, str):
            raw = content.strip()
            if raw:
                normalized_tokens = []
                seen = set()
                for token in raw.lower().split():
                    if not token or token in seen:
                        continue
                    seen.add(token)
                    normalized_tokens.append(token)
                    if len(normalized_tokens) >= 3:
                        break
                if normalized_tokens:
                    result = " ".join(normalized_tokens)
                    logger.info(
                        "Sitemap query planner returning query='%s' (raw='%s') for instruction preview='%s'",
                        result,
                        raw[:80],
                        text[:80],
                    )
                    return result
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
