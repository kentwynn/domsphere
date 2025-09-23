"""Helper utilities for suggestion agent workflows."""

from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from contracts.client_api import SiteAtlasResponse, SiteInfoResponse


def normalize_url(url: str) -> str:
    """Normalize URLs by stripping trailing slashes when provided as strings."""
    return url.rstrip("/") if isinstance(url, str) else url


def get_site_info(site_id: str, url: str, api_url: str, timeout: float) -> SiteInfoResponse:
    """Fetch site info for the given site_id and url."""
    normalized_url = normalize_url(url)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{api_url}/site/info", params={"siteId": site_id, "url": normalized_url}
        )
        response.raise_for_status()
        data: Any = response.json() or {}
        if not data:
            return SiteInfoResponse(siteId=site_id, url=normalized_url, meta=None, normalized=None)
        return SiteInfoResponse(**data)


def get_site_atlas(site_id: str, url: str, api_url: str, timeout: float) -> SiteAtlasResponse:
    """Fetch site atlas for the given site_id and url."""
    normalized_url = normalize_url(url)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{api_url}/site/atlas", params={"siteId": site_id, "url": normalized_url}
        )
        response.raise_for_status()
        data: Any = response.json() or {}
        if not data:
            return SiteAtlasResponse(siteId=site_id, url=normalized_url, atlas=None, queuedPlanRebuild=None)
        return SiteAtlasResponse(**data)


def parse_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object from text, returning an empty dict on failure."""
    if not text:
        return {}

    cleaned = text.strip()
    extraction_methods = [
        lambda t: t[t.find("{"):t.rfind("}") + 1] if "{" in t and "}" in t else "",
        lambda t: t,
        _extract_balanced_json,
    ]

    for method in extraction_methods:
        try:
            json_text = method(cleaned)
            if json_text:
                json_text = (
                    json_text.replace(" ,", ",")
                    .replace(", }", "}")
                    .replace("{ ", "{")
                    .replace(" }", "}")
                )
                obj = json.loads(json_text)
                if isinstance(obj, dict):
                    return obj
        except Exception:
            continue

    return {}


def _extract_balanced_json(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return ""

    brace_count = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                return text[start:index + 1]
    return ""
