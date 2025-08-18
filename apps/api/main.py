from fastapi import FastAPI
from routes.health import router as health_router
from routes.agent import router as agent_router
from routes.sites import router as sites_router
from routes.usage import router as usage_router
from routes.auth import router as auth_router  # optional

app = FastAPI(title="DomSphere API", version="0.1.0")

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(agent_router,  prefix="/api/v1/agent", tags=["agent"])
app.include_router(sites_router,  prefix="/api/v1/sites", tags=["sites"])
app.include_router(usage_router,  prefix="/api/v1/usage", tags=["usage"])
app.include_router(auth_router,   prefix="/api/v1/auth",  tags=["auth"])
