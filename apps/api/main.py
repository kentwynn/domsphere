from __future__ import annotations
from fastapi import FastAPI

from core.config import wire_common
from routes.health import router as health_router
from routes.rule import router as rule_router
from routes.suggest import router as suggest_router
from routes.drag import router as drag_router
from routes.mock_routes import router as mock_route

app = FastAPI()
wire_common(app)

# Mount routers
# app.include_router(health_router)
# app.include_router(rule_router)
# app.include_router(suggest_router)
# app.include_router(drag_router)

app.include_router(mock_route)
