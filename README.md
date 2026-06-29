# RegShift

RegShift is a Conduct-style change assurance layer. Conduct gives enterprises deep system understanding. RegShift takes a new business change and compiles it into a machine-checkable Change Contract, then maps it to impacted legacy modules, tests, risk controls, simulation, and approval evidence. The agent does not autonomously change production. It keeps the expert in control.

## Why this fits the Conduct track

Conduct helps enterprises **understand** legacy systems. RegShift helps them **safely change** those systems — with human approval gates, evidence-backed impact tracing, and approval-ready change packs.

## What makes it unique

```text
business change
→ Change Contract
→ Knowledge Graph
→ Impact Path
→ Risk
→ Tests
→ Simulation
→ Approval Pack
```

Not: `business change → AI finds files`

## Architecture

```text
/frontend   Next.js dashboard (workflow, graph, agent trace, production gate)
/backend    FastAPI + LangGraph orchestration + policy governance
/data       Domain packs, demo seed, generated packs, optional ERPNext clone
/infra/k8s  Optional enterprise deployment manifests
```

### Production stack

| Layer | Technology | Role |
|---|---|---|
| Agent orchestration | **LangGraph** | Step-gated workflow with human approval interrupts |
| Knowledge graph | **Neo4j** | Persistent impact graph (fallback: NetworkX in SQLite) |
| Policy governance | Rule engine | 9 production gate checks before pack generation |
| Code index | SQLite + AST scanner | ERPNext file/keyword index |
| Session state | SQLite | Change sessions, traces, governance evaluations |

**Production gate checks:** contract approved, obligations defined, impact evidence, graph traceable, risk scored, agent auto-merge blocked, tests linked, simulation passes, approval roles assigned.

Change pack generation is **blocked** until governance evaluation passes.

## Clone ERPNext (optional)

```bash
git clone --depth 1 https://github.com/frappe/erpnext.git data/repos/erpnext
```

If ERPNext is not cloned, RegShift uses `data/demo_seed/erpnext_index.json`.

## Run locally

### 1. Backend virtual environment (recommended)

```powershell
# From repo root
.\scripts\setup-venv.ps1
.\scripts\run-backend.ps1
```

Or manually:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATA_DIR="..\data"
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000

## Docker Compose

### Mini dev stack (fast — hot reload, no frontend build)

```bash
docker compose -f docker-compose.mini.yml up --build
```

### Production-style stack

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Golden demo script (90 seconds)

1. Click **Demo Mode**
2. Click **Classify Change** → **Compile Change Contract**
3. Click **Approve Contract**
4. Click **Build Knowledge Graph** — click an Obligation node to trace impact path
5. Click **Score Risk** — note agent blocked from autonomous merge
6. Click **Generate Tests** → **Run Simulation** — show before/after
7. Click **Generate Change Pack** → **Download .md**

## Acceptance criteria

- [x] Procurement change request → classified → contract → approved
- [x] ERPNext scan or demo seed fallback
- [x] Knowledge graph with trace path
- [x] Impact files with evidence
- [x] Risk scoring + agent limits
- [x] Contract-linked tests + simulation
- [x] Markdown change pack export
- [x] Docker Compose
- [x] Conduct-inspired enterprise UI

## Kubernetes (optional)

For the hackathon, RegShift runs with Docker Compose. For enterprise deployment, the services are containerised and can run on Kubernetes alongside Conduct-style system connectors, indexing workers, and approval workflow services. See `infra/k8s/`.

## Tests

```bash
cd backend && pip install -r requirements.txt && pytest --cov=app --cov-report=term-missing
```
