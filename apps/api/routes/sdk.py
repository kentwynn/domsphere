from __future__ import annotations

from fastapi import APIRouter, HTTPException

from contracts.client_api import (
    SiteSettingsPayload,
    SiteSettingsResponse,
    SiteStylePayload,
    SiteStyleResponse,
)
from helper.common import (
    get_site_style,
    store_site_style,
    get_site_settings_payload,
    store_site_settings_payload,
)
from core.logging import get_api_logger

router = APIRouter(prefix="/sdk", tags=["sdk"])

logger = get_api_logger(__name__)


@router.get("/style", response_model=SiteStyleResponse)
def fetch_style(siteId: str) -> SiteStyleResponse:
    css, updated = get_site_style(siteId)
    if css is None:
        logger.info("Style not found for site=%s", siteId)
        return SiteStyleResponse(siteId=siteId, css=None, updatedAt=updated, source="none")
    logger.info("Returning style configuration site=%s", siteId)
    return SiteStyleResponse(siteId=siteId, css=css, updatedAt=updated, source="mock")


@router.post("/style", response_model=SiteStyleResponse)
def upsert_style(payload: SiteStylePayload) -> SiteStyleResponse:
    if not isinstance(payload.css, str):
        raise HTTPException(status_code=400, detail="'css' must be a string")
    updated = store_site_style(payload.siteId, payload.css)
    logger.info("Stored style configuration site=%s", payload.siteId)
    return SiteStyleResponse(
        siteId=payload.siteId,
        css=payload.css,
        updatedAt=updated,
        source="mock",
    )


@router.get("/settings", response_model=SiteSettingsResponse)
def fetch_settings(siteId: str) -> SiteSettingsResponse:
    payload = get_site_settings_payload(siteId)
    logger.info(
        "Returning SDK settings site=%s enableSuggestion=%s enableSearch=%s topSearch=%s",
        payload["siteId"],
        payload["enableSuggestion"],
        payload["enableSearch"],
        payload.get("topSearchResults"),
    )
    return SiteSettingsResponse(**payload)


@router.put("/settings", response_model=SiteSettingsResponse)
def upsert_settings(payload: SiteSettingsPayload) -> SiteSettingsResponse:
    updated = store_site_settings_payload(
        payload.siteId,
        enable_suggestion=payload.enableSuggestion,
        enable_search=payload.enableSearch,
        top_search_results=payload.topSearchResults,
    )
    logger.info(
        "Stored SDK settings site=%s enableSuggestion=%s enableSearch=%s topSearch=%s",
        updated["siteId"],
        updated["enableSuggestion"],
        updated["enableSearch"],
        updated.get("topSearchResults"),
    )
    return SiteSettingsResponse(**updated)
