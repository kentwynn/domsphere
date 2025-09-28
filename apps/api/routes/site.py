from __future__ import annotations
from typing import Dict, Iterable, List

import httpx
from fastapi import APIRouter, Header, HTTPException
from contracts.client_api import (
    SiteMapRequest, SiteRegisterRequest, SiteRegisterResponse,
    SiteMapResponse, SiteMapPage,
    SiteInfoRequest, SiteInfoResponse, SiteInfoCollectionResponse,
    SiteAtlasRequest, SiteAtlasResponse, SiteAtlasCollectionResponse,
    SiteMapEmbeddingRequest, SiteMapEmbeddingResponse,
    SiteMapSearchResponse, SiteMapSearchResult,
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
    register_site as register_site_helper,
    resolve_site_url,
    refresh_site_info,
    lookup_site_info,
    get_site_atlas_response,
    refresh_site_atlas,
    list_site_atlas_responses,
    list_site_pages_payload,
    EMBED_BATCH_LIMIT,
    _paginate_items,
)
from db.crud import get_site as db_get_site
from core.logging import get_api_logger

router = APIRouter(prefix="/site", tags=["site"])

logger = get_api_logger(__name__)


@router.get("/pages", response_model=dict)
def list_site_pages(
    siteId: str,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 10,
) -> dict:
    pages = list_site_pages_payload(siteId, status=status)
    paged_pages, total = _paginate_items(pages, page, pageSize)
    logger.info(
        "Returning %s page(s) for site=%s status=%s",
        len(paged_pages),
        siteId,
        status,
    )
    return {
        "siteId": siteId,
        "status": status,
        "pages": paged_pages,
        "total": total,
        "page": max(page, 1),
        "pageSize": max(pageSize, 1),
    }


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
    total_expected: int | None = None,
) -> SiteMapEmbeddingResponse:
    pages_list = list(pages)
    attempted = len(pages_list)
    total = total_expected if total_expected is not None else attempted
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
    if total > attempted:
        message += f" (processed {attempted} in this batch)"
    return SiteMapEmbeddingResponse(
        siteId=site_id,
        totalUrls=total,
        embeddedUrls=embedded,
        failedUrls=failed,
        message=message,
    )


def _resolve_optional_url(site_id: str, url: str | None) -> str | None:
    if url is None:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    return resolve_site_url(site_id, candidate)


def _build_full_sitemap(
    site_id: str,
    *,
    force: bool = False,
) -> SiteMapResponse:
    site_map = get_site_map_response(site_id)
    if not force and site_map.pages:
        return site_map

    start_url = resolve_site_url(site_id, None)
    if not start_url:
        logger.warning("Missing parent URL for site sitemap site=%s", site_id)
        raise HTTPException(status_code=400, detail="START_URL_REQUIRED")

    full_map = generate_site_map(
        site_id,
        start_url=start_url,
        depth=None,
        limit=None,
        mark_missing=True,
    )
    logger.info(
        "Generated full sitemap site=%s page_count=%s force=%s",
        site_id,
        len(full_map.pages),
        force,
    )
    return full_map


def _load_site_pages(
    site_id: str,
    *,
    force_sitemap: bool = False,
) -> List[SiteMapPage]:
    existing = get_site_map_response(site_id).pages
    if existing:
        seen: Dict[str, SiteMapPage] = {}
        for page in existing:
            if not page.url:
                continue
            if page.url not in seen:
                seen[page.url] = page
        if seen:
            return list(seen.values())
    if not force_sitemap:
        return []
    try:
        generated = _build_full_sitemap(site_id, force=True)
    except HTTPException:
        return []
    seen: Dict[str, SiteMapPage] = {}
    for page in generated.pages:
        if not page.url:
            continue
        if page.url not in seen:
            seen[page.url] = page
    return list(seen.values())


def _collect_site_urls(site_id: str, *, force_sitemap: bool = False) -> List[str]:
    pages = _load_site_pages(site_id, force_sitemap=force_sitemap)
    canonical_urls: List[str] = []
    seen: set[str] = set()
    for page in pages:
        if not page.url:
            continue
        normalized = resolve_site_url(site_id, page.url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        canonical_urls.append(normalized)
    if canonical_urls:
        return canonical_urls
    start_url = resolve_site_url(site_id, None)
    return [start_url] if start_url else []

# ------------------------------------------------------------------------
# /site/register  (create/update/fetch site metadata)
# ------------------------------------------------------------------------
@router.post("/register", response_model=SiteRegisterResponse)
def register_site(payload: SiteRegisterRequest) -> SiteRegisterResponse:
    if not payload.parentUrl:
        raise HTTPException(status_code=400, detail="PARENT_URL_REQUIRED")

    site_id = register_site_helper(
        payload.siteId,
        parent_url=payload.parentUrl,
        display_name=payload.displayName,
        meta=payload.meta,
    )

    record = db_get_site(site_id)
    logger.info("Registered site siteId=%s parent=%s", site_id, payload.parentUrl)
    return SiteRegisterResponse(
        siteId=site_id,
        displayName=getattr(record, "display_name", None),
        parentUrl=getattr(record, "parent_url", payload.parentUrl),
        meta=getattr(record, "meta", payload.meta),
    )


@router.put("/register", response_model=SiteRegisterResponse)
def update_site(payload: SiteRegisterRequest) -> SiteRegisterResponse:
    if not payload.siteId:
        raise HTTPException(status_code=400, detail="SITE_ID_REQUIRED")
    if not payload.parentUrl:
        existing = db_get_site(payload.siteId)
        if existing is None or not getattr(existing, "parent_url", None):
            raise HTTPException(status_code=400, detail="PARENT_URL_REQUIRED")
        parent_url = existing.parent_url
    else:
        parent_url = payload.parentUrl

    site_id = register_site_helper(
        payload.siteId,
        parent_url=parent_url,
        display_name=payload.displayName,
        meta=payload.meta,
    )

    record = db_get_site(site_id)
    logger.info("Updated site siteId=%s", site_id)
    return SiteRegisterResponse(
        siteId=site_id,
        displayName=getattr(record, "display_name", payload.displayName),
        parentUrl=getattr(record, "parent_url", parent_url),
        meta=getattr(record, "meta", payload.meta),
    )


@router.get("/register", response_model=SiteRegisterResponse)
def get_site_registration(siteId: str) -> SiteRegisterResponse:
    record = db_get_site(siteId)
    if record is None:
        raise HTTPException(status_code=404, detail="SITE_NOT_FOUND")
    return SiteRegisterResponse(
        siteId=record.site_id,
        displayName=getattr(record, "display_name", None),
        parentUrl=getattr(record, "parent_url", None),
        meta=getattr(record, "meta", None),
    )

# ------------------------------------------------------------------------
# /site/map (GET = fetch current; POST = request build)
# ------------------------------------------------------------------------
@router.get("/map", response_model=SiteMapResponse)
def get_site_map(
    siteId: str,
    url: str | None = None,
    depth: int | None = None,
    limit: int | None = None,
    force: bool = False,
    page: int = 1,
    pageSize: int = 10,
) -> SiteMapResponse:
    custom_request = any(value is not None for value in (url, depth, limit))
    if not custom_request:
        site_map = _build_full_sitemap(siteId, force=force)
        paged_pages, total = _paginate_items(site_map.pages, page, pageSize)
        logger.info(
            "Returning full sitemap site=%s pages=%s force=%s",
            siteId,
            len(site_map.pages),
            force,
        )
        return site_map.copy(
            update={
                "pages": paged_pages,
                "total": total,
                "page": max(page, 1),
                "pageSize": max(pageSize, 1),
            }
        )

    start_url = resolve_site_url(siteId, url)
    if not start_url:
        logger.warning(
            "Custom sitemap request unresolved site=%s url=%s",
            siteId,
            url,
        )
        raise HTTPException(status_code=400, detail="START_URL_REQUIRED")

    generated = generate_site_map(
        siteId,
        start_url=start_url,
        depth=depth,
        limit=limit,
        mark_missing=url is None,
    )
    logger.info(
        "Generated custom sitemap site=%s pages=%s depth=%s limit=%s",
        siteId,
        len(generated.pages),
        depth,
        limit,
    )
    return generated

@router.post("/map", response_model=SiteMapResponse)
def build_site_map(
    payload: SiteMapRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapResponse:
    custom_request = any(
        value is not None for value in (payload.url, payload.depth, payload.limit)
    )

    if not custom_request:
        logger.info(
            "Building full sitemap site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return _build_full_sitemap(payload.siteId, force=True)

    start_url = resolve_site_url(payload.siteId, payload.url)
    if not start_url:
        logger.warning(
            "Build sitemap missing start URL site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        raise HTTPException(status_code=400, detail="START_URL_REQUIRED")

    logger.info(
        "Building custom sitemap site=%s depth=%s limit=%s request_id=%s",
        payload.siteId,
        payload.depth,
        payload.limit,
        x_request_id,
    )
    sm = generate_site_map(
        payload.siteId,
        start_url=start_url,
        depth=payload.depth,
        limit=payload.limit,
        mark_missing=payload.url is None,
    )
    return sm


@router.post("/map/embed", response_model=SiteMapEmbeddingResponse)
def embed_site_map(
    payload: SiteMapEmbeddingRequest,
    x_contract_version: str | None = Header(default=None, alias="X-Contract-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SiteMapEmbeddingResponse:
    known_pages = _load_site_pages(payload.siteId, force_sitemap=not bool(payload.urls))
    pages_by_url = {page.url: page for page in known_pages}

    requested_urls = payload.urls or [page.url for page in known_pages]

    if not requested_urls:
        logger.warning(
            "Embedding requested but no URLs available site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return SiteMapEmbeddingResponse(
            siteId=payload.siteId,
            totalUrls=0,
            embeddedUrls=0,
            failedUrls=[],
            message="No URLs available for embedding",
        )

    unique_pages: List[SiteMapPage] = []
    pending_records: List[SiteMapPage] = []
    new_pages: List[SiteMapPage] = []
    seen_urls: Dict[str, SiteMapPage] = {}

    for url in requested_urls:
        resolved = resolve_site_url(payload.siteId, url)
        if not resolved:
            logger.warning(
                "Embedding specific URL rejected site=%s url=%s (outside domain)",
                payload.siteId,
                url,
            )
            continue
        if resolved in seen_urls:
            continue
        page = pages_by_url.get(resolved)
        if page is None:
            logger.debug(
                "Embedding specific URL not in sitemap site=%s url=%s request_id=%s",
                payload.siteId,
                resolved,
                x_request_id,
            )
            page = SiteMapPage(url=resolved, meta=None)
            new_pages.append(page)
        seen_urls[resolved] = page
        unique_pages.append(page)

    if new_pages:
        store_site_map_pages(payload.siteId, new_pages, mark_missing=False)

    if not unique_pages:
        logger.warning(
            "Embedding requested but no URLs resolved site=%s request_id=%s",
            payload.siteId,
            x_request_id,
        )
        return SiteMapEmbeddingResponse(
            siteId=payload.siteId,
            totalUrls=0,
            embeddedUrls=0,
            failedUrls=[],
            message="No resolvable URLs available for embedding",
        )

    batch_limit = EMBED_BATCH_LIMIT if EMBED_BATCH_LIMIT > 0 else len(unique_pages)
    batch_pages = unique_pages[:batch_limit]
    pending_records = unique_pages[batch_limit:]

    if not batch_pages:
        message = (
            "No URLs embedded in this batch; remaining URLs deferred for asynchronous processing"
        )
        return SiteMapEmbeddingResponse(
            siteId=payload.siteId,
            totalUrls=len(unique_pages),
            embeddedUrls=0,
            failedUrls=[],
            message=message,
            pendingUrls=[page.url for page in pending_records],
        )

    logger.info(
        "Embedding sitemap URLs site=%s requested=%s batch=%s pending=%s request_id=%s",
        payload.siteId,
        len(unique_pages),
        len(batch_pages),
        len(pending_records),
        x_request_id,
    )

    response = _embed_pages(
        payload.siteId,
        batch_pages,
        xcv=x_contract_version,
        xrid=x_request_id,
        total_expected=len(unique_pages),
    )

    if pending_records:
        response = response.copy(
            update={
                "pendingUrls": [page.url for page in pending_records],
                "message": f"{response.message} (remaining {len(pending_records)} URL(s) deferred)",
            }
        )

    return response


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
@router.get("/info", response_model=SiteInfoCollectionResponse)
def get_site_info(
    siteId: str,
    url: str | None = None,
    force: bool = False,
    page: int = 1,
    pageSize: int = 10,
) -> SiteInfoCollectionResponse:
    target_url = _resolve_optional_url(siteId, url)
    if target_url:
        info = None if force else lookup_site_info(siteId, target_url)
        if info is None or force:
            info = refresh_site_info(siteId, url=target_url, force=True)
        items = [info] if info else []
        if info:
            logger.info("Returning site info site=%s url=%s", siteId, target_url)
        else:
            logger.warning("Site info not available site=%s url=%s", siteId, target_url)
        success_count = 1 if info else 0
        failure_count = 0 if info else 1
        return SiteInfoCollectionResponse(
            siteId=siteId,
            items=items,
            total=1,
            page=1,
            pageSize=1,
            successCount=success_count,
            failureCount=failure_count,
        )

    urls = _collect_site_urls(siteId, force_sitemap=force)
    paged_urls, total = _paginate_items(urls, page, pageSize)
    collected: Dict[str, SiteInfoResponse] = {}
    failure_count = 0
    for candidate in paged_urls:
        info = None if force else lookup_site_info(siteId, candidate)
        if info is None or force:
            info = refresh_site_info(siteId, url=candidate, force=True)
        if info:
            collected[candidate] = info
        else:
            failure_count += 1
    logger.info(
        "Returning aggregate site info site=%s count=%s force=%s",
        siteId,
        len(collected),
        force,
    )
    return SiteInfoCollectionResponse(
        siteId=siteId,
        items=list(collected.values()),
        total=total,
        page=max(page, 1),
        pageSize=max(pageSize, 1),
        successCount=len(collected),
        failureCount=failure_count,
    )


@router.post("/info", response_model=SiteInfoCollectionResponse)
def drag_site_info(payload: SiteInfoRequest) -> SiteInfoCollectionResponse:
    target_url = _resolve_optional_url(payload.siteId, payload.url)
    collected: Dict[str, SiteInfoResponse] = {}

    if target_url:
        logger.info("Refreshing site info site=%s url=%s", payload.siteId, target_url)
        info = refresh_site_info(payload.siteId, url=target_url, force=True)
        if info:
            collected[target_url] = info
        success_count = 1 if info else 0
        failure_count = 0 if info else 1
        return SiteInfoCollectionResponse(
            siteId=payload.siteId,
            items=list(collected.values()),
            total=1,
            page=1,
            pageSize=1,
            successCount=success_count,
            failureCount=failure_count,
        )

    urls = _collect_site_urls(payload.siteId, force_sitemap=True)
    logger.info(
        "Refreshing aggregate site info site=%s count=%s",
        payload.siteId,
        len(urls),
    )
    success_count = 0
    failure_count = 0
    for candidate in urls:
        info = refresh_site_info(payload.siteId, url=candidate, force=True)
        if info:
            collected[candidate] = info
            success_count += 1
        else:
            failure_count += 1
    return SiteInfoCollectionResponse(
        siteId=payload.siteId,
        items=[],
        total=len(urls),
        page=1,
        pageSize=max(len(urls), 1),
        successCount=success_count,
        failureCount=failure_count,
    )

# ------------------------------------------------------------------------
# /site/atlas (GET = fetch; POST = drag)
# ------------------------------------------------------------------------
@router.get("/atlas", response_model=SiteAtlasCollectionResponse)
def get_site_atlas(
    siteId: str,
    url: str | None = None,
    force: bool = False,
    page: int = 1,
    pageSize: int = 10,
) -> SiteAtlasCollectionResponse:
    target_url = _resolve_optional_url(siteId, url)
    collected: Dict[str, SiteAtlasResponse] = {}

    if target_url:
        atlas = None if force else get_site_atlas_response(siteId, target_url)
        if atlas is None or force:
            atlas = refresh_site_atlas(siteId, target_url, force=True)
        if atlas:
            collected[target_url] = atlas
            logger.info(
                "Returning site atlas site=%s url=%s force=%s",
                siteId,
                target_url,
                force,
            )
        else:
            logger.warning("Site atlas not available site=%s url=%s", siteId, target_url)
        success_count = 1 if target_url in collected else 0
        failure_count = 0 if success_count else 1
        return SiteAtlasCollectionResponse(
            siteId=siteId,
            items=list(collected.values()),
            total=1,
            page=1,
            pageSize=1,
            successCount=success_count,
            failureCount=failure_count,
        )

    urls = _collect_site_urls(siteId, force_sitemap=force)
    existing = {
        atlas.url: atlas for atlas in list_site_atlas_responses(siteId)
    }
    paged_urls, total = _paginate_items(urls, page, pageSize)
    failure_count = 0
    for candidate in paged_urls:
        atlas = None if force else existing.get(candidate)
        if atlas is None or force:
            atlas = refresh_site_atlas(siteId, candidate, force=True)
        if atlas:
            collected[candidate] = atlas
        else:
            failure_count += 1

    logger.info(
        "Returning aggregate site atlas site=%s count=%s force=%s",
        siteId,
        len(collected),
        force,
    )
    return SiteAtlasCollectionResponse(
        siteId=siteId,
        items=list(collected.values()),
        total=total,
        page=max(page, 1),
        pageSize=max(pageSize, 1),
        successCount=len(collected),
        failureCount=failure_count,
    )


@router.post("/atlas", response_model=SiteAtlasCollectionResponse)
def drag_site_atlas(payload: SiteAtlasRequest) -> SiteAtlasCollectionResponse:
    target_url = _resolve_optional_url(payload.siteId, payload.url)
    collected: Dict[str, SiteAtlasResponse] = {}

    if target_url:
        logger.info("Refreshing site atlas site=%s url=%s", payload.siteId, target_url)
        atlas = refresh_site_atlas(payload.siteId, target_url, force=True)
        if atlas:
            collected[target_url] = atlas
        success_count = 1 if atlas else 0
        failure_count = 0 if atlas else 1
        return SiteAtlasCollectionResponse(
            siteId=payload.siteId,
            items=list(collected.values()),
            total=1,
            page=1,
            pageSize=1,
            successCount=success_count,
            failureCount=failure_count,
        )

    urls = _collect_site_urls(payload.siteId, force_sitemap=True)
    logger.info(
        "Refreshing aggregate site atlas site=%s count=%s",
        payload.siteId,
        len(urls),
    )
    success_count = 0
    failure_count = 0
    for candidate in urls:
        atlas = refresh_site_atlas(payload.siteId, candidate, force=True)
        if atlas:
            collected[candidate] = atlas
            success_count += 1
        else:
            failure_count += 1
    return SiteAtlasCollectionResponse(
        siteId=payload.siteId,
        items=[],
        total=len(urls),
        page=1,
        pageSize=max(len(urls), 1),
        successCount=success_count,
        failureCount=failure_count,
    )
