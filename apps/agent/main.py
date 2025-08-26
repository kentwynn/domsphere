from fastapi import FastAPI
from core.config import wire_common
from routes.health import router as health_router
from routes.rule import router as rule_router
from routes.step import router as step_router
from routes.suggestion import router as suggestion_router

app = FastAPI()
wire_common(app)

# Mount routers
app.include_router(health_router)
app.include_router(rule_router)
app.include_router(step_router)
app.include_router(suggestion_router)
