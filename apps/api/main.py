from __future__ import annotations
from fastapi import FastAPI

from core.config import wire_common
from core.logging import get_api_logger
from routes.health import router as health_router
from routes.rule import router as rule_router
from routes.suggest import router as suggest_router
from routes.site import router as site_router
from routes.sdk import router as sdk_router

logger = get_api_logger(__name__)

app = FastAPI()
logger.info("Initializing DomSphere API app")
wire_common(app)
logger.debug("Common wiring complete")

app.include_router(health_router)
app.include_router(rule_router)
app.include_router(suggest_router)
app.include_router(site_router)
app.include_router(sdk_router)
logger.info("Registered API routers: health, rule, suggest, site, sdk")
