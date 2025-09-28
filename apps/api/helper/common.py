import hashlib
import math
import os
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Sequence, Tuple, Set
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl

import httpx
import numpy as np
from bs4 import BeautifulSoup

from db.crud import (
    get_rule as db_get_rule,
    get_site as db_get_site,
    get_site_atlas as db_get_site_atlas,
    get_site_info as db_get_site_info,
    get_site_style as db_get_site_style,
    insert_rule as db_insert_rule,
    list_rules as db_list_rules,
    list_site_pages as db_list_site_pages,
    list_site_embeddings as db_list_site_embeddings,
    list_site_info as db_list_site_info,
    list_site_map_pages as db_list_site_map_pages,
    list_site_atlas as db_list_site_atlas,
    bulk_upsert_site_pages as db_bulk_upsert_site_pages,
    upsert_site_map_pages as db_upsert_site_map_pages,
    upsert_site as db_upsert_site,
    upsert_site_embedding as db_upsert_site_embedding,
    upsert_site_info_record as db_upsert_site_info_record,
    upsert_site_atlas as db_upsert_site_atlas,
    upsert_site_style as db_upsert_site_style,
    touch_site_page_info as db_touch_site_page_info,
    touch_site_page_atlas as db_touch_site_page_atlas,
    touch_site_page_embedding as db_touch_site_page_embedding,
    update_rule_fields as db_update_rule_fields,
    update_rule_triggers as db_update_rule_triggers,
)
from db.models import (
    Rule as RuleModel,
    SiteAtlas as SiteAtlasModel,
    SiteInfo as SiteInfoModel,
    SiteMapPage as SiteMapPageModel,
    SitePage as SitePageModel,
)
from db.utils import init_db

from contracts.client_api import (
    RuleCheckRequest,
    SiteMapResponse, SiteMapPage,
    SiteInfoResponse,
    SiteAtlasResponse,
)
from core.logging import get_api_logger

logger = get_api_logger(__name__)


AGENT_URL = os.getenv("AGENT_BASE_URL", "http://localhost:5001").rstrip("/")
AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT", "300"))
DEFAULT_SITEMAP_MAX_PAGES = max(1, int(os.getenv("SITEMAP_MAX_PAGES", "5000")))
SITEMAP_QUEUE_FANOUT = max(2, int(os.getenv("SITEMAP_QUEUE_FANOUT", "4")))
EMBED_BATCH_LIMIT = max(1, int(os.getenv("EMBED_BATCH_LIMIT", "100")))
logger.info("API proxy configured agent_url=%s timeout=%s", AGENT_URL, AGENT_TIMEOUT)


_DB_READY = False


def _ensure_db_ready() -> None:
    global _DB_READY
    if _DB_READY:
        return
    init_db()
    _DB_READY = True


def _rule_model_to_dict(rule: RuleModel) -> Dict[str, Any]:
    return {
        "id": rule.id,
        "enabled": bool(rule.enabled),
        "tracking": bool(rule.tracking),
        "ruleInstruction": rule.rule_instruction,
        "outputInstruction": rule.output_instruction,
        "triggers": list(rule.triggers or []),
    }


def _site_info_model_to_response(model: SiteInfoModel) -> SiteInfoResponse:
    return SiteInfoResponse(
        siteId=model.site_id,
        url=model.url,
        meta=model.meta,
        normalized=model.normalized,
    )


def _site_map_page_model_to_contract(model: SiteMapPageModel) -> SiteMapPage:
    return SiteMapPage(url=model.url, meta=model.meta)


def _site_atlas_model_to_response(model: SiteAtlasModel) -> SiteAtlasResponse:
    return SiteAtlasResponse(
        siteId=model.site_id,
        url=model.url,
        atlas=model.atlas,
        queuedPlanRebuild=model.queued_plan_rebuild,
    )


def _site_page_model_to_dict(model: SitePageModel) -> Dict[str, Any]:
    return {
        "url": model.url,
        "status": model.status,
        "firstSeenAt": model.first_seen_at.isoformat() if model.first_seen_at else None,
        "lastSeenAt": model.last_seen_at.isoformat() if model.last_seen_at else None,
        "lastCrawledAt": model.last_crawled_at.isoformat() if model.last_crawled_at else None,
        "infoLastRefreshedAt": model.info_last_refreshed_at.isoformat()
        if model.info_last_refreshed_at
        else None,
        "atlasLastRefreshedAt": model.atlas_last_refreshed_at.isoformat()
        if model.atlas_last_refreshed_at
        else None,
        "embeddingsLastRefreshedAt": model.embeddings_last_refreshed_at.isoformat()
        if model.embeddings_last_refreshed_at
        else None,
        "meta": model.meta,
    }


_NULL_BYTE = "\x00"


def _strip_null_bytes(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(_NULL_BYTE, "")
    if isinstance(value, list):
        return [_strip_null_bytes(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_null_bytes(val) for key, val in value.items()}
    return value


def _paginate_items(items: Sequence[Any], page: int, page_size: int) -> Tuple[List[Any], int]:
    page = max(page, 1)
    page_size = max(page_size, 1)
    total = len(items)
    start = (page - 1) * page_size
    if start >= total:
        return [], total
    end = start + page_size
    sliced = list(items[start:end])
    return sliced, total


_HTTP_HEADERS = {
    "User-Agent": os.getenv("API_FETCH_USER_AGENT", "DomSphereAPI/1.0"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _get_site(site_id: str):
    _ensure_db_ready()
    return db_get_site(site_id)


def _slugify_site_id_from_url(parent_url: str) -> str:
    parsed = urlparse(parent_url)
    host = parsed.netloc or parsed.path or parent_url
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", host.strip().lower()).strip("-")
    return slug or "site"


def register_site(
    site_id: Optional[str],
    *,
    parent_url: str,
    display_name: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    _ensure_db_ready()
    resolved_site_id = site_id or _slugify_site_id_from_url(parent_url)
    db_upsert_site(resolved_site_id, parent_url=parent_url, display_name=display_name, meta=meta)
    return resolved_site_id


def _normalize_internal_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    normalized_path = parsed.path or "/"
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    normalized_query = urlencode(query_items, doseq=True)
    normalized = parsed._replace(
        path=normalized_path,
        fragment="",
        params="",
        query=normalized_query,
    )
    if not normalized.query:
        normalized = normalized._replace(query="")
    return normalized.geturl()


def resolve_site_url(site_id: str, url: Optional[str]) -> Optional[str]:
    site = _get_site(site_id)
    base = getattr(site, "parent_url", None)
    candidate = url
    if candidate:
        try:
            parsed = urlparse(candidate)
        except Exception:
            logger.warning("Failed to parse url=%s for site=%s", candidate, site_id)
            return None
        if base and not parsed.scheme:
            candidate = urljoin(base.rstrip("/") + "/", candidate.lstrip("/"))
    else:
        candidate = base

    if not candidate:
        return None

    normalized = _normalize_internal_url(candidate)
    if not normalized:
        return None

    if base:
        parent_host = urlparse(base).hostname
        resolved_host = urlparse(normalized).hostname
        if parent_host and resolved_host and resolved_host != parent_host:
            logger.warning(
                "Resolved URL host mismatch site=%s resolved=%s parent=%s",
                site_id,
                normalized,
                base,
            )
            return None
    return normalized


def _fetch_html(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        with httpx.Client(timeout=AGENT_TIMEOUT, headers=_HTTP_HEADERS) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as exc:
        logger.warning("Failed to fetch url=%s: %s", url, exc)
        return None


def _extract_meta_from_soup(url: str, soup: BeautifulSoup) -> Dict[str, Any]:
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    desc = None
    keywords = None
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property")
        if not name:
            continue
        name_lower = name.lower()
        if desc is None and name_lower in {"description", "og:description"}:
            desc = meta.get("content")
        if keywords is None and name_lower == "keywords":
            keywords = meta.get("content")
    meta: Dict[str, Any] = {"url": url}
    if title:
        meta["title"] = title
    if desc:
        meta["description"] = desc
    if keywords:
        meta["keywords"] = keywords
    return meta


def _normalize_metadata(meta: Dict[str, Any], url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    normalized: Dict[str, Any] = {
        "path": parsed.path or "/",
        "hostname": parsed.hostname,
    }
    if "title" in meta:
        normalized["title"] = meta["title"]
    if "description" in meta:
        normalized["description"] = meta["description"]
    return normalized


def _css_path(node: Any) -> Optional[str]:
    segments: List[str] = []
    current = node
    while current is not None and getattr(current, "name", None):
        segment = current.name
        node_id = current.attrs.get("id") if hasattr(current, "attrs") else None
        classes = current.attrs.get("class") if hasattr(current, "attrs") else None
        if node_id:
            segment += f"#{node_id}"
        elif classes:
            segment += "." + ".".join(classes)
        segments.append(segment)
        current = current.parent
    if not segments:
        return None
    return " ".join(reversed(segments))


def _build_dom_atlas(site_id: str, url: str, soup: BeautifulSoup, html: str) -> Dict[str, Any]:
    elements: List[Dict[str, Any]] = []
    node_index: Dict[int, int] = {}
    for idx, node in enumerate(soup.find_all(True, limit=200)):
        attrs = getattr(node, "attrs", {})
        class_list = attrs.get("class")
        role = attrs.get("role")
        data_attrs = {k: v for k, v in attrs.items() if isinstance(k, str) and k.startswith("data-")}
        text_sample = node.get_text(strip=True) if hasattr(node, "get_text") else None
        parent_idx = None
        parent = node.parent
        while parent is not None and getattr(parent, "name", None):
            parent_idx = node_index.get(id(parent))
            if parent_idx is not None:
                break
            parent = parent.parent
        element = _strip_null_bytes({
            "idx": idx,
            "tag": node.name,
            "id": attrs.get("id"),
            "classList": class_list,
            "role": role,
            "dataAttrs": data_attrs or None,
            "textSample": (text_sample[:160] if text_sample else None),
            "cssPath": _css_path(node),
            "parentIdx": parent_idx,
        })
        elements.append(element)
        node_index[id(node)] = idx

    atlas_payload = _strip_null_bytes({
        "atlasId": f"atlas-{hashlib.sha1(f'{site_id}:{url}'.encode('utf-8')).hexdigest()[:16]}",
        "siteId": site_id,
        "url": url,
        "domHash": hashlib.sha1(html.encode("utf-8", errors="ignore")).hexdigest(),
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "elementCount": len(elements),
        "elements": elements,
    })
    return atlas_payload


def store_site_map_pages(
    site_id: str,
    pages: List[SiteMapPage],
    *,
    mark_missing: bool = True,
) -> None:
    if not pages:
        return
    payload = [{"url": page.url, "meta": page.meta} for page in pages]
    db_upsert_site_map_pages(site_id, payload, replace=mark_missing)
    db_bulk_upsert_site_pages(
        site_id,
        [
            {
                "url": page.url,
                "meta": page.meta,
                "content_hash": (page.meta or {}).get("hash") if page.meta else None,
                "last_crawled_at": datetime.now(timezone.utc),
            }
            for page in pages
        ],
        mark_missing=mark_missing,
    )


def refresh_site_info(
    site_id: str,
    *,
    url: Optional[str] = None,
    force: bool = False,
) -> Optional[SiteInfoResponse]:
    target_url = resolve_site_url(site_id, url)
    if not target_url:
        logger.warning("Site info refresh missing target url site=%s", site_id)
        return None

    _ensure_db_ready()
    existing = None if force else db_get_site_info(site_id, target_url)
    if existing and not force:
        return _site_info_model_to_response(existing)

    html = _fetch_html(target_url)
    if html is None:
        if existing:
            return _site_info_model_to_response(existing)
        return None

    soup = BeautifulSoup(html, "html.parser")
    meta = _extract_meta_from_soup(target_url, soup)
    normalized = _normalize_metadata(meta, target_url)
    record = db_upsert_site_info_record(site_id, target_url, meta=meta, normalized=normalized)
    db_touch_site_page_info(site_id, target_url)
    return _site_info_model_to_response(record)


def generate_site_map(
    site_id: str,
    *,
    start_url: str,
    depth: Optional[int] = None,
    limit: Optional[int] = None,
    mark_missing: bool = True,
) -> SiteMapResponse:
    max_depth = depth if depth is not None else math.inf
    max_pages = max(1, limit) if limit is not None else DEFAULT_SITEMAP_MAX_PAGES
    queue_budget = max(SITEMAP_QUEUE_FANOUT * 2, max_pages * SITEMAP_QUEUE_FANOUT)

    normalized_start = _normalize_internal_url(start_url)
    if not normalized_start:
        return SiteMapResponse(siteId=site_id, pages=[])

    parsed_base = urlparse(normalized_start)
    base_netloc = parsed_base.netloc
    seen: Set[str] = set()
    queue: deque[Tuple[str, int]] = deque([(normalized_start, 0)])

    pages: List[SiteMapPage] = []

    while queue and len(pages) < max_pages:
        current, level = queue.popleft()
        if current in seen:
            continue
        seen.add(current)

        html = _fetch_html(current)
        if html is None:
            continue

        soup = BeautifulSoup(html, "html.parser")
        meta = _extract_meta_from_soup(current, soup)
        page_meta = {k: v for k, v in meta.items() if k != "url"}
        page_meta["hash"] = hashlib.sha1(html.encode("utf-8", errors="ignore")).hexdigest()
        pages.append(SiteMapPage(url=current, meta=page_meta or None))

        if level >= max_depth:
            continue

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href:
                continue
            candidate = urljoin(current, href)
            candidate = _normalize_internal_url(candidate)
            if not candidate:
                continue
            parsed_candidate = urlparse(candidate)
            if parsed_candidate.scheme not in {"http", "https"}:
                continue
            if parsed_candidate.netloc != base_netloc:
                continue
            if candidate in seen:
                continue
            if len(queue) >= queue_budget:
                continue
            queue.append((candidate, level + 1))

    store_site_map_pages(site_id, pages, mark_missing=mark_missing)
    return SiteMapResponse(siteId=site_id, pages=pages)


def refresh_site_atlas(site_id: str, url: str, *, force: bool = False) -> Optional[SiteAtlasResponse]:
    _ensure_db_ready()
    existing = None if force else db_get_site_atlas(site_id, url)
    if existing and not force:
        return _site_atlas_model_to_response(existing)

    html = _fetch_html(url)
    if html is None:
        if existing:
            return _site_atlas_model_to_response(existing)
        return None

    soup = BeautifulSoup(html, "html.parser")
    atlas_payload = _build_dom_atlas(site_id, url, soup, html)
    record = db_upsert_site_atlas(site_id, url, atlas_payload, queued=False)
    db_touch_site_page_atlas(site_id, url)
    return _site_atlas_model_to_response(record)


def get_site_style(site_id: str) -> Tuple[Optional[str], Optional[str]]:
    _ensure_db_ready()
    style = db_get_site_style(site_id)
    if style is None:
        return None, None
    return style.css, style.updated_at.isoformat()


def store_site_style(site_id: str, css: str) -> str:
    _ensure_db_ready()
    style = db_upsert_site_style(site_id, css)
    return style.updated_at.isoformat()


def get_site_map_response(site_id: str) -> SiteMapResponse:
    _ensure_db_ready()
    page_models = db_list_site_pages(site_id, status="active")
    if page_models:
        pages = [SiteMapPage(url=record.url, meta=record.meta) for record in page_models]
    else:
        pages = [_site_map_page_model_to_contract(page) for page in db_list_site_map_pages(site_id)]
    return SiteMapResponse(siteId=site_id, pages=pages)


def list_site_pages_payload(site_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    _ensure_db_ready()
    records = db_list_site_pages(site_id, status=status)
    if records:
        return [_site_page_model_to_dict(record) for record in records]
    # Fallback to legacy sitemap entries if inventory not yet populated
    legacy = db_list_site_map_pages(site_id)
    return [
        {
            "url": item.url,
            "status": "active",
            "firstSeenAt": None,
            "lastSeenAt": None,
            "lastCrawledAt": None,
            "infoLastRefreshedAt": None,
            "atlasLastRefreshedAt": None,
            "embeddingsLastRefreshedAt": None,
            "meta": item.meta,
        }
        for item in legacy
    ]


def get_site_atlas_response(site_id: str, url: str) -> Optional[SiteAtlasResponse]:
    _ensure_db_ready()
    record = db_get_site_atlas(site_id, url)
    if record is None:
        return None
    return _site_atlas_model_to_response(record)


def list_site_atlas_responses(site_id: str) -> List[SiteAtlasResponse]:
    _ensure_db_ready()
    return [_site_atlas_model_to_response(row) for row in db_list_site_atlas(site_id)]


def list_site_info_responses(site_id: str) -> List[SiteInfoResponse]:
    _ensure_db_ready()
    return [_site_info_model_to_response(info) for info in db_list_site_info(site_id)]


def lookup_site_info(site_id: str, url: str) -> Optional[SiteInfoResponse]:
    _ensure_db_ready()
    record = db_get_site_info(site_id, url)
    if record is None:
        return None
    return _site_info_model_to_response(record)


def build_page_embedding_text(
    site_id: str,
    page: SiteMapPage,
) -> Tuple[str, Dict[str, Any]]:
    """Combine sitemap and site info metadata into a single embedding text payload."""
    info = lookup_site_info(site_id, page.url)
    merged_meta: Dict[str, Any] = {}
    if isinstance(page.meta, dict):
        merged_meta.update(page.meta)
    if info and isinstance(info.meta, dict):
        for key, value in info.meta.items():
            if value is not None:
                merged_meta.setdefault(key, value)

    text_parts: List[str] = [page.url]
    for value in merged_meta.values():
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, (list, tuple)):
            text_parts.extend(str(v) for v in value if v is not None)
        elif isinstance(value, dict):
            text_parts.extend(str(v) for v in value.values() if v is not None)
        elif value is not None:
            text_parts.append(str(value))

    text = "\n".join(part for part in text_parts if part)
    return text, merged_meta


def _vector_to_numpy(vector: Optional[Sequence[float]]) -> np.ndarray:
    """Convert arbitrary sequence input into a 1-D float32 numpy array."""
    if vector is None or isinstance(vector, (str, bytes)):
        return np.array([], dtype=np.float32)
    if isinstance(vector, Sequence):
        seq = list(vector)
    else:  # pragma: no cover - defensive
        try:
            seq = list(vector)
        except TypeError:
            return np.array([], dtype=np.float32)
    if not seq:
        return np.array([], dtype=np.float32)
    try:
        arr = np.asarray(seq, dtype=np.float32)
    except (TypeError, ValueError):
        return np.array([], dtype=np.float32)
    arr = np.reshape(arr, (-1,))
    return np.where(np.isfinite(arr), arr, 0.0)


def _normalize_numpy(vector: Optional[Sequence[float]]) -> np.ndarray:
    """Return a normalized float32 numpy vector (cosine-safe)."""
    arr = _vector_to_numpy(vector)
    if arr.size == 0:
        return arr
    norm = float(np.linalg.norm(arr))
    if not math.isfinite(norm) or norm == 0.0:
        return arr
    return arr / norm


def _normalize_to_list(vector: Optional[Sequence[float]]) -> List[float]:
    normalized = _normalize_numpy(vector)
    if normalized.size == 0:
        return []
    return [float(x) for x in normalized]


def store_site_embedding(
    site_id: str,
    url: str,
    embedding: Sequence[float],
    *,
    text: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    _ensure_db_ready()
    normalized = _normalize_to_list(embedding)
    db_upsert_site_embedding(
        site_id=site_id,
        url=url,
        embedding=normalized,
        text=text,
        meta=meta or {},
    )
    db_touch_site_page_embedding(site_id, url)


def get_site_embeddings(site_id: str) -> Dict[str, Dict[str, Any]]:
    _ensure_db_ready()
    records = db_list_site_embeddings(site_id)
    out: Dict[str, Dict[str, Any]] = {}
    for record in records:
        out[record.url] = {
            "embedding": list(record.embedding or []),
            "text": record.text,
            "meta": record.meta or {},
        }
    return out


def search_site_embeddings(
    site_id: str,
    query_embedding: Sequence[float],
    *,
    top_k: int = 3,
) -> List[Tuple[str, float, Dict[str, Any]]]:
    if top_k <= 0:
        return []

    query_vector = _normalize_numpy(query_embedding)
    if query_vector.size == 0:
        return []

    records = get_site_embeddings(site_id)
    if not records:
        return []

    urls: List[str] = []
    payloads: List[Dict[str, Any]] = []
    vectors: List[np.ndarray] = []
    expected_dim = query_vector.shape[0]

    for url, payload in records.items():
        embedding = payload.get("embedding")
        normalized = _normalize_numpy(embedding)
        if normalized.size == 0 or normalized.shape[0] != expected_dim:
            continue
        payload["embedding"] = [float(x) for x in normalized]
        urls.append(url)
        payloads.append(payload)
        vectors.append(normalized)

    if not vectors:
        return []

    matrix = np.vstack(vectors)
    scores = matrix @ query_vector
    limit = min(top_k, scores.shape[0])

    if limit <= 0:
        return []

    top_indices = np.argpartition(-scores, limit - 1)[:limit]
    ordered = top_indices[np.argsort(scores[top_indices])[::-1]]

    results: List[Tuple[str, float, Dict[str, Any]]] = []
    for idx in ordered:
        results.append((urls[idx], float(scores[idx]), payloads[idx]))
    return results

# AgentRuleResponse instance not needed; persisted rules store agent-style JSON

def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if hasattr(cur, part):
            cur = getattr(cur, part)
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        return None
    return cur

def _op_eval(left: Any, op: str, right: Any) -> bool:
    try:
        if op == "equals": return left == right
        if op == "eq": return left == right
        if op == "in": return left in right if isinstance(right, (list, tuple, set)) else False
        if op == "gt": return left is not None and right is not None and left > right
        if op == "gte": return left is not None and right is not None and left >= right
        if op == "lt": return left is not None and right is not None and left < right
        if op == "lte": return left is not None and right is not None and left <= right
        if op == "contains":
            if isinstance(left, str) and isinstance(right, str):
                return right in left
            if isinstance(left, (list, tuple, set)):
                return right in left
            return False
        if op == "between":
            if isinstance(right, (list, tuple)) and len(right) == 2:
                lo, hi = right
                return left is not None and lo <= left <= hi
            return False
        if op == "regex":
            return bool(re.search(str(right), str(left)))
    except Exception:
        return False
    return False

def _rule_matches(rule: Dict[str, Any], payload: RuleCheckRequest) -> bool:
    allowed = rule.get("eventType")
    evt_type = getattr(payload.event, "type", None) or "unknown"
    if allowed and str(evt_type) not in set(map(str, allowed)):
        logger.debug("Rule match skipped rule=%s event=%s (not allowed)", rule.get("id"), evt_type)
        return False
    scope = {
        "event": payload.event,
        "telemetry": getattr(payload.event, "telemetry", None),
        "context": {},
    }
    for cond in rule.get("when", []):
        field, op, val = cond["field"], cond["op"], cond["value"]
        if field.startswith("event."):
            left = _get_path(scope, field)
        else:
            left = _get_path(scope, field) or _get_path(payload, field) or _get_path(payload.event, field)
        if isinstance(left, str) and left.isdigit():
            left = int(left)
        if _op_eval(left, op, val) is False:
            logger.debug(
                "Rule condition failed rule=%s field=%s op=%s left=%s right=%s",
                rule.get("id"),
                field,
                op,
                left,
                val,
            )
            return False
    logger.debug("Rule matched rule=%s event=%s", rule.get("id"), evt_type)
    return True


def _fwd_headers(xcv: Optional[str], xrid: Optional[str]) -> Dict[str, str]:
    h: Dict[str, str] = {}
    if xcv: h["X-Contract-Version"] = xcv
    if xrid: h["X-Request-Id"] = xrid
    return h


# ----------------------------------------------------------------------------
# Rule helpers used by routes
# ----------------------------------------------------------------------------

def update_rule_fields(
    site_id: str,
    rule_id: str,
    *,
    enabled: Optional[bool] = None,
    tracking: Optional[bool] = None,
    ruleInstruction: Optional[str] = None,
    outputInstruction: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    _ensure_db_ready()
    updated = db_update_rule_fields(
        site_id=site_id,
        rule_id=rule_id,
        enabled=enabled,
        tracking=tracking,
        rule_instruction=ruleInstruction,
        output_instruction=outputInstruction,
    )
    if updated is None:
        return None
    return _rule_model_to_dict(updated)


def list_rules(siteId: str) -> List[Dict[str, Any]]:
    _ensure_db_ready()
    rules = db_list_rules(siteId)
    return [_rule_model_to_dict(rule) for rule in rules]


def get_rule(site_id: str, rule_id: str) -> Optional[Dict[str, Any]]:
    _ensure_db_ready()
    record = db_get_rule(site_id, rule_id)
    if record is None:
        return None
    return _rule_model_to_dict(record)


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return s or "rule"


def create_rule(site_id: str, rule_instruction: str, output_instruction: Optional[str] = None) -> Dict[str, Any]:
    _ensure_db_ready()
    base_id = _slugify(rule_instruction)[:24]
    rid = base_id or "rule"
    existing_ids = {r.id for r in db_list_rules(site_id)}
    idx = 1
    cand = rid
    while cand in existing_ids:
        idx += 1
        cand = f"{rid}_{idx}"
    rule_model = db_insert_rule(
        site_id=site_id,
        rule_id=cand,
        rule_instruction=rule_instruction,
        output_instruction=output_instruction,
        enabled=True,
        tracking=True,
        triggers=[],
    )
    logger.info("Created rule site=%s rule=%s", site_id, cand)
    return _rule_model_to_dict(rule_model)


def update_rule_triggers(site_id: str, rule_id: str, triggers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    _ensure_db_ready()
    updated = db_update_rule_triggers(site_id, rule_id, triggers)
    if updated is None:
        return None
    return _rule_model_to_dict(updated)
