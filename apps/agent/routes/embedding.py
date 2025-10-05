"""Embedding route for the agent service."""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException

from contracts.agent_api import AgentEmbeddingRequest, AgentEmbeddingResponse
from core.logging import get_agent_logger


router = APIRouter(prefix="/agent", tags=["embedding"])

logger = get_agent_logger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


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
