from __future__ import annotations
from fastapi import APIRouter, Header
from contracts.sdk_api import (
    UrlDragRequest, UrlDragResponse,
    PageDragRequest, PageDragResponse,
)

router = APIRouter(prefix="", tags=["drag"])

@router.post("/url/drag", response_model=UrlDragResponse)
def url_drag(
    payload: UrlDragRequest,
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> UrlDragResponse:
    # TODO: schedule crawl; persist UrlDocument(s) in DB
    job_id = f"job_{payload.siteId}"
    return UrlDragResponse(jobId=job_id, queued=True)

@router.post("/page/drag", response_model=PageDragResponse)
def page_drag(
    payload: PageDragRequest,
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> PageDragResponse:
    # TODO: capture DOM; build DomAtlasSnapshot; persist; maybe queue plan rebuild
    return PageDragResponse(atlas=None, normalized=None, queuedPlanRebuild=False)
