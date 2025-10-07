from __future__ import annotations
from typing import Optional
import httpx
from fastapi import APIRouter, Header, HTTPException

from helper.common import AGENT_URL, AGENT_TIMEOUT, _fwd_headers, get_site_settings_payload
from contracts.client_api import (
    SuggestGetRequest,
    SuggestGetResponse,
    SuggestNextRequest,
    SuggestNextResponse,
)
from core.logging import get_api_logger

router = APIRouter(prefix="/suggest", tags=["suggest"])

logger = get_api_logger(__name__)

@router.post("", response_model=SuggestGetResponse)
def suggest(
    payload: SuggestGetRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    settings = get_site_settings_payload(payload.siteId)
    if not settings.get("enableSuggestion", True):
        logger.info(
            "Suggestion disabled for site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return SuggestGetResponse(suggestions=[])

    body = payload.model_dump()
    try:
        logger.info(
            "Suggest request site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(
                f"{AGENT_URL}/agent/suggest",
                json=body,
                headers=_fwd_headers(x_contract_version, x_request_id),
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.exception(
            "Suggest proxy failed site=%s request_id=%s: %s",
            payload.siteId,
            x_request_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")
    try:
        suggestions = data.get("suggestions", [])
        logger.info(
            "Suggest returning %s suggestion(s) site=%s request_id=%s",
            len(suggestions),
            payload.siteId,
            x_request_id,
        )
        return SuggestGetResponse(suggestions=suggestions)
    except Exception as e:
        logger.exception(
            "Suggest response parsing failed site=%s request_id=%s: %s",
            payload.siteId,
            x_request_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Agent response invalid: {e}")


@router.post("/next", response_model=SuggestNextResponse)
def suggest_next(
    payload: SuggestNextRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> SuggestNextResponse:
    settings = get_site_settings_payload(payload.siteId)
    if not settings.get("enableSuggestion", True):
        logger.info(
            "Suggestion disabled for site=%s request_id=%s (next)",
            payload.siteId,
            x_request_id,
        )
        return SuggestNextResponse(suggestions=[])

    body = payload.model_dump()
    try:
        logger.info(
            "SuggestNext request site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(
                f"{AGENT_URL}/agent/suggest",
                json=body,
                headers=_fwd_headers(x_contract_version, x_request_id),
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.exception(
            "SuggestNext proxy failed site=%s request_id=%s: %s",
            payload.siteId,
            x_request_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")
    try:
        suggestions = data.get("suggestions", [])
        logger.info(
            "SuggestNext returning %s suggestion(s) site=%s request_id=%s",
            len(suggestions),
            payload.siteId,
            x_request_id,
        )
        return SuggestNextResponse(suggestions=suggestions)
    except Exception as e:
        logger.exception(
            "SuggestNext response parsing failed site=%s request_id=%s: %s",
            payload.siteId,
            x_request_id,
            e,
        )
        raise HTTPException(status_code=502, detail=f"Agent response invalid: {e}")
