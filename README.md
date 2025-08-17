# DomSphere

Monorepo powered by Nx.

## Projects (Nx)

apps/
web/ # Next.js app (site & dashboard)
api/ # FastAPI + LangServe backend (Python)

packages/
api-client/ # TypeScript types generated from /openapi.json
sdk/ # Embeddable widget (ESM/CJS + UMD)
shared/ # Shared TS utilities & types
ui/ # Shared React UI components

# (generated)

dist/ # build outputs

# (seen in workspace)

@domsphere/source # internal workspace target (ignore if unused)

⸻

## Prerequisites

• Node 18+ (LTS recommended)
• npm
• Python 3.11–3.13
• (Optional) nx globally: npm i -g nx (you can always use npx nx)

⸻

## Quick Start

# 1) Install JS deps

npm install

# 2) Create & activate Python venv for the API

cd apps/api
python -m venv .venv
. .venv/bin/activate

# 3) Install API deps (pin as you like)

pip install fastapi uvicorn[standard] langserve sse-starlette langchain pydantic python-multipart

Tip: When working in the repo root, you can always run Nx targets. The API command below uses the venv interpreter path explicitly so Nx can launch it.

⸻

## Development Commands

Start the backend (FastAPI)

nx serve api

    •	Exposes: http://localhost:4000
    •	Health: GET /health
    •	LangServe playground: /agent/playground/

Start the web app (Next.js)

nx serve web

    •	Exposes: http://localhost:3000

Generate API types (OpenAPI → TypeScript)

nx run api-client:codegen

    •	Requires the API to be running (reads http://localhost:4000/openapi.json).

Build the SDK (ESM+CJS) and UMD bundle

# ESM + CJS (Nx Rollup executor)

nx build sdk

# UMD bundle (separate rollup config)

nx run sdk:bundle-umd

# Everything (ESM+CJS + UMD)

nx run sdk:build-all

    •	Outputs land in: dist/packages/sdk/
    •	index.esm.js, index.cjs.js, umd/sdk.umd.js

Demo the SDK (UMD)

# Serve the UMD folder

npx http-server dist/packages/sdk/umd -p 8080 -c-1

# Open http://localhost:8080

    •	Demo page: dist/packages/sdk/umd/index.html
    •	Ensure the API is running (nx serve api).

⸻

## Environment & CORS (dev)

The SDK demo runs on http://localhost:8080. Allow it in FastAPI CORS:

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
CORSMiddleware,
allow_origins=[
"http://localhost:3000",
"http://127.0.0.1:3000",
"http://localhost:8080",
"http://127.0.0.1:8080",
],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)

You may also set window.DOMSPHERE_API_URL in the demo HTML to point the SDK at a specific API URL.

⸻

## Common Flows

• Fresh types for web build: nx run api-client:codegen && nx build web
• Run web + API separately: nx serve api (term A), nx serve web (term B)
• Rebuild SDK then test: nx run sdk:build-all && npx http-server dist/packages/sdk/umd -p 8080 -c-1

⸻

## Troubleshooting

• window.DomSphereSDK is not a constructor
• Ensure packages/sdk/src/index.ts exports default and assigns the UMD global:

export default DomSphereSDK;
(globalThis as any).DomSphereSDK = DomSphereSDK;

    •	Rebuild UMD: nx run sdk:bundle-umd and hard-reload the page.

    •	CORS errors in the browser
    •	Update CORSMiddleware origins to include your demo origin (8080).
    •	Disable caching in the static server: http-server -c-1.
    •	openapi-typescript fails (500)
    •	Make sure /openapi.json returns 200 by visiting http://localhost:4000/openapi.json.
    •	Keep LangServe routes out of schema if needed; provide clean typed endpoints under /v1/*.

⸻

## Nx Tips

• List all projects: nx show projects
• Show a project’s targets: nx show project <name>
• Visualize graph: npx nx graph
