from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from core.logging import get_api_logger

from .models import (
    Rule,
    Site,
    SiteAtlas,
    SiteEmbedding,
    SiteInfo,
    SiteMapPage,
    SitePage,
    SiteStyle,
)
from .session import session_scope

logger = get_api_logger(__name__)


def _ensure_site(session: Session, site_id: str) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        site = Site(site_id=site_id)
        session.add(site)
        session.flush()
        logger.debug("Created site record site_id=%s", site_id)
    return site


def get_site(site_id: str) -> Optional[Site]:
    with session_scope() as session:
        return session.get(Site, site_id)


def upsert_site(
    site_id: str,
    *,
    display_name: Optional[str] = None,
    parent_url: Optional[str] = None,
    rules_version: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Site:
    with session_scope() as session:
        site = session.get(Site, site_id)
        if site is None:
            site = Site(site_id=site_id)
            session.add(site)
        if display_name is not None:
            site.display_name = display_name
        if parent_url is not None:
            site.parent_url = parent_url
        if rules_version is not None:
            site.rules_version = rules_version
        if meta is not None:
            site.meta = dict(meta)
        session.flush()
        logger.debug("Upserted site site_id=%s", site_id)
        return site


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_site_pages(
    site_id: str,
    *,
    status: Optional[str] = None,
) -> List[SitePage]:
    with session_scope() as session:
        stmt: Select[SitePage] = select(SitePage).where(SitePage.site_id == site_id)
        if status:
            stmt = stmt.where(SitePage.status == status)
        stmt = stmt.order_by(SitePage.last_seen_at.desc())
        return list(session.execute(stmt).scalars())


def bulk_upsert_site_pages(
    site_id: str,
    pages: Sequence[dict],
    *,
    mark_missing: bool = True,
) -> Tuple[int, int]:
    if not pages:
        return 0, 0

    now = _now()
    seen_urls = {page.get("url") for page in pages if page.get("url")}
    seen_urls = {url for url in seen_urls if url}

    with session_scope() as session:
        _ensure_site(session, site_id)
        existing_stmt: Select[SitePage] = select(SitePage).where(SitePage.site_id == site_id)
        existing = {row.url: row for row in session.execute(existing_stmt).scalars()}
        touched = 0

        for page in pages:
            url = page.get("url")
            if not url:
                continue
            meta = page.get("meta")
            content_hash = page.get("content_hash")
            last_crawled_at = page.get("last_crawled_at") or now
            record = existing.get(url)
            if record is None:
                record = SitePage(
                    site_id=site_id,
                    url=url,
                    status="active",
                    meta=meta,
                    content_hash=content_hash,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_crawled_at=last_crawled_at,
                )
                session.add(record)
            else:
                record.status = "active"
                record.last_seen_at = now
                record.last_crawled_at = last_crawled_at
                if meta is not None:
                    record.meta = meta
                if content_hash is not None:
                    record.content_hash = content_hash
            touched += 1

        marked_gone = 0
        if existing and mark_missing:
            for url, record in existing.items():
                if url in seen_urls:
                    continue
                if record.status != "gone":
                    record.status = "gone"
                    record.updated_at = now
                    marked_gone += 1

        logger.info(
            "Upserted %s sitemap page(s) site_id=%s marked_gone=%s",
            touched,
            site_id,
            marked_gone,
        )
        return touched, marked_gone


def mark_site_pages_status(
    site_id: str,
    urls: Sequence[str],
    *,
    status: str,
) -> int:
    if not urls:
        return 0
    with session_scope() as session:
        stmt: Select[SitePage] = select(SitePage).where(
            SitePage.site_id == site_id,
            SitePage.url.in_(urls),
        ).with_for_update()
        rows = list(session.execute(stmt).scalars())
        for row in rows:
            row.status = status
            row.updated_at = _now()
        logger.debug("Marked %s site page(s) status=%s site_id=%s", len(rows), status, site_id)
        return len(rows)

def list_rules(site_id: str) -> List[Rule]:
    with session_scope() as session:
        stmt: Select[Rule] = select(Rule).where(Rule.site_id == site_id).order_by(Rule.created_at.asc())
        rules = list(session.execute(stmt).scalars())
        logger.debug("Loaded %s rules site_id=%s", len(rules), site_id)
        return rules


def get_rule(site_id: str, rule_id: str) -> Optional[Rule]:
    with session_scope() as session:
        stmt: Select[Rule] = select(Rule).where(Rule.site_id == site_id, Rule.id == rule_id)
        return session.execute(stmt).scalar_one_or_none()


def insert_rule(
    site_id: str,
    rule_id: str,
    rule_instruction: str,
    output_instruction: Optional[str],
    *,
    enabled: bool = True,
    tracking: bool = True,
    triggers: Optional[Sequence[dict]] = None,
) -> Rule:
    with session_scope() as session:
        _ensure_site(session, site_id)
        rule = Rule(
            id=rule_id,
            site_id=site_id,
            enabled=enabled,
            tracking=tracking,
            rule_instruction=rule_instruction,
            output_instruction=output_instruction,
            triggers=list(triggers or []),
        )
        session.add(rule)
        session.flush()
        logger.info("Inserted rule site_id=%s rule_id=%s", site_id, rule_id)
        return rule


def upsert_site_info_record(
    site_id: str,
    url: str,
    *,
    meta: Optional[dict] = None,
    normalized: Optional[dict] = None,
) -> SiteInfo:
    with session_scope() as session:
        _ensure_site(session, site_id)
        stmt: Select[SiteInfo] = (
            select(SiteInfo)
            .where(SiteInfo.site_id == site_id, SiteInfo.url == url)
            .with_for_update()
        )
        record = session.execute(stmt).scalar_one_or_none()
        if record is None:
            record = SiteInfo(site_id=site_id, url=url, meta=meta, normalized=normalized)
            session.add(record)
        else:
            record.meta = meta
            record.normalized = normalized
        session.flush()
        logger.info("Upserted site info site_id=%s url=%s", site_id, url)
        return record


def touch_site_page_info(site_id: str, url: str) -> None:
    with session_scope() as session:
        stmt: Select[SitePage] = (
            select(SitePage)
            .where(SitePage.site_id == site_id, SitePage.url == url)
            .with_for_update()
        )
        record = session.execute(stmt).scalar_one_or_none()
        if record is None:
            record = SitePage(
                site_id=site_id,
                url=url,
                status="active",
                first_seen_at=_now(),
                last_seen_at=_now(),
            )
            session.add(record)
        record.info_last_refreshed_at = _now()
        record.last_seen_at = _now()
        if record.status == "gone":
            record.status = "active"


def update_rule_fields(
    site_id: str,
    rule_id: str,
    *,
    enabled: Optional[bool] = None,
    tracking: Optional[bool] = None,
    rule_instruction: Optional[str] = None,
    output_instruction: Optional[str] = None,
) -> Optional[Rule]:
    with session_scope() as session:
        stmt: Select[Rule] = select(Rule).where(Rule.site_id == site_id, Rule.id == rule_id).with_for_update()
        rule = session.execute(stmt).scalar_one_or_none()
        if rule is None:
            logger.debug("update_rule_fields missing rule site_id=%s rule_id=%s", site_id, rule_id)
            return None
        if enabled is not None:
            rule.enabled = enabled
        if tracking is not None:
            rule.tracking = tracking
        if rule_instruction is not None:
            rule.rule_instruction = rule_instruction
        if output_instruction is not None:
            rule.output_instruction = output_instruction
        session.flush()
        logger.info("Updated rule site_id=%s rule_id=%s", site_id, rule_id)
        return rule


def update_rule_triggers(site_id: str, rule_id: str, triggers: Sequence[dict]) -> Optional[Rule]:
    with session_scope() as session:
        stmt: Select[Rule] = select(Rule).where(Rule.site_id == site_id, Rule.id == rule_id).with_for_update()
        rule = session.execute(stmt).scalar_one_or_none()
        if rule is None:
            logger.debug("update_rule_triggers missing rule site_id=%s rule_id=%s", site_id, rule_id)
            return None
        rule.triggers = list(triggers)
        session.flush()
        logger.info("Updated rule triggers site_id=%s rule_id=%s", site_id, rule_id)
        return rule


def get_site_style(site_id: str) -> Optional[SiteStyle]:
    with session_scope() as session:
        return session.get(SiteStyle, site_id)


def upsert_site_style(site_id: str, css: str) -> SiteStyle:
    with session_scope() as session:
        _ensure_site(session, site_id)
        style = session.get(SiteStyle, site_id)
        if style is None:
            style = SiteStyle(site_id=site_id, css=css)
            session.add(style)
        else:
            style.css = css
        session.flush()
        logger.info("Upserted site style site_id=%s", site_id)
        return style


def list_site_info(site_id: str) -> List[SiteInfo]:
    with session_scope() as session:
        stmt: Select[SiteInfo] = select(SiteInfo).where(SiteInfo.site_id == site_id)
        return list(session.execute(stmt).scalars())


def get_site_info(site_id: str, url: str) -> Optional[SiteInfo]:
    with session_scope() as session:
        stmt: Select[SiteInfo] = select(SiteInfo).where(
            SiteInfo.site_id == site_id,
            SiteInfo.url == url,
        )
        return session.execute(stmt).scalar_one_or_none()


def upsert_site_info(entries: Iterable[SiteInfo]) -> None:
    entries_list = list(entries)
    if not entries_list:
        return
    with session_scope() as session:
        for entry in entries_list:
            session.merge(entry)
        logger.info("Upserted %s site info entries", len(entries_list))


def list_site_map_pages(site_id: str) -> List[SiteMapPage]:
    with session_scope() as session:
        stmt: Select[SiteMapPage] = select(SiteMapPage).where(
            SiteMapPage.site_id == site_id
        ).order_by(SiteMapPage.created_at.asc())
        return list(session.execute(stmt).scalars())


def list_site_atlas(site_id: str) -> List[SiteAtlas]:
    with session_scope() as session:
        stmt: Select[SiteAtlas] = select(SiteAtlas).where(SiteAtlas.site_id == site_id)
        return list(session.execute(stmt).scalars())


def upsert_site_map_pages(site_id: str, pages: Sequence[dict], *, replace: bool = True) -> None:
    with session_scope() as session:
        _ensure_site(session, site_id)
        current_stmt: Select[SiteMapPage] = select(SiteMapPage).where(SiteMapPage.site_id == site_id)
        current = {row.url: row for row in session.execute(current_stmt).scalars()}
        urls_seen = set()
        for page in pages:
            url = page.get("url")
            if not url:
                continue
            urls_seen.add(url)
            meta = page.get("meta")
            existing = current.get(url)
            if existing:
                existing.meta = meta
            else:
                session.add(SiteMapPage(site_id=site_id, url=url, meta=meta))
        if replace:
            for url, obj in current.items():
                if url not in urls_seen:
                    session.delete(obj)
        logger.info(
            "Upserted sitemap pages site_id=%s count=%s replace=%s",
            site_id,
            len(urls_seen),
            replace,
        )


def list_site_embeddings(site_id: str) -> List[SiteEmbedding]:
    with session_scope() as session:
        stmt: Select[SiteEmbedding] = select(SiteEmbedding).where(SiteEmbedding.site_id == site_id)
        return list(session.execute(stmt).scalars())


def upsert_site_embedding(
    site_id: str,
    url: str,
    embedding: Sequence[float],
    text: str,
    meta: Optional[dict],
) -> SiteEmbedding:
    with session_scope() as session:
        _ensure_site(session, site_id)
        stmt: Select[SiteEmbedding] = select(SiteEmbedding).where(
            SiteEmbedding.site_id == site_id,
            SiteEmbedding.url == url,
        ).with_for_update()
        record = session.execute(stmt).scalar_one_or_none()
        if record is None:
            record = SiteEmbedding(
                site_id=site_id,
                url=url,
                embedding=list(embedding),
                text=text,
                meta=meta,
            )
            session.add(record)
        else:
            record.embedding = list(embedding)
            record.text = text
            record.meta = meta
        session.flush()
        logger.debug("Upserted embedding site_id=%s url=%s", site_id, url)
        return record


def touch_site_page_embedding(site_id: str, url: str) -> None:
    with session_scope() as session:
        stmt: Select[SitePage] = (
            select(SitePage)
            .where(SitePage.site_id == site_id, SitePage.url == url)
            .with_for_update()
        )
        record = session.execute(stmt).scalar_one_or_none()
        now = _now()
        if record is None:
            record = SitePage(
                site_id=site_id,
                url=url,
                status="active",
                first_seen_at=now,
                last_seen_at=now,
                embeddings_last_refreshed_at=now,
            )
            session.add(record)
        else:
            record.embeddings_last_refreshed_at = now
            record.last_seen_at = now
            if record.status == "gone":
                record.status = "active"


def get_site_atlas(site_id: str, url: str) -> Optional[SiteAtlas]:
    with session_scope() as session:
        stmt: Select[SiteAtlas] = select(SiteAtlas).where(
            SiteAtlas.site_id == site_id,
            SiteAtlas.url == url,
        )
        return session.execute(stmt).scalar_one_or_none()


def upsert_site_atlas(
    site_id: str,
    url: str,
    atlas: Optional[dict],
    queued: Optional[bool],
) -> SiteAtlas:
    with session_scope() as session:
        _ensure_site(session, site_id)
        stmt: Select[SiteAtlas] = select(SiteAtlas).where(
            SiteAtlas.site_id == site_id,
            SiteAtlas.url == url,
        ).with_for_update()
        record = session.execute(stmt).scalar_one_or_none()
        if record is None:
            record = SiteAtlas(site_id=site_id, url=url, atlas=atlas, queued_plan_rebuild=queued)
            session.add(record)
        else:
            record.atlas = atlas
            record.queued_plan_rebuild = queued
        session.flush()
        logger.debug("Upserted atlas site_id=%s url=%s", site_id, url)
        return record


def touch_site_page_atlas(site_id: str, url: str) -> None:
    with session_scope() as session:
        stmt: Select[SitePage] = (
            select(SitePage)
            .where(SitePage.site_id == site_id, SitePage.url == url)
            .with_for_update()
        )
        record = session.execute(stmt).scalar_one_or_none()
        now = _now()
        if record is None:
            record = SitePage(
                site_id=site_id,
                url=url,
                status="active",
                first_seen_at=now,
                last_seen_at=now,
                atlas_last_refreshed_at=now,
            )
            session.add(record)
        else:
            record.atlas_last_refreshed_at = now
            record.last_seen_at = now
            if record.status == "gone":
                record.status = "active"
