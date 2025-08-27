from __future__ import annotations
from fastapi import APIRouter, Header
from contracts.sdk_api import RuleCheckRequest, RuleCheckResponse, RuleTrackRequest, RuleTrackResponse

router = APIRouter(prefix="/rule", tags=["rule"])

@router.post("/check", response_model=RuleCheckResponse)
def rule_check(
    payload: RuleCheckRequest,
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RuleCheckResponse:
    # TODO: classify event via atlas; load rules; evaluate deterministically
    return RuleCheckResponse(
        eventType="unknown",
        matchedRules=[],
        shouldProceed=False,
        reason="no_rule",
    )

@router.post("/track", response_model=RuleTrackResponse)
def rule_track_post(
    payload: RuleTrackRequest,
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RuleTrackResponse:
    return RuleTrackResponse(
        siteId=payload.siteId,
        status=payload.status,
        version=None,
        updatedAt=None,
        events={},
    )

@router.get("/track", response_model=RuleTrackResponse)
def rule_track_get(
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RuleTrackResponse:
    return RuleTrackResponse(
        siteId="demo-site",
        status="off",
        version=None,
        updatedAt=None,
        events={},
    )
