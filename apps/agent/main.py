from fastapi import FastAPI
from routes.health import router as health_router

app = FastAPI(title="Agent (Planner)", version="0.1.0")
app.include_router(health_router)
