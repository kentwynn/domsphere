from __future__ import annotations

from core.logging import get_api_logger

from .models import Base
from .session import engine

logger = get_api_logger(__name__)


def init_db() -> None:
    """Create database tables if they are missing."""
    logger.info("Ensuring database schema is created")
    Base.metadata.create_all(bind=engine)
