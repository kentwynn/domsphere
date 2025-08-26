# DomSphere

DomSphere is a full-stack platform for building, deploying, and sharing intelligent web agents—combining a modern Next.js frontend, a FastAPI backend powered by LangServe, and a robust SDK for seamless integration. The project uses a monorepo (managed by Nx) to unify all core apps and packages, enabling tight integration, shared code, and streamlined development across the web UI, backend API, SDK, and reusable UI components.

---

### Project Structure

**apps/**

- `web/` — Next.js app (site & dashboard)
- `api/` — FastAPI + LangServe backend (Python)

**packages/**

- `contracts/` — Shared Python models (Pydantic) used by both `api` and `agent`
- `sdk/` — Embeddable widget (ESM/CJS + UMD)
- `ui/` — Shared React UI components

**(generated)**

- `dist/` — build outputs

**(seen in workspace)**

- `domsphere` — internal workspace target (ignore if unused)

---

### Prerequisites

- Node.js 18+ (LTS recommended)
- npm
- Python 3.11–3.13
- _(Optional)_ Nx CLI globally:
  ```sh
  npm i -g nx
  ```
  You can always use `npx nx` if you prefer not to install globally.

---

### Quick Start

#### 1. Install JavaScript dependencies

- In the repo root:
  ```sh
  npm install
  ```

#### 2. Create & activate a Python virtual environment for the API

- In the API directory:
  ```sh
  cd apps/api
  python -m venv .venv
  . .venv/bin/activate
  ```

#### 3. Install API dependencies

- With the venv activated:
  ```sh
  pip install fastapi uvicorn[standard] langserve sse-starlette langchain pydantic python-multipart
  ```
  _(Pin versions as you like.)_

> **Tip:** From the repo root, you can run Nx targets. When running API commands, the venv interpreter path is used so Nx can launch it.

---

### Development Commands

#### Start the backend (FastAPI)

- Run:
  ```sh
  nx serve api
  ```
  - Exposes: http://localhost:4000
  - Health check: `GET /health`
  - LangServe playground: `/agent/playground/`

#### Start the web app (Next.js)

- Run:
  ```sh
  nx serve web
  ```
  - Exposes: http://localhost:3000

#### Generate API types (OpenAPI → TypeScript)

- Run:
  ```sh
  nx run api-client:codegen
  ```
  - Requires the API to be running (reads from `http://localhost:4000/openapi.json`).

#### Build the SDK (ESM + CJS and UMD)

- ESM + CJS (Nx Rollup executor):
  ```sh
  nx build sdk
  ```
- UMD bundle (separate Rollup config):
  ```sh
  nx run sdk:bundle-umd
  ```
- Everything (ESM + CJS + UMD):
  ```sh
  nx run sdk:build-all
  ```
  - Outputs are in: `dist/packages/sdk/`
  - Includes: `index.esm.js`, `index.cjs.js`, `umd/sdk.umd.js`

#### Demo the SDK (UMD)

- Serve the UMD folder:
  ```sh
  npx http-server dist/packages/sdk/umd -p 8080 -c-1
  ```
- Open [http://localhost:8080](http://localhost:8080)
  - Demo page: `dist/packages/sdk/umd/index.html`
  - Ensure the API is running (`nx serve api`)

---

### Environment & CORS (development)

The SDK demo runs at `http://localhost:8080`. To allow it in FastAPI CORS, add:

```python
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
```

You may also set `window.DOMSPHERE_API_URL` in the demo HTML to point the SDK at a specific API URL.

---

### Common Flows

- Fresh types for web build:
  ```sh
  nx run api-client:codegen && nx build web
  ```
- Run web and API separately in two terminals:
  ```sh
  nx serve api
  # (in another terminal)
  nx serve web
  ```
- Rebuild SDK then test demo:
  ```sh
  nx run sdk:build-all && npx http-server dist/packages/sdk/umd -p 8080 -c-1
  ```

---

### Troubleshooting

- **`window.DomSphereSDK` is not a constructor**

  - Ensure `packages/sdk/src/index.ts` exports default and assigns the UMD global:
    ```ts
    export default DomSphereSDK;
    (globalThis as any).DomSphereSDK = DomSphereSDK;
    ```
  - Rebuild UMD:
    ```sh
    nx run sdk:bundle-umd
    ```
    Then hard-reload the page.

- **CORS errors in the browser**

  - Update `CORSMiddleware` origins to include your demo origin (`8080`).
  - Disable caching in the static server:
    ```sh
    http-server -c-1
    ```

- **`openapi-typescript` fails (500)**
  - Ensure `/openapi.json` returns 200 by visiting [http://localhost:4000/openapi.json](http://localhost:4000/openapi.json).
  - Keep LangServe routes out of schema if needed; provide clean typed endpoints under `/v1/*`.

---

### Nx Tips

- List all projects:
  ```sh
  nx show projects
  ```
- Show a project’s targets:
  ```sh
  nx show project <name>
  ```
- Visualize dependency graph:
  ```sh
  npx nx graph
  ```
