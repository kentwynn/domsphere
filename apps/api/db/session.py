from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.logging import get_api_logger

logger = get_api_logger(__name__)

_DEFAULT_DATABASE_URL = "postgresql+psycopg://domsphere:domsphere@localhost:5432/domsphere"

_database_url = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)

engine = create_engine(
    _database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,
)

logger.info("Database engine configured url=%s", _database_url)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine():
    return engine
