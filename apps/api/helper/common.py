import math
import os
import re
from typing import Any, Dict, Optional, List, Sequence, Tuple

import numpy as np

from db.crud import (
    get_rule as db_get_rule,
    get_site_atlas as db_get_site_atlas,
    get_site_info as db_get_site_info,
    get_site_style as db_get_site_style,
    insert_rule as db_insert_rule,
    list_rules as db_list_rules,
    list_site_embeddings as db_list_site_embeddings,
    list_site_map_pages as db_list_site_map_pages,
    list_site_info as db_list_site_info,
    upsert_site_embedding as db_upsert_site_embedding,
    upsert_site_style as db_upsert_site_style,
    update_rule_fields as db_update_rule_fields,
    update_rule_triggers as db_update_rule_triggers,
)
from db.models import (
    Rule as RuleModel,
    SiteAtlas as SiteAtlasModel,
    SiteInfo as SiteInfoModel,
    SiteMapPage as SiteMapPageModel,
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
    pages = [_site_map_page_model_to_contract(page) for page in db_list_site_map_pages(site_id)]
    return SiteMapResponse(siteId=site_id, pages=pages)


def get_site_atlas_response(site_id: str, url: str) -> Optional[SiteAtlasResponse]:
    _ensure_db_ready()
    record = db_get_site_atlas(site_id, url)
    if record is None:
        return None
    return _site_atlas_model_to_response(record)


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
