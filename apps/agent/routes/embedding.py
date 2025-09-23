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
    """Generate an embedding vector for the provided text input using OpenAI."""

    api_key = os.getenv("OPENAI_TOKEN")
    if not api_key:
        logger.error(
            "OPENAI_TOKEN missing while handling embedding request request_id=%s",
            x_request_id,
        )
        raise HTTPException(status_code=500, detail="OpenAI configuration missing")

    configured_model = os.getenv("OPENAI_EMBEDDING_MODEL")
    model_name = configured_model or DEFAULT_EMBEDDING_MODEL

    try:
        # Delay import so service can start without optional dependency
        from langchain_openai import OpenAIEmbeddings

        def _embed(target_model: str) -> List[float]:
            embeddings = OpenAIEmbeddings(api_key=api_key, model=target_model)
            logger.debug(
                "Generating embedding with model=%s request_id=%s text_length=%s",
                target_model,
                x_request_id,
                len(payload.text or ""),
            )
            return embeddings.embed_query(payload.text)

        try:
            vector = _embed(model_name)
        except Exception as exc:  # pragma: no cover - retry path
            model_not_found = exc.__class__.__name__ == "NotFoundError"
            if not model_not_found or not configured_model:
                raise
            logger.warning(
                "Configured embedding model unavailable model=%s request_id=%s; falling back to %s",
                configured_model,
                x_request_id,
                DEFAULT_EMBEDDING_MODEL,
            )
            model_name = DEFAULT_EMBEDDING_MODEL
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
