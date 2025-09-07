from __future__ import annotations
from fastapi import APIRouter, Header
from contracts.sdk_api import (
    SiteMapRequest, SiteRegisterRequest, SiteRegisterResponse,
    SiteMapResponse, SiteMapPage,
    SiteInfoRequest, SiteInfoResponse,
    SiteAtlasRequest, SiteAtlasResponse,
)
from helper.common import SITE_MAP, SITE_INFO, SITE_ATLAS

router = APIRouter(prefix="/site", tags=["site"])

# ------------------------------------------------------------------------
# /site/register  (no side effects; just echo a siteId + parentUrl)
# ------------------------------------------------------------------------
@router.post("/register", response_model=SiteRegisterResponse)
def register_site(payload: SiteRegisterRequest) -> SiteRegisterResponse:
    site_id = payload.siteId or f"site_{abs(hash(payload.parentUrl)) % 99999}"
    return SiteRegisterResponse(siteId=site_id, parentUrl=payload.parentUrl, meta=payload.meta)

# ------------------------------------------------------------------------
# /site/map (GET = fetch current; POST = request build)
# ------------------------------------------------------------------------
@router.get("/map", response_model=SiteMapResponse)
def get_site_map(siteId: str) -> SiteMapResponse:
    # Return mock sitemap if available; otherwise an empty map
    sm = SITE_MAP.get(siteId)
    return sm if sm else SiteMapResponse(siteId=siteId, pages=[])

@router.post("/map", response_model=SiteMapResponse)
def build_site_map(
    payload: SiteMapRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapResponse:
    # no mock generation; just return correct shape
    return SiteMapResponse(siteId=payload.siteId, pages=[])

# ------------------------------------------------------------------------
# /site/info (GET = fetch; POST = drag)
# ------------------------------------------------------------------------
@router.get("/info", response_model=SiteInfoResponse)
def get_site_info(siteId: str, url: str) -> SiteInfoResponse:
    # Return mock site info entry if available; otherwise minimal info
    for info in SITE_INFO:
        if info.siteId == siteId and info.url == url:
            return info
    return SiteInfoResponse(siteId=siteId, url=url, meta=None, normalized=None)

@router.post("/info", response_model=SiteInfoResponse)
def drag_site_info(payload: SiteInfoRequest) -> SiteInfoResponse:
    # no mock meta/normalized; just reflect inputs
    return SiteInfoResponse(siteId=payload.siteId, url=payload.url, meta=None, normalized=None)

# ------------------------------------------------------------------------
# /site/atlas (GET = fetch; POST = drag)
# ------------------------------------------------------------------------
@router.get("/atlas", response_model=SiteAtlasResponse)
def get_site_atlas(siteId: str, url: str) -> SiteAtlasResponse:
    # Return mock atlas snapshot if available; otherwise minimal response
    sa = SITE_ATLAS.get(url)
    return sa if sa else SiteAtlasResponse(siteId=siteId, url=url, atlas=None, queuedPlanRebuild=None)

@router.post("/atlas", response_model=SiteAtlasResponse)
def drag_site_atlas(payload: SiteAtlasRequest) -> SiteAtlasResponse:
    # no mock atlas content; just reflect inputs
    return SiteAtlasResponse(siteId=payload.siteId, url=payload.url, atlas=None, queuedPlanRebuild=None)
