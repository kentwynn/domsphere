from __future__ import annotations
from typing import Optional
import httpx
from fastapi import APIRouter, Header, HTTPException

from helper.common import AGENT_TIMEOUT, AGENT_URL, _fwd_headers
from contracts.sdk_api import SuggestGetRequest, SuggestGetResponse

router = APIRouter(prefix="/suggest", tags=["suggest"])

@router.post("", response_model=SuggestGetResponse)
def suggest(
    payload: SuggestGetRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    body = payload.model_dump()
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(
                f"{AGENT_URL}/agent/suggest",
                json=body,
                headers=_fwd_headers(x_contract_version, x_request_id),
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")
    try:
        suggestions = data.get("suggestions", [])
        return SuggestGetResponse(suggestions=suggestions)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent response invalid: {e}")
