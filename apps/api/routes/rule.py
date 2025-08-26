from __future__ import annotations
from fastapi import APIRouter, Header
from contracts.sdk_api import RuleCheckRequest, RuleCheckResponse

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
