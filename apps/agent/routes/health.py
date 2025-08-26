from fastapi import APIRouter
from contracts.common import HealthResponse

router = APIRouter(prefix="/agent", tags=["health"])

@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
