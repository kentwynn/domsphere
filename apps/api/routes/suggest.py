from __future__ import annotations
from fastapi import APIRouter, Header
from contracts.sdk_api import SuggestGetRequest, SuggestGetResponse

router = APIRouter(prefix="/suggest", tags=["suggest"])

@router.post("/get", response_model=SuggestGetResponse)
def suggest_get(
    payload: SuggestGetRequest,
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    # TODO: render via recipes or call agent /agent/suggestion when needed
    return SuggestGetResponse(
        suggestions=[],
        trace=["stub:suggest_get"],
        ttlSec=20,
        planVersion=None,
        noActionReason=None,
    )
