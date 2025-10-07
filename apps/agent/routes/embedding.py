"""Embedding route for the agent service."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException

from contracts.agent_api import (
    AgentEmbeddingRequest,
    AgentEmbeddingResponse,
    AgentEmbeddingSearchRequest,
    AgentEmbeddingSearchResponse,
    AgentEmbeddingSearchResult,
)
from core.logging import get_agent_logger


router = APIRouter(prefix="/agent", tags=["embedding"])

logger = get_agent_logger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
API_BASE_URL = (os.getenv("API_BASE_URL") or "http://localhost:4000").rstrip("/")
API_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "300"))


@router.post("/embedding", response_model=AgentEmbeddingResponse)
def create_embedding(
    payload: AgentEmbeddingRequest,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentEmbeddingResponse:
    """Generate an embedding vector for the provided text input using the configured LLM."""

    raw_model = os.getenv("LLM_EMBEDDING_MODEL") or os.getenv("LLM_MODEL")
    model_name = (raw_model.strip() if isinstance(raw_model, str) and raw_model.strip() else None) or DEFAULT_EMBEDDING_MODEL

    raw_key = os.getenv("LLM_API_KEY")
    api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None

    raw_base_url = os.getenv("LLM_BASE_URL")
    base_url = None
    if isinstance(raw_base_url, str):
        raw_base_url = raw_base_url.strip()
        if raw_base_url:
            base_url = raw_base_url.rstrip("/")

    if not base_url and not api_key:
        logger.error(
            "LLM credentials missing while handling embedding request request_id=%s",
            x_request_id,
        )
        raise HTTPException(status_code=500, detail="LLM configuration missing")

    try:
        # Delay import so service can start without optional dependency
        from langchain_openai import OpenAIEmbeddings

        def _embed(target_model: str) -> List[float]:
            kwargs = {"model": target_model}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url

            embeddings = OpenAIEmbeddings(**kwargs)
            logger.debug(
                "Generating embedding with model=%s request_id=%s text_length=%s",
                target_model,
                x_request_id,
                len(payload.text or ""),
            )
            return embeddings.embed_query(payload.text)

        vector = _embed(model_name)
    except HTTPException:
        raise
    except ImportError as exc:
        logger.exception("langchain_openai missing for embedding generation")
        raise HTTPException(status_code=500, detail="Embedding dependencies unavailable") from exc
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception(
            "Unexpected error generating embedding request_id=%s", x_request_id
        )
        raise HTTPException(status_code=500, detail="Failed to generate embedding") from exc

    if not isinstance(vector, list):
        logger.error(
            "Embedding backend returned non-list vector request_id=%s", x_request_id
        )
        raise HTTPException(status_code=502, detail="Embedding data invalid")

    logger.info(
        "Generated embedding model=%s dims=%s request_id=%s",
        model_name,
        len(vector),
        x_request_id,
    )

    return AgentEmbeddingResponse(
        model=model_name,
        embedding=vector,
    )


@router.post("/embedding/search", response_model=AgentEmbeddingSearchResponse)
def search_embedding(
    payload: AgentEmbeddingSearchRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> AgentEmbeddingSearchResponse:
    """Proxy embedding search requests to the API service."""

    body = payload.model_dump(exclude_none=True)
    headers: Dict[str, str] = {}
    if x_contract_version:
        headers["X-Contract-Version"] = x_contract_version
    if x_request_id:
        headers["X-Request-Id"] = x_request_id

    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            response = client.post(
                f"{API_BASE_URL}/embedding/search",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json() or {}
    except Exception as exc:
        logger.exception(
            "Embedding search proxy failed site=%s request_id=%s error=%s",
            payload.siteId,
            x_request_id,
            exc,
        )
        raise HTTPException(status_code=502, detail="Embedding search proxy failed") from exc

    results_payload = data.get("results") if isinstance(data, dict) else None
    results: List[AgentEmbeddingSearchResult] = []
    if isinstance(results_payload, list):
        for item in results_payload:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            similarity = item.get("similarity", item.get("score"))
            if not isinstance(url, str):
                continue
            try:
                similarity_val = float(similarity)
            except (TypeError, ValueError):
                similarity_val = 0.0
            results.append(
                AgentEmbeddingSearchResult(
                    url=url,
                    similarity=similarity_val,
                    title=item.get("title"),
                    description=item.get("description"),
                    meta=item.get("meta") if isinstance(item.get("meta"), dict) else None,
                )
            )

    site_id = data.get("siteId") if isinstance(data, dict) else None
    query = data.get("query") if isinstance(data, dict) else None

    logger.info(
        "Embedding search proxy returning %s result(s) site=%s request_id=%s",
        len(results),
        payload.siteId,
        x_request_id,
    )

    return AgentEmbeddingSearchResponse(
        siteId=site_id if isinstance(site_id, str) else payload.siteId,
        query=query if isinstance(query, str) else payload.query,
        results=results,
    )
