# SchemaSense: Natural Language Database Explorer

> Connect a PostgreSQL, MySQL, or SQLite database — or upload CSV, TSV, XLS, and XLSX files — ask questions in plain English, and get safe SQL, interactive charts, anomaly insights, and Gmail/CSV exports.

---

## 🌐 Live Deployment (Railway)

- **Live Web App**: https://frontend-production-6309bff1.up.railway.app
- **Backend API**: https://backend-production-a59abaca.up.railway.app
- **API Health Check**: https://backend-production-a59abaca.up.railway.app/api/health

> **Public Demo Note:** The live demo comes pre-seeded with the sample E-Commerce & SaaS SQLite database (`Demo E-Commerce Store`) backed by a persistent Railway `/data` volume, and also supports uploading your own CSV/Excel datasets. For private or production multi-user deployments, add authentication and restrict `Access-Control-Allow-Origin` in [`backend/app/main.py`](backend/app/main.py).

---

## 🌟 Highlights & Architecture

- **Multi-Source Data Support (DB + Spreadsheets)**:
  - Connects to PostgreSQL, MySQL, and SQLite databases with schema introspection & vector retrieval.
  - Drag-and-drop **CSV, TSV, XLS, and XLSX upload** ([`backend/app/services/file_ingest.py`](backend/app/services/file_ingest.py)) that automatically sanitizes columns, builds queryable SQLite tables, and syncs schemas.
- **Multi-Provider LLM Support + Interactive Assistant**:
  - Supports **Google Gemini**, **LM Studio** (local OpenAI-compatible models), **OpenAI**, and a deterministic offline fallback engine configured via [`/settings`](frontend/src/app/settings/page.tsx) or environment variables.
  - Includes an **Interactive Analysis Assistant Drawer** ([`AnalysisAssistantDrawer.tsx`](frontend/src/components/AnalysisAssistantDrawer.tsx)) aware of the active schema, SQL query, sample rows, and insights.
- **Data Visualizer Studio & Charting**:
  - Dedicated [`/visualizer`](frontend/src/app/visualizer/page.tsx) studio and inline chat visualizations powered by **Apache ECharts** (Bar, Line, Area, Pie, Donut, Scatter, and KPI views).
- **Gmail & Data Export**:
  - Export query results and charts as CSV/JSON or send formatted analytical summaries via **Gmail Web Compose** or direct **SMTP** ([`export_email.py`](backend/app/services/export_email.py), [`GmailExportModal.tsx`](frontend/src/components/results/GmailExportModal.tsx)).
- **Layered AST SQL Safety Core (Section 5.4)**:
  - Single-statement enforcement, `SELECT`/`WITH` allowlist, function denylist (`pg_sleep`, `pg_read_file`, `lo_import`, `dblink`, `INTO OUTFILE`, etc.), table-scope verification, forced `LIMIT` injection (default `1,000`, hard cap `10,000`), and read-only execution sandbox.
- **9-Stage SSE Query Orchestrator Pipeline**:
  - Follow-up resolution -> cosine schema retrieval -> compact prompt building -> structured JSON generation -> safety validation -> self-healing repair loop (max 2 retries) -> caching -> chart recommendation + AST explanation -> real-time **Server-Sent Events (SSE)** streaming.
- **Envelope Encryption for DB Credentials**:
  - Two-tier KEK (`MASTER_ENCRYPTION_KEY`) + per-credential DEK encryption decrypted only in memory during target execution.
- **Statistical Anomaly Insights**:
  - Metric monitoring with rolling median and Median Absolute Deviation (MAD) in [`anomaly_detector.py`](backend/app/services/anomaly_detector.py).

---

## 📁 Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py                  # Settings, env vars & persistent volume paths
│   │   ├── main.py                    # REST & SSE streaming API server
│   │   ├── db/
│   │   │   ├── models.py              # Section 5.1 Data Model
│   │   │   ├── database.py            # SQLite app store & initialization
│   │   │   ├── repository.py          # CRUD repository
│   │   │   └── target_db.py           # Target DB introspection & read-only executor
│   │   ├── safety/
│   │   │   ├── validator.py           # Layered SQL safety validator
│   │   │   └── adversarial_corpus.py  # Adversarial injection test corpus
│   │   ├── security/
│   │   │   └── crypto.py              # KEK/DEK envelope encryption
│   │   ├── services/
│   │   │   ├── anomaly_detector.py    # Rolling median + MAD anomaly engine
│   │   │   ├── cache.py               # Query & embedding cache
│   │   │   ├── explanation.py         # Query explanation & optimization hints
│   │   │   ├── export_email.py        # CSV/HTML formatting, Gmail URL & SMTP export
│   │   │   ├── file_ingest.py         # CSV, TSV, XLS, XLSX ingestion to SQLite
│   │   │   ├── llm_client.py          # Gemini, LM Studio, OpenAI & offline client
│   │   │   ├── prompt_builder.py      # Follow-up & dialect system prompts
│   │   │   ├── repair_loop.py         # Self-healing SQL repair loop
│   │   │   ├── schema_retriever.py    # Vector retrieval & compact schema formatting
│   │   │   ├── visualizer.py          # Data Visualizer Studio aggregation engine
│   │   │   └── viz_recommender.py     # Rules-first ECharts recommendation engine
│   │   ├── orchestrator/
│   │   │   └── pipeline.py            # 9-stage SSE streaming orchestrator
│   │   └── eval/
│   │       ├── dataset.py             # Evaluation dataset & Gold SQL
│   │       └── harness.py             # Execution accuracy evaluation harness
│   ├── tests/                         # Backend unit tests
│   ├── run_api.py                     # API server launcher (auto-seeds demo DB if empty)
│   ├── run_evals.py                   # Evaluation harness CLI
│   ├── run_safety_tests.py            # Adversarial security test runner
│   ├── seed_demo_data.py              # Demo e-commerce target DB seeder
│   ├── requirements.txt               # Backend Python dependencies
│   ├── .env.example                   # Environment template
│   ├── .dockerignore
│   └── Dockerfile
├── frontend/
│   ├── public/                        # Static assets directory
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx             # Root layout with responsive Navbar
│   │   │   ├── page.tsx               # Landing & quick-start dashboard
│   │   │   ├── chat/page.tsx          # Natural language explorer (SSE chat)
│   │   │   ├── visualizer/page.tsx    # Interactive Data Visualizer Studio
│   │   │   ├── connections/page.tsx   # DB connections, CSV/XLS upload & schema browser
│   │   │   ├── insights/page.tsx      # Automated anomaly insights dashboard
│   │   │   └── settings/page.tsx      # LLM provider (Gemini/LM Studio/OpenAI) & SMTP config
│   │   ├── components/
│   │   │   ├── Navbar.tsx
│   │   │   ├── FileUploadPanel.tsx
│   │   │   ├── AnalysisAssistantDrawer.tsx
│   │   │   ├── chat/                  # MessageList, QuestionInput, SqlViewer, AssumptionChips
│   │   │   ├── results/               # DataGrid, ChartPanel (ECharts), ExportMenu, GmailExportModal
│   │   │   └── schema/                # SchemaTree, ColumnEditor (PII toggles)
│   │   └── lib/                       # API client, SSE stream reader, ECharts mapper
│   ├── package.json
│   ├── next.config.js
│   ├── .dockerignore
│   └── Dockerfile
└── docker-compose.yml                 # Local multi-service stack
```

---

## 🚀 Local Quick Start

### 1. Backend Setup & Tests
```bash
# Optional: seed the sample E-Commerce SQLite DB (also runs automatically on API boot)
PYTHONPATH=backend python3 backend/seed_demo_data.py

# Run adversarial safety tests & unit tests
PYTHONPATH=backend python3 backend/run_safety_tests.py
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v

# Start backend API server (default: http://localhost:8000)
PYTHONPATH=backend python3 backend/run_api.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## ☁️ Railway Two-Service Deployment

SchemaSense runs on Railway as two separate Docker services from this monorepo:

1. **Backend service (`./backend`)**:
   - Mount a persistent volume at `/data` (Railway automatically injects `RAILWAY_VOLUME_MOUNT_PATH=/data` so SQLite databases, uploads, and saved settings persist across deploys).
   - Set variables:
     - `HOST=0.0.0.0`
     - `PORT=8000`
     - `DEBUG=false`
     - `LLM_PROVIDER=gemini` (or `openai`)
     - `LLM_MODEL=gemini-flash-lite-latest`
     - `GEMINI_API_KEY=<your-key>`
     - `MASTER_ENCRYPTION_KEY=<random-32+-byte-secret>`
   - Generate a public domain for port `8000` and deploy:
     ```bash
     railway up ./backend --path-as-root --service backend
     ```

2. **Frontend service (`./frontend`)**:
   - Set `PORT=3000` and `NEXT_PUBLIC_BACKEND_URL=https://<your-backend-domain>` **before building** (`frontend/Dockerfile` accepts `ARG NEXT_PUBLIC_BACKEND_URL` for Next.js compile-time client bundling).
   - Generate a public domain for port `3000` and deploy:
     ```bash
     railway up ./frontend --path-as-root --service frontend
     ```

---

## 🐳 Docker Compose (Local Full Stack)

To build and run the local Docker stack (App Postgres with `pgvector`, Demo Target Postgres, Redis, Backend API, and Next.js Frontend):
```bash
docker compose up --build -d
```

---

## 🛡️ Verification Summary

| Check | Result | Status |
|---|---|---|
| **Backend Unit Tests** (`backend/tests`) | 25 tests passing | PASS |
| **Adversarial SQL Safety Suite** | 100% rejection of non-SELECT & dangerous SQL | PASS |
| **Frontend Production Build** (`next@14.2.35`) | All 9 App Router pages compiled cleanly | PASS |
| **Live Railway Deployment** | Both `frontend` & `backend` `SUCCESS` + `/data` mounted | LIVE |
