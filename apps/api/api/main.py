from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from .chains import echo_chain, InvokeInput, InvokeOutput

app = FastAPI(title="DomSphere API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1) Mount LangServe for playground/dev
add_routes(app, echo_chain, path="/agent")

# 2) Hide LangServe endpoints from OpenAPI (workaround for Pydantic v2/py3.13 issue)
for route in app.routes:
    try:
        if getattr(route, "path", "").startswith("/agent"):
            route.include_in_schema = False
    except Exception:
        pass

# 3) Provide a clean, typed FastAPI endpoint for codegen
@app.post("/v1/agent/invoke", response_model=InvokeOutput)
def invoke_simple(body: InvokeInput) -> InvokeOutput:
    return InvokeOutput(output=f"DomSphere echo: {body.input}")

@app.get("/health")
def health():
    return {"status": "ok"}
