from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contracts.version import CONTRACT_VERSION
from .logging import get_api_logger

logger = get_api_logger(__name__)

def _env_suffix() -> str:
    # Pick one that’s present; default to local
    suffix = (
        os.getenv("BUILD_ENV")
        or os.getenv("ENV")
        or os.getenv("NX_TASK_TARGET_CONFIGURATION")
        or ("development" if os.getenv("NODE_ENV") == "development" else "local")
    )
    logger.debug("Resolved environment suffix=%s", suffix)
    return suffix

def _load_env() -> None:
    suffix = _env_suffix()
    # repo root relative to this file
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    env_path = os.path.join(repo_root, f".env.build.{suffix}")
    loaded = load_dotenv(env_path)
    if loaded:
        logger.info("Loaded API environment from %s", env_path)
    else:
        logger.debug("No API env file found at %s", env_path)

_load_env()

def _list(key: str) -> list[str]:
    val = os.getenv(key, "")
    return [v.strip() for v in val.split(",") if v.strip()]

API_ALLOWED_ORIGINS = _list("API_ALLOWED_ORIGINS")

def wire_common(app: FastAPI) -> None:
    app.title = "DomSphere API"
    app.version = CONTRACT_VERSION
    app.docs_url = "/docs"
    app.redoc_url = "/redoc"
    app.openapi_url = "/openapi.json"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=API_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(
        "Configured FastAPI instance origins=%s",
        API_ALLOWED_ORIGINS if API_ALLOWED_ORIGINS else "*",
    )
