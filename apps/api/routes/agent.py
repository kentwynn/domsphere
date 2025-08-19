from fastapi import APIRouter, Header, HTTPException
import httpx
from models.contracts import PlanRequest, PlanResponse
from clients.agent import call_agent_plan
from config import SITE_KEY

router = APIRouter()

def _validate_site_key(x_site_key: str | None):
    if not x_site_key:
        raise HTTPException(status_code=401, detail="Missing site key")
    if x_site_key != SITE_KEY:
        raise HTTPException(status_code=403, detail="Invalid site key")

@router.post("/plan", response_model=PlanResponse)
def plan_endpoint(body: PlanRequest, x_site_key: str | None = Header(default=None, alias="X-Site-Key")):
    _validate_site_key(x_site_key)
    try:
        agent_res = call_agent_plan(body.model_dump())
        return PlanResponse.model_validate(agent_res)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except (httpx.ConnectError, httpx.ReadTimeout):
        raise HTTPException(status_code=502, detail="Agent unavailable")
