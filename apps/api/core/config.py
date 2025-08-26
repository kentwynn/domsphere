from __future__ import annotations
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from contracts.version import CONTRACT_VERSION

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

def wire_common(app: FastAPI) -> None:
    app.title = "DomSphere API"
    app.version = CONTRACT_VERSION
    app.docs_url = "/docs"
    app.redoc_url = "/redoc"
    app.openapi_url = "/openapi.json"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
