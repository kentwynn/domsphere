# DomSphere

DomSphere is a full-stack platform for building, deploying, and sharing intelligent web agents. The Nx-managed monorepo bundles the Next.js operations dashboard, FastAPI services (public API plus the dedicated agent runtime), and shared TypeScript/Python packages—including the embeddable SDK, contracts, and UI kits—so every surface ships from the same source of truth. Under the hood, our agent workflows are orchestrated with LangGraph, giving each LLM-driven planner/template/validator stage a clean, testable hand-off.

## 🏗️ Architecture Overview

DomSphere consists of three main tiers:

### Frontend Layer

- **Next.js Web App** - User interface and dashboard
- **Embeddable SDK** - JavaScript widget for third-party integration
- **Shared UI Components** - Reusable React components

### Backend Layer

- **Public API** - RESTful endpoints for client interactions
- **Agent Service** - AI-powered suggestion engine with multi-agent architecture
- **Contracts** - Shared type definitions and schemas

### AI Agent Architecture

The Agent Service implements a sophisticated multi-agent system for generating contextual suggestions:

```
[User Request]
      │
      ▼
 ┌──────────────────┐
 │ Planner Agent    │  ← Analyzes request and selects template type
 │ (system_planner) │    (info, action, or choice)
 └──────────────────┘
      │
      ▼
 ┌──────────────────┐
 │ Template Agent   │  ← Fills templates with contextual data
 │ (template_filler)│    using site maps, DOM selectors, etc.
 └──────────────────┘
      │
      ├─ If template type = "info"
      │      └─ Fill Info Template → return Suggestion
      │
      ├─ If template type = "action"
      │      └─ Fill Action Template → return Suggestion
      │
      └─ If template type = "choice"
             │
             ▼
      ┌───────────────────────┐
      │ Choice Manager Agent  │  ← Handles multi-step user flows
      │ (choice_flow_manager) │    and state management
      └───────────────────────┘
             │
             │ Manages:
             │  - User choice collection (step 1, 2, 3...)
             │  - Context preservation between steps
             │  - Dynamic re-querying of tools
             │
             ▼
      ┌──────────────────┐
      │ Template Agent   │  ← Called again for final suggestion
      │ (final fill)     │    with complete user context
      └──────────────────┘
             │
             ▼
      [Final Suggestion JSON]
      │
      ▼
 ┌──────────────────────┐
 │ Validator / Executor │  ← Schema validation and DOM verification
 │ (schema + DOM check) │
 └──────────────────────┘
      │
      ▼
 [Final Suggestion Response → User]
```

**Key Features:**

- **Context-Aware**: Analyzes page content, user behavior, and site structure
- **Multi-Step Flows**: Handles complex decision trees and user choice collection
- **DOM Integration**: Validates selectors against actual page elements
- **Template-Driven**: Flexible suggestion types (info, actions, choices)
- **LangChain Powered**: Uses OpenAI models with structured tool calling

### Rule Trigger System

DomSphere uses a standardized trigger contract to determine when AI agents should activate:

#### **Trigger Contract Structure**

```python
class RuleTrigger(BaseModel):
    eventType: DomEventType  # "page_load" | "dom_click" | "input_change" | "submit" | "route_change"
    when: List[TriggerCondition]  # All conditions must be true

class TriggerCondition(BaseModel):
    field: str  # Telemetry field path
    op: ConditionOp  # Comparison operator
    value: Any  # Value to compare against
```

#### **Field Paths (Generic for all websites)**

- `telemetry.attributes.path` - URL path (e.g., "/cart", "/checkout")
- `telemetry.attributes.id` - Element ID (e.g., "cart-count", "submit-btn")
- `telemetry.attributes.class` - CSS class (e.g., "btn-primary")
- `telemetry.elementText` - Element text content (e.g., "2", "Add to Cart")
- `telemetry.cssPath` - CSS selector (e.g., "#cart-count", ".product-link")

#### **Operators**

- `equals` - Exact match
- `gt`, `gte` - Greater than (for numbers)
- `lt`, `lte` - Less than (for numbers)
- `contains` - Substring match
- `in` - Value in array
- `regex` - Regular expression match

#### **Example Triggers**

**Simple Page Load:**

```json
{
  "eventType": "page_load",
  "when": [{ "field": "telemetry.attributes.path", "op": "equals", "value": "/products" }]
}
```

**Cart with 2+ Items:**

```json
{
  "eventType": "page_load",
  "when": [
    { "field": "telemetry.attributes.path", "op": "equals", "value": "/cart" },
    { "field": "telemetry.attributes.id", "op": "equals", "value": "cart-count" },
    { "field": "telemetry.elementText", "op": "gt", "value": 2 }
  ]
}
```

**Click Event:**

```json
{
  "eventType": "dom_click",
  "when": [
    { "field": "telemetry.attributes.path", "op": "equals", "value": "/checkout" },
    { "field": "telemetry.attributes.id", "op": "equals", "value": "place-order" }
  ]
}
```

#### **System Flow**

1. **Agent Service** (`/agent/rule`) - Generates triggers from natural language
2. **Public API** (`/rule`) - Stores and validates triggers
3. **SDK** - Evaluates triggers in real-time and fires rules when conditions are met

**Benefits:**

- ✅ **Type Safety** - Pydantic models ensure valid structure
- ✅ **Consistency** - Same format across all components
- ✅ **Generic** - Works for any website structure
- ✅ **Maintainable** - Single source of truth for trigger format
- ✅ **Extensible** - Easy to add new operators and field paths

### Rule Agent Flow (Current)

The rule agent uses a LangGraph pipeline so that the orchestration logic lives outside the agent class.

```
AgentSuggestNextRequest
        │
        ▼
RuleAgent.generate_triggers
        │  (apps/agent/agents/rule.py)
        ▼
RuleAgent._llm_generate
        │  ↳ build_rule_graph(self._create_toolkit)
        ▼
LangGraph: build_rule_graph
        ├─ Node "generate" → rule_generation_node
        │        │
        │        └─ run_llm_generation (LLM + tools)
        │                ├─ get_output_schema
        │                ├─ plan_sitemap_query
        │                ├─ search_sitemap
        │                └─ get_site_atlas
        ▼
        └─ Node "validate" → rule_validation_node
                 │
                 └─ Filters triggers against allowed event types & operators
        ▼
Validated triggers returned to RuleAgent.generate_triggers
```

This structure keeps the agent thin, makes the LangGraph reusable, and cleanly separates concerns between LLM generation, tool access, and schema validation.

### Suggestion Agent Flow (Current)

The suggestion agent mirrors the same graph-driven architecture, letting LangGraph orchestrate planning, template filling, choice flows, and final output cleanup.

```
AgentSuggestNextRequest
        │
        ▼
SuggestionAgent.generate_suggestions
        │
        ▼
SuggestionAgent._run_suggestion_graph
        │  ↳ build_suggestion_graph(self._create_toolkit, request_meta)
        ▼
LangGraph: build_suggestion_graph
        ├─ Node "planner" → planner_agent_node
        │        └─ LLM prompt selects template_type hint
        ├─ Node "template" → template_agent_node
        │        ├─ Uses SuggestionLLMToolkit tools (plan query, sitemap search, atlas/info, templates)
        │        └─ Returns suggestion_data + intermediate flag
        ├─ Conditional router "template_router"
        │        ├─ template_type == "choice" → "choice_manager"
        │        └─ otherwise → "validator"
        ├─ Node "choice_manager" → choice_manager_agent_node
        │        └─ Drives multi-step choice flows using fresh toolkits
        └─ Node "validator" → finalize_suggestion_state
                 ├─ Applies fallbacks / acknowledgements when needed
                 └─ Normalizes suggestion + emits suggestions list
        ▼
Normalized suggestions returned to SuggestionAgent.generate_suggestions
```

Like the rule agent, the toolkit isolates all external dependencies so the graph can bind LangChain tools on demand while the agent itself stays focused on context prep and API orchestration.

## 🚀 Enhanced Features & Advanced Capabilities

DomSphere's rule agent and assistant support sophisticated targeting and interaction patterns that go far beyond simple ID-based matching. The system works across **any website** by leveraging universal web standards and intelligent pattern recognition.

### **Advanced Targeting Capabilities**

#### **1. Role-Based Targeting**

Target elements by their semantic function rather than specific IDs:

```javascript
// Natural language: "help users with submit buttons"
// Generated trigger:
{
  "eventType": "dom_click",
  "when": [
    {"field": "telemetry.attributes.role", "op": "equals", "value": "button"},
    {"field": "telemetry.elementText", "op": "contains", "value": "submit"}
  ]
}
```

#### **2. Time-Based Conditions**

Create time-aware triggers that respond to user engagement patterns:

```javascript
// Natural language: "show help after 10 seconds on checkout page"
// Generated trigger:
{
  "eventType": "time_spent",
  "when": [
    {"field": "telemetry.attributes.path", "op": "equals", "value": "/checkout"},
    {"field": "session.timeOnPage", "op": "gte", "value": 10}
  ]
}
```

#### **3. Data Attribute Targeting**

Leverage custom data attributes for precise product and content targeting:

```javascript
// Natural language: "target expensive electronics products"
// Generated trigger:
{
  "eventType": "dom_click",
  "when": [
    {"field": "telemetry.attributes.data-category", "op": "equals", "value": "electronics"},
    {"field": "telemetry.attributes.data-price", "op": "gt", "value": 100}
  ]
}
```

#### **4. Pattern Matching with Regex**

Advanced validation and content pattern matching:

```javascript
// Natural language: "validate positive numbers in quantity field"
// Generated trigger:
{
  "eventType": "input_change",
  "when": [
    {"field": "telemetry.attributes.id", "op": "equals", "value": "quantity"},
    {"field": "telemetry.elementText", "op": "regex", "value": "^[1-9][0-9]*$"}
  ]
}
```

#### **5. Engagement Tracking**

Reward and assist users based on interaction depth:

```javascript
// Natural language: "reward users who scroll 75% down product page"
// Generated trigger:
{
  "eventType": "scroll",
  "when": [
    {"field": "telemetry.attributes.path", "op": "equals", "value": "/products"},
    {"field": "session.scrollDepth", "op": "gte", "value": 75}
  ]
}
```

### **Universal Website Compatibility**

The enhanced system works across **any website** by leveraging universal web standards:

#### **Standard HTML Attributes**

- `id`, `class` - Universal identifiers
- `role`, `aria-label` - Accessibility standards
- `data-*` - Custom data attributes

#### **CSS Patterns**

- Complex selectors: `div.product[data-price]`
- Pseudo-selectors: `:nth-child()`, `:contains()`
- Attribute selectors: `[role="button"]`

#### **Session Context**

- Time tracking: `timeOnPage`, `timeOnSite`
- Interaction counts: `clickCount`, `scrollDepth`
- User context: `referrer`, `userAgent`, `viewport`

### **Intelligent Agent Training**

The rule agent understands complex natural language instructions:

- **Simple:** "Show promo on products page"
- **Advanced:** "Help users who spend more than 30 seconds on checkout without clicking submit"
- **Complex:** "Target returning users from Google who view expensive electronics"

### **Enhanced System Flow**

```
Natural Language → Enhanced Agent → Advanced Triggers → Smart Assistant → Contextual Suggestions
```

**Enhanced Agent Processing:**

1. **Semantic Analysis** - Understands intent and context
2. **Real DOM Discovery** - Finds actual elements using atlas
3. **Pattern Generation** - Creates sophisticated conditions
4. **Contract Validation** - Ensures type safety

**Smart Assistant Evaluation:**

1. **Multi-condition Matching** - Complex boolean logic
2. **Session State Tracking** - Time, interactions, context
3. **Performance Optimization** - Efficient event filtering
4. **Real-time Suggestions** - Contextual help delivery

### **Enhanced Benefits**

- 🎯 **Precise Targeting** - Role, data attributes, patterns
- ⏰ **Time-Aware** - Duration-based conditions
- 🔍 **Pattern Matching** - Regex, complex selectors
- 📊 **Session Tracking** - User behavior analysis
- ♿ **Accessibility** - ARIA and role support
- 🌐 **Universal** - Works on any website
- 🚀 **Scalable** - Contract-driven architecture

Your system now rivals enterprise personalization platforms while maintaining simplicity and type safety!

---

## 📁 Project Structure

### Applications (`apps/`)

| App          | Technology          | Purpose                                        | Port |
| ------------ | ------------------- | ---------------------------------------------- | ---- |
| **`web/`**   | Next.js 14          | Main web interface and dashboard               | 3000 |
| **`api/`**   | FastAPI + Python    | Public API endpoints and data services         | 4000 |
| **`agent/`** | FastAPI + LangChain | AI agent service with multi-agent architecture | 5001 |

### Shared Packages (`packages/`)

| Package           | Technology            | Purpose                                      |
| ----------------- | --------------------- | -------------------------------------------- |
| **`contracts/`**  | Pydantic + TypeScript | Shared type definitions and API schemas      |
| **`api-client/`** | TypeScript            | Auto-generated API client from OpenAPI specs |
| **`sdk/`**        | TypeScript + Rollup   | Embeddable widget (ESM/CJS + UMD builds)     |
| **`ui/`**         | React + TypeScript    | Shared UI components and design system       |

### Generated Outputs (`dist/`)

- Build artifacts and bundled packages
- SDK distributions (ESM, CJS, UMD)
- Type definitions

### Development Assets

- **`poc/`** - Proof of concept demos and examples
- **`.github/`** - CI/CD workflows and issue templates
- **Nx Configuration** - Monorepo tooling and build orchestration

---

## 🛠️ Prerequisites

### Required Software

- **Node.js** 18+ (LTS recommended)
- **npm** (comes with Node.js)
- **Python** 3.11–3.13
- **Git** (for version control)

### Optional Tools

- **Nx CLI** (for enhanced developer experience):
  ```bash
  npm install -g nx
  ```
  > You can always use `npx nx` if you prefer not to install globally.

### Environment Setup

- **OpenAI API Key** (for AI agent functionality)
- **IDE/Editor** with TypeScript and Python support (VS Code recommended)

---

## 🚀 Quick Start

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd domsphere

# Install JavaScript dependencies
npm install
```

### 2. Set Up Python Environment

```bash
# Navigate to API directory
cd apps/api

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install API dependencies
pip install fastapi uvicorn[standard] langserve sse-starlette langchain pydantic python-multipart

# Return to project root
cd ../..
```

### 3. Set Up Agent Service

```bash
# Navigate to Agent directory
cd apps/agent

# Create virtual environment (if different from API)
python -m venv .venv
source .venv/bin/activate

# Install agent dependencies
pip install fastapi uvicorn[standard] langchain langchain-openai langgraph httpx pydantic

# Set up environment variables
echo "OPENAI_TOKEN=your_openai_api_key_here" > .env

# Return to project root
cd ../..
```

### 4. Start the Development Environment

```bash
# Start all services (in separate terminals)

# Terminal 1: Start the public API
nx serve api

# Terminal 2: Start the agent service
nx serve agent

# Terminal 3: Start the web application
nx serve web
```

### 5. Verify Installation

- **Web App**: http://localhost:3000
- **Public API**: http://localhost:4000 (health check: `/health`)
- **Agent Service**: http://localhost:5001 (health check: `/health`)
- **API Documentation**: http://localhost:4000/docs

---

## 💻 Development Commands

### Core Services

#### Start the Public API (FastAPI)

```bash
nx serve api
```

- **URL**: http://localhost:4000
- **Health Check**: `GET /health`
- **Documentation**: `/docs` (Swagger UI)
- **OpenAPI Schema**: `/openapi.json`

#### Start the Agent Service (AI Backend)

```bash
nx serve agent
```

- **URL**: http://localhost:5001
- **Health Check**: `GET /health`
- **Suggestion Endpoint**: `POST /agent/suggest`
- **Features**: Multi-agent AI, DOM analysis, contextual suggestions

#### Start the Web App (Next.js)

```bash
nx serve web
```

- **URL**: http://localhost:3000
- **Features**: Dashboard, agent management, real-time previews

### SDK Development

#### Generate API Client Types (OpenAPI → TypeScript)

```bash
nx run api-client:codegen
```

> **Note**: Requires the API to be running at `http://localhost:4000/openapi.json`

#### Build the SDK

**ESM + CJS (Production)**:

```bash
nx build sdk
```

**UMD Bundle (Browser)**:

```bash
nx run sdk:bundle-umd
```

**All Formats**:

```bash
nx run sdk:build-all
```

- **Output**: `dist/packages/sdk/`
- **Includes**: `index.esm.js`, `index.cjs.js`, `umd/sdk.umd.js`

#### Demo the SDK

```bash
# Build and serve UMD demo
nx run sdk:build-all
npx http-server dist/packages/sdk/umd -p 8080 -c-1

# Open http://localhost:8080
```

> **Requirements**: Ensure API and Agent services are running

### Testing & Quality

#### Run Tests

```bash
# Run all tests
nx run-many --target=test

# Test specific project
nx test sdk
nx test web
```

#### Lint & Format

```bash
# Lint all projects
nx run-many --target=lint

# Format code
nx format
```

---

## ⚙️ Environment Configuration

### CORS Setup (Development)

The SDK demo runs at `http://localhost:8080`. Add this to your FastAPI CORS configuration:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js web app
        "http://127.0.0.1:3000",
        "http://localhost:8080",  # SDK demo
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Environment Variables

#### Agent Service (`.env` in `apps/agent/`)

```bash
OPENAI_TOKEN=your_openai_api_key_here
OPENAI_MODEL=gpt-4o                    # Optional, defaults to gpt-4o
API_BASE_URL=http://localhost:4000     # Optional, points to public API
HTTP_TIMEOUT=300                       # Optional, request timeout
LLM_TIMEOUT=300                        # Optional, LLM response timeout
```

#### SDK Configuration

Set `window.DOMSPHERE_API_URL` in demo HTML to point SDK at specific API URL:

```javascript
window.DOMSPHERE_API_URL = 'http://localhost:4000';
```

---

## 🔄 Common Development Workflows

### Full Development Setup

```bash
# Terminal 1: Start API
nx serve api

# Terminal 2: Start Agent Service
nx serve agent

# Terminal 3: Start Web App
nx serve web

# Terminal 4: Watch SDK changes
nx build sdk --watch
```

### Update API Types

```bash
# Regenerate types when API changes
nx run api-client:codegen && nx build web
```

### SDK Development & Testing

```bash
# Build SDK and test in browser
nx run sdk:build-all && npx http-server dist/packages/sdk/umd -p 8080 -c-1
```

### Fresh Build (Clean Slate)

```bash
# Clean and rebuild everything
rm -rf dist/ node_modules/.cache
nx reset
npm install
nx run-many --target=build
```

---

## 🔧 Troubleshooting

### Common Issues

#### **`window.DomSphereSDK` is not a constructor**

```bash
# Ensure SDK exports are configured correctly
# Check packages/sdk/src/index.ts has:
export default DomSphereSDK;
(globalThis as any).DomSphereSDK = DomSphereSDK;

# Rebuild UMD bundle
nx run sdk:bundle-umd

# Hard reload browser page
```

#### **CORS errors in browser**

```bash
# 1. Update CORSMiddleware origins (see Environment Configuration)
# 2. Disable caching in static server
npx http-server -c-1

# 3. Verify all services are running on correct ports
```

#### **`openapi-typescript` fails (500 error)**

```bash
# 1. Verify API is running and accessible
curl http://localhost:4000/openapi.json

# 2. Check API service health
curl http://localhost:4000/health

# 3. Ensure no LangServe routes interfere with schema generation
```

#### **Agent service connection errors**

```bash
# 1. Verify OpenAI API key is set
echo $OPENAI_TOKEN

# 2. Check agent service is running
curl http://localhost:5001/health

# 3. Verify Python dependencies are installed
cd apps/agent && pip list | grep -E "(langchain|openai|langgraph)"
```

#### **Python virtual environment issues**

```bash
# Recreate virtual environment
rm -rf apps/api/.venv apps/agent/.venv
cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../agent && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Performance Tips

- **Development**: Use `--watch` flags for auto-rebuilding
- **SDK Size**: UMD bundle is optimized for browser delivery
- **API Response**: Agent service includes caching for repeated suggestions
- **Memory**: Agent service uses streaming for large LLM responses

---

## 📚 Nx Workspace Commands

### Project Management

```bash
# List all projects
nx show projects

# Show project details and targets
nx show project sdk

# Visualize dependency graph
npx nx graph
```

### Build System

```bash
# Build affected projects only
nx affected --target=build

# Run target for multiple projects
nx run-many --target=lint --projects=sdk,web,ui

# Clear Nx cache
nx reset
```

### Advanced Usage

```bash
# Generate new library
nx g @nx/js:lib my-new-lib

# Run with specific configuration
nx build sdk --configuration=production

# Parallel execution
nx run-many --target=test --parallel=3
```

---

## 🚀 Deployment

### Production Builds

```bash
# Build all applications for production
nx run-many --target=build --configuration=production

# Build specific app
nx build web --configuration=production
```

### Environment-Specific Builds

```bash
# Staging environment
nx build web --configuration=staging

# Production with custom API URL
API_URL=https://api.production.com nx build web
```

### Docker Support

Each application includes Dockerfile for containerization:

```bash
# Build API container
docker build -f apps/api/Dockerfile -t domsphere-api .

# Build agent container
docker build -f apps/agent/Dockerfile -t domsphere-agent .
```

---

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Install** dependencies (`npm install`)
4. **Make** your changes
5. **Test** your changes (`nx run-many --target=test`)
6. **Lint** your code (`nx run-many --target=lint`)
7. **Commit** your changes (`git commit -m 'Add amazing feature'`)
8. **Push** to the branch (`git push origin feature/amazing-feature`)
9. **Open** a Pull Request

### Code Standards

- **TypeScript**: Strict mode enabled
- **Python**: PEP 8 compliance with Black formatting
- **Commits**: Conventional commit messages
- **Testing**: Unit tests required for new features

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: Check the `/docs` folder for detailed guides
- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Join community discussions in GitHub Discussions
- **API Reference**: Available at `/docs` endpoint when services are running

---

_Built with ❤️ using Nx, Next.js, FastAPI, and LangChain_
