from __future__ import annotations
from fastapi import APIRouter
from contracts.client_api import APIHealthResponse

router = APIRouter(tags=["health"])

@router.get("/health", response_model=APIHealthResponse)
def health() -> APIHealthResponse:
    return APIHealthResponse(status="ok")
