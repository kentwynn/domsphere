from __future__ import annotations
import os
import httpx
from fastapi import APIRouter, Header, HTTPException

from contracts.sdk_api import SuggestGetRequest, SuggestGetResponse
from contracts.agent_api import AgentSuggestNextRequest, AgentSuggestNextResponse

router = APIRouter(prefix="/suggest", tags=["suggest"])

AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:5001")


@router.post("/get", response_model=SuggestGetResponse)
async def suggest_get(
    payload: SuggestGetRequest,
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SuggestGetResponse:
    """
    Thin pass-through:
    SDK -> /suggest/get -> (API) -> Agent /agent/suggest/next
    The Agent fully controls the micro-conversation (ask|final).
    """
    agent_req = AgentSuggestNextRequest(**payload.dict())

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{AGENT_BASE_URL}/agent/suggest/next",
                json=agent_req.model_dump(),
                headers={
                    "X-Contract-Version": x_contract_version or "",
                    "X-Request-Id": x_request_id or "",
                    "X-Site-Key": x_site_key or "",
                },
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail={"message": "agent unreachable", "error": str(e)})

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail={"message": "agent error", "status": resp.status_code, "body": resp.text},
        )

    agent_resp = AgentSuggestNextResponse(**resp.json())
    return SuggestGetResponse(turn=agent_resp.turn)
