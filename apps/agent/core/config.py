from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contracts.version import CONTRACT_VERSION

def _env_suffix() -> str:
    return (
        os.getenv("BUILD_ENV")
        or os.getenv("ENV")
        or os.getenv("NX_TASK_TARGET_CONFIGURATION")
        or ("development" if os.getenv("NODE_ENV") == "development" else "local")
    )

def _load_env() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    load_dotenv(os.path.join(repo_root, f".env.build.{_env_suffix()}"))

_load_env()

def _list(key: str) -> list[str]:
    val = os.getenv(key, "")
    return [v.strip() for v in val.split(",") if v.strip()]

AGENT_ALLOWED_ORIGINS = _list("AGENT_ALLOWED_ORIGINS")

def wire_common(app: FastAPI) -> None:
    app.title = "DomSphere Agent"
    app.version = CONTRACT_VERSION
    app.docs_url = "/docs"
    app.redoc_url = "/redoc"
    app.openapi_url = "/openapi.json"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=AGENT_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
