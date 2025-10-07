from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException

from contracts.client_api import (
    EmbeddingSearchRequest,
    EmbeddingSearchResponse,
    EmbeddingSearchResult,
)
from core.logging import get_api_logger
from helper.common import (
    AGENT_TIMEOUT,
    AGENT_URL,
    _fwd_headers,
    get_site_embeddings,
    get_site_settings_payload,
    search_site_embeddings,
)

router = APIRouter(prefix="/embedding", tags=["embedding"])

logger = get_api_logger(__name__)

_BLOCKED_RESOURCE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".bmp",
    ".ico",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".m4a",
    ".mov",
    ".avi",
    ".wmv",
    ".css",
    ".js",
}


def _is_allowed_result_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if not path:
        return True
    last_segment = path.rsplit("/", 1)[-1]
    if "." not in last_segment:
        return True
    ext = "." + last_segment.rsplit(".", 1)[-1]
    return ext not in _BLOCKED_RESOURCE_EXTENSIONS


def _call_agent_embedding(
    text: str,
    xcv: Optional[str],
    xrid: Optional[str],
) -> list[float]:
    payload = {"text": text.strip() or "Embedding request with empty query"}
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            response = client.post(
                f"{AGENT_URL}/agent/embedding",
                json=payload,
                headers=_fwd_headers(xcv, xrid),
            )
            response.raise_for_status()
            data = response.json() or {}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "Embedding request failed query_length=%s request_id=%s error=%s",
            len(text or ""),
            xrid,
            exc,
        )
        raise RuntimeError(f"Agent embedding request failed: {exc}") from exc

    vector = data.get("embedding")
    if not isinstance(vector, list):
        raise RuntimeError("Agent embedding response missing 'embedding'")
    return [float(v) for v in vector]


def _pick_first(meta: Dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


@router.post("/search", response_model=EmbeddingSearchResponse)
def embedding_search(
    payload: EmbeddingSearchRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> EmbeddingSearchResponse:
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must be provided")
    if len(query) < 3:
        logger.info(
            "Embedding search query too short site=%s request_id=%s length=%s",
            payload.siteId,
            x_request_id,
            len(query),
        )
        return EmbeddingSearchResponse(siteId=payload.siteId, query=query, results=[])

    settings = get_site_settings_payload(payload.siteId)
    if not settings.get("enableSearch", True):
        logger.info(
            "Embedding search disabled site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return EmbeddingSearchResponse(siteId=payload.siteId, query=query, results=[])

    top_limit_raw = settings.get("topSearchResults", 5)
    try:
        top_limit = int(top_limit_raw)
    except (TypeError, ValueError):
        top_limit = 5
    top_limit = max(1, min(top_limit, 20))

    store = get_site_embeddings(payload.siteId)
    if not store:
        logger.info(
            "Embedding search requested but no embeddings cached site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return EmbeddingSearchResponse(siteId=payload.siteId, query=query, results=[])

    try:
        query_vector = _call_agent_embedding(query, x_contract_version, x_request_id)
    except RuntimeError as exc:
        logger.exception(
            "Failed to embed query site=%s request_id=%s error=%s",
            payload.siteId,
            x_request_id,
            exc,
        )
        raise HTTPException(status_code=502, detail="Failed to generate query embedding") from exc

    requested_limit = payload.limit if isinstance(payload.limit, int) else top_limit
    try:
        requested_limit = int(requested_limit)
    except (TypeError, ValueError):
        requested_limit = top_limit
    requested_limit = max(1, requested_limit)
    limit = min(requested_limit, top_limit)
    search_limit = min(max(limit * 3, limit), 100)

    matches = search_site_embeddings(
        payload.siteId,
        query_vector,
        top_k=search_limit,
        records=store,
    )
    results: list[EmbeddingSearchResult] = []
    for url, score, metadata in matches:
        if not _is_allowed_result_url(url):
            continue
        meta: Dict[str, Any] = {}
        if isinstance(metadata, dict):
            raw_meta = metadata.get("meta")
            if isinstance(raw_meta, dict):
                meta = raw_meta
            else:
                meta = {
                    key: value
                    for key, value in metadata.items()
                    if key not in {"embedding", "text"}
                }
        title = _pick_first(
            meta,
            ("title", "metaTitle", "pageTitle", "ogTitle", "name"),
        ) or url
        description = _pick_first(
            meta,
            (
                "description",
                "metaDescription",
                "ogDescription",
                "summary",
            ),
        )
        results.append(
            EmbeddingSearchResult(
                url=url,
                similarity=score,
                title=title,
                description=description,
                meta=meta or None,
            )
        )
        if len(results) >= limit:
            break

    logger.info(
        "Embedding search returning %s result(s) site=%s request_id=%s",
        len(results),
        payload.siteId,
        x_request_id,
    )
    return EmbeddingSearchResponse(siteId=payload.siteId, query=query, results=results)
