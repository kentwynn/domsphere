from __future__ import annotations
import os
from typing import Optional
import httpx
from fastapi import APIRouter, Header, HTTPException

from helper.common import AGENT_TIMEOUT, AGENT_URL, _fwd_headers
from contracts.sdk_api import SuggestGetRequest, SuggestGetResponse, Turn

router = APIRouter(prefix="/suggest", tags=["suggest"])

AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:5001")


@router.post("/get", response_model=SuggestGetResponse)
def suggest_get(
    payload: SuggestGetRequest,
    x_contract_version: Optional[str] = Header(default=None, alias="X-Contract-Version"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    body = payload.model_dump()
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            r = client.post(f"{AGENT_URL}/agent/suggest/next", json=body, headers=_fwd_headers(x_contract_version, x_request_id))
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent proxy failed: {e}")
    try:
        turn = Turn.model_validate(data["turn"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent response invalid: {e}")
    return SuggestGetResponse(turn=turn)
