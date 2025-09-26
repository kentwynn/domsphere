from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class Site(TimestampMixin, Base):
    __tablename__ = "sites"

    site_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    parent_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rules_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    rules = relationship("Rule", back_populates="site", cascade="all, delete-orphan")
    style = relationship("SiteStyle", back_populates="site", uselist=False, cascade="all, delete-orphan")
    infos = relationship("SiteInfo", back_populates="site", cascade="all, delete-orphan")
    sitemap_pages = relationship("SiteMapPage", back_populates="site", cascade="all, delete-orphan")
    embeddings = relationship("SiteEmbedding", back_populates="site", cascade="all, delete-orphan")
    atlas_entries = relationship("SiteAtlas", back_populates="site", cascade="all, delete-orphan")


class SiteStyle(TimestampMixin, Base):
    __tablename__ = "site_styles"

    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"),
        primary_key=True,
    )
    css: Mapped[str] = mapped_column(Text, nullable=False)

    site = relationship("Site", back_populates="style")


class Rule(TimestampMixin, Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tracking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rule_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    output_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    site = relationship("Site", back_populates="rules")


class SiteInfo(TimestampMixin, Base):
    __tablename__ = "site_info"
    __table_args__ = (
        UniqueConstraint("site_id", "url", name="uq_site_info_site_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    normalized: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    site = relationship("Site", back_populates="infos")


class SiteMapPage(TimestampMixin, Base):
    __tablename__ = "site_map_pages"
    __table_args__ = (
        UniqueConstraint("site_id", "url", name="uq_site_map_site_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    site = relationship("Site", back_populates="sitemap_pages")


class SiteEmbedding(TimestampMixin, Base):
    __tablename__ = "site_embeddings"
    __table_args__ = (
        UniqueConstraint("site_id", "url", name="uq_site_embedding_site_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    site = relationship("Site", back_populates="embeddings")


class SiteAtlas(TimestampMixin, Base):
    __tablename__ = "site_atlas"
    __table_args__ = (
        UniqueConstraint("site_id", "url", name="uq_site_atlas_site_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.site_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    atlas: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    queued_plan_rebuild: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    site = relationship("Site", back_populates="atlas_entries")
