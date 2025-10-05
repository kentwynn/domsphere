"""LLM toolkit definitions for the suggestion agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SuggestionLLMToolkit:
    """Container for callable dependencies used by the suggestion LLM flow."""

    plan_sitemap_query: Callable[[str], str]
    search_sitemap: Callable[[str, str], List[Dict[str, Any]]]
    get_site_info: Callable[[str, str], Any]
    get_site_atlas: Callable[[str, str], Any]
    get_templates: Callable[[], Dict[str, Dict[str, Any]]]
    api_key: Optional[str]
    model_name: str
    base_url: Optional[str]
    timeout: float
