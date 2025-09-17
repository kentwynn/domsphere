from __future__ import annotations
from fastapi import APIRouter
from contracts.client_api import APIHealthResponse
from core.logging import get_api_logger

router = APIRouter(tags=["health"])

logger = get_api_logger(__name__)

@router.get("/health", response_model=APIHealthResponse)
def health() -> APIHealthResponse:
    logger.debug("Health endpoint pinged")
    return APIHealthResponse(status="ok")
