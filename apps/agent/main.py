from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from routes.health import router as health_router
from runnables.agent import build_agent

app = FastAPI(title="Agent (Planner)", version="0.1.0")

# CORS for SDK (adjust origins later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
add_routes(app, build_agent(), path="/agent")
