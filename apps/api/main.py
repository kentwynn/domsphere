from __future__ import annotations
from fastapi import FastAPI

from core.config import wire_common
from routes.health import router as health_router
from routes.rule import router as rule_router
from routes.suggest import router as suggest_router
from routes.site import router as site_router

app = FastAPI()
wire_common(app)

app.include_router(health_router)
app.include_router(rule_router)
app.include_router(suggest_router)
app.include_router(site_router)

