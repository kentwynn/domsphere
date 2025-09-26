from __future__ import annotations
from typing import Iterable, List

import httpx
from fastapi import APIRouter, Header, HTTPException
from contracts.client_api import (
    SiteMapRequest, SiteRegisterRequest, SiteRegisterResponse,
    SiteMapResponse, SiteMapPage,
    SiteInfoRequest, SiteInfoResponse,
    SiteAtlasRequest, SiteAtlasResponse,
    SiteMapEmbeddingRequest, SiteMapEmbeddingResponse,
    SiteMapUrlEmbeddingRequest, SiteMapSearchResponse, SiteMapSearchResult,
)
from helper.common import (
    AGENT_URL,
    AGENT_TIMEOUT,
    build_page_embedding_text,
    store_site_embedding,
    search_site_embeddings,
    get_site_embeddings,
    _fwd_headers,
    get_site_map_response,
    store_site_map_pages,
    generate_site_map,
    register_site,
    resolve_site_url,
    refresh_site_info,
    lookup_site_info,
    get_site_atlas_response,
    refresh_site_atlas,
)
from core.logging import get_api_logger

router = APIRouter(prefix="/site", tags=["site"])

logger = get_api_logger(__name__)


def _call_agent_embedding(
    text: str,
    xcv: str | None,
    xrid: str | None,
) -> List[float]:
    if not text.strip():
        # Minimal fallback – still embed the URL itself
        text = "Embedding request with empty page metadata"
    body = {"text": text}
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT) as client:
            response = client.post(
                f"{AGENT_URL}/agent/embedding",
                json=body,
                headers=_fwd_headers(xcv, xrid),
            )
            response.raise_for_status()
            data = response.json() or {}
    except Exception as exc:
        raise RuntimeError(f"Agent embedding request failed: {exc}") from exc

    vector = data.get("embedding")
    if not isinstance(vector, list):
        raise RuntimeError("Agent embedding response missing 'embedding' array")

    try:
        return [float(v) for v in vector]
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Agent embedding response contained non-numeric values") from exc


def _embed_pages(
    site_id: str,
    pages: Iterable[SiteMapPage],
    *,
    xcv: str | None,
    xrid: str | None,
) -> SiteMapEmbeddingResponse:
    pages_list = list(pages)
    total = len(pages_list)
    embedded = 0
    failed: List[str] = []

    for page in pages_list:
        text, meta = build_page_embedding_text(site_id, page)
        try:
            vector = _call_agent_embedding(text, xcv, xrid)
        except RuntimeError as exc:
            logger.exception(
                "Embedding failed site=%s url=%s request_id=%s: %s",
                site_id,
                page.url,
                xrid,
                exc,
            )
            failed.append(page.url)
            continue

        store_site_embedding(site_id, page.url, vector, text=text, meta=meta)
        embedded += 1

    message = f"Embedded {embedded} of {total} sitemap URL(s)"
    return SiteMapEmbeddingResponse(
        siteId=site_id,
        totalUrls=total,
        embeddedUrls=embedded,
        failedUrls=failed,
        message=message,
    )

# ------------------------------------------------------------------------
# /site/register  (no side effects; just echo a siteId + parentUrl)
# ------------------------------------------------------------------------
@router.post("/register", response_model=SiteRegisterResponse)
def register_site(payload: SiteRegisterRequest) -> SiteRegisterResponse:
    site_id = payload.siteId or f"site_{abs(hash(payload.parentUrl)) % 99999}"
    logger.info(
        "Site registration request parent=%s assigned=%s",
        payload.parentUrl,
        site_id,
    )
    register_site(
        site_id,
        parent_url=payload.parentUrl,
        meta=payload.meta,
    )
    return SiteRegisterResponse(siteId=site_id, parentUrl=payload.parentUrl, meta=payload.meta)

# ------------------------------------------------------------------------
# /site/map (GET = fetch current; POST = request build)
# ------------------------------------------------------------------------
@router.get("/map", response_model=SiteMapResponse)
def get_site_map(
    siteId: str,
    url: str | None = None,
    depth: int = 1,
    force: bool = False,
) -> SiteMapResponse:
    sm = get_site_map_response(siteId)
    if sm.pages and not force:
        logger.info("Returning cached sitemap site=%s pages=%s", siteId, len(sm.pages))
        return sm

    start_url = resolve_site_url(siteId, url)
    if not start_url:
        if sm.pages:
            return sm
        logger.warning("Sitemap not found and no start URL provided site=%s", siteId)
        return SiteMapResponse(siteId=siteId, pages=[])

    generated = generate_site_map(siteId, start_url=start_url, depth=depth)
    logger.info(
        "Generated sitemap site=%s pages=%s depth=%s force=%s",
        siteId,
        len(generated.pages),
        depth,
        force,
    )
    return generated

@router.post("/map", response_model=SiteMapResponse)
def build_site_map(
    payload: SiteMapRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapResponse:
    start_url = resolve_site_url(payload.siteId, payload.url)
    if not start_url:
        logger.warning(
            "Build sitemap missing start URL site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        raise HTTPException(status_code=400, detail="START_URL_REQUIRED")

    logger.info(
        "Building sitemap site=%s depth=%s request_id=%s",
        payload.siteId,
        payload.depth,
        x_request_id,
    )
    depth = payload.depth or 1
    sm = generate_site_map(payload.siteId, start_url=start_url, depth=depth)
    return sm


@router.post("/map/embed", response_model=SiteMapEmbeddingResponse)
def embed_site_map(
    payload: SiteMapEmbeddingRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapEmbeddingResponse:
    site_map = get_site_map_response(payload.siteId)
    if not site_map.pages:
        logger.warning(
            "Embed sitemap requested but sitemap missing site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return SiteMapEmbeddingResponse(
            siteId=payload.siteId,
            totalUrls=0,
            embeddedUrls=0,
            failedUrls=[],
            message="No sitemap entries available",
        )

    logger.info(
        "Embedding full sitemap site=%s pages=%s request_id=%s",
        payload.siteId,
        len(site_map.pages),
        x_request_id,
    )
    return _embed_pages(
        payload.siteId,
        site_map.pages,
        xcv=x_contract_version,
        xrid=x_request_id,
    )


@router.post("/map/embed/urls", response_model=SiteMapEmbeddingResponse)
def embed_specific_urls(
    payload: SiteMapUrlEmbeddingRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapEmbeddingResponse:
    if not payload.urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    site_map = get_site_map_response(payload.siteId)
    pages_by_url = {page.url: page for page in site_map.pages}

    pages: List[SiteMapPage] = []
    for url in payload.urls:
        page = pages_by_url.get(url)
        if page:
            pages.append(page)
        else:
            logger.debug(
                "Embedding specific URL not in sitemap site=%s url=%s request_id=%s",
                payload.siteId,
                url,
                x_request_id,
            )
            pages.append(SiteMapPage(url=url, meta=None))

    store_site_map_pages(payload.siteId, pages)

    logger.info(
        "Embedding specific URLs site=%s count=%s request_id=%s",
        payload.siteId,
        len(pages),
        x_request_id,
    )
    return _embed_pages(
        payload.siteId,
        pages,
        xcv=x_contract_version,
        xrid=x_request_id,
    )


@router.get("/map/search", response_model=SiteMapSearchResponse)
def search_site_map(
    siteId: str,
    query: str,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapSearchResponse:
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query must be provided")

    embeddings = get_site_embeddings(siteId)
    if not embeddings:
        logger.info(
            "Search requested but no embeddings cached site=%s request_id=%s",
            siteId,
            x_request_id,
        )
        return SiteMapSearchResponse(siteId=siteId, query=query, results=[])

    try:
        query_vector = _call_agent_embedding(query, x_contract_version, x_request_id)
    except RuntimeError as exc:
        logger.exception(
            "Search embedding failed site=%s request_id=%s: %s",
            siteId,
            x_request_id,
            exc,
        )
        raise HTTPException(status_code=502, detail="Failed to generate query embedding") from exc

    matches = search_site_embeddings(siteId, query_vector, top_k=3)
    results = [
        SiteMapSearchResult(
            url=url,
            score=score,
            meta=payload.get("meta") if isinstance(payload, dict) else None,
        )
        for url, score, payload in matches
    ]

    logger.info(
        "Search returning %s result(s) site=%s request_id=%s",
        len(results),
        siteId,
        x_request_id,
    )
    return SiteMapSearchResponse(siteId=siteId, query=query, results=results)

# ------------------------------------------------------------------------
# /site/info (GET = fetch; POST = drag)
# ------------------------------------------------------------------------
@router.get("/info", response_model=SiteInfoResponse)
def get_site_info(
    siteId: str,
    url: str | None = None,
    path: str | None = None,
    force: bool = False,
) -> SiteInfoResponse:
    if not url and not path:
        raise HTTPException(status_code=400, detail="URL_OR_PATH_REQUIRED")

    target_url = resolve_site_url(siteId, url, path)
    if not target_url:
        raise HTTPException(status_code=400, detail="UNRESOLVED_URL")

    info = None if force else lookup_site_info(siteId, target_url)
    if info is None:
        info = refresh_site_info(siteId, url=target_url, force=True)

    if info:
        logger.info("Returning site info site=%s url=%s", siteId, target_url)
        return info

    logger.warning("Site info not available site=%s url=%s", siteId, target_url)
    return SiteInfoResponse(siteId=siteId, url=target_url, meta=None, normalized=None)

@router.post("/info", response_model=SiteInfoResponse)
def drag_site_info(payload: SiteInfoRequest) -> SiteInfoResponse:
    target_url = resolve_site_url(payload.siteId, payload.url, payload.path)
    if not target_url:
        raise HTTPException(status_code=400, detail="URL_OR_PATH_REQUIRED")

    logger.info("Refreshing site info site=%s url=%s", payload.siteId, target_url)
    info = refresh_site_info(payload.siteId, url=target_url, force=True)
    if info:
        return info
    return SiteInfoResponse(siteId=payload.siteId, url=target_url, meta=None, normalized=None)

# ------------------------------------------------------------------------
# /site/atlas (GET = fetch; POST = drag)
# ------------------------------------------------------------------------
@router.get("/atlas", response_model=SiteAtlasResponse)
def get_site_atlas(siteId: str, url: str, force: bool = False) -> SiteAtlasResponse:
    if not url:
        raise HTTPException(status_code=400, detail="URL_REQUIRED")

    if not force:
        atlas = get_site_atlas_response(siteId, url)
        if atlas:
            atlas_payload = atlas.atlas
            element_count = None
            if isinstance(atlas_payload, dict):
                element_count = atlas_payload.get("elementCount")
            else:
                element_count = getattr(atlas_payload, "elementCount", None)
            logger.info(
                "Returning cached site atlas site=%s url=%s elements=%s",
                siteId,
                url,
                element_count if element_count is not None else 0,
            )
            return atlas

    refreshed = refresh_site_atlas(siteId, url, force=True)
    if refreshed:
        atlas_payload = refreshed.atlas
        element_count = None
        if isinstance(atlas_payload, dict):
            element_count = atlas_payload.get("elementCount")
        else:
            element_count = getattr(atlas_payload, "elementCount", None)
        logger.info(
            "Refreshed site atlas site=%s url=%s elements=%s",
            siteId,
            url,
            element_count if element_count is not None else 0,
        )
        return refreshed

    logger.warning("Site atlas not available site=%s url=%s", siteId, url)
    return SiteAtlasResponse(siteId=siteId, url=url, atlas=None, queuedPlanRebuild=None)

@router.post("/atlas", response_model=SiteAtlasResponse)
def drag_site_atlas(payload: SiteAtlasRequest) -> SiteAtlasResponse:
    if not payload.url:
        raise HTTPException(status_code=400, detail="URL_REQUIRED")

    logger.info("Refreshing site atlas site=%s url=%s", payload.siteId, payload.url)
    atlas = refresh_site_atlas(payload.siteId, payload.url, force=True)
    if atlas:
        return atlas
    return SiteAtlasResponse(siteId=payload.siteId, url=payload.url, atlas=None, queuedPlanRebuild=None)
