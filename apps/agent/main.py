# apps/agent/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from pydantic import BaseModel, Field
from typing import Dict, Any, Literal

from runnables.agent import build_agent
class PlanRequest(BaseModel):
    url: str = Field(examples=["https://shop.example.com/products"])
    intent: str = Field(examples=["buy_with_coupon"])
    atlasVersion: str = "demo"
    domSnapshot: Dict[str, Any] = Field(default_factory=dict)
    doNotStore: bool = False

class PlanResponse(BaseModel):
    sessionId: str
    agentVersion: str
    planId: str
    cache: Literal["HIT", "MISS"]
    plan: Dict[str, Any]   # keep generic for now

app = FastAPI(
    title="Agent (Planner)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


runnable = build_agent().with_types(input_type=PlanRequest, output_type=PlanResponse)
add_routes(app, runnable, path="/agent")
