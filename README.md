# Corvo Engineering Autonomous Procurement Decision System

An enterprise-grade, deterministic, **Policy-as-Data** procurement platform that transforms employee purchase requests into purchase orders or sourcing workflows following Corvo Procurement Policy v5.0.

Built for the **Cantill.ai Full-Stack Intern Task**.

---

## Key Features

1. **Deterministic Policy-as-Data Core**:
   - Zero-hallucination execution of Corvo Procurement Policy v5.0.
   - 100% verified against all 14 official worked examples (`backend/tests/test_worked_examples.py`).
   - Anti-splitting clubber, run-isolated ceiling ledger, 3-step valuation waterfall, multi-factor supplier ranker, and 24-hour sliding window PO consolidation.
   - Dynamic policy versioning: upload amendments, inspect JSON diffs, and activate new policies at runtime without code deployment or server restarts.

2. **Conversational PR Intake (Chat Agent)**:
   - Natural language interface for employees to raise PRs.
   - Slot extraction (Item, Quantity, Plant PUN1/CHK1, Need-by Date, Urgency) with clarifying follow-up questions for missing details.
   - Real-time policy decision preview with one-click submission to buyer review.

3. **Bulk Batch Processing**:
   - Ingests CSV batches, runs anti-splitting & pricing pipelines, and generates Section 4 decisions.
   - Instant export of full decision results (`decisions_{run_id}.csv`) in the exact official evaluation format.

4. **Buyer Workspace & Governance**:
   - Centralized review table with filters (plant, route, decision, status).
   - Detailed inspection drawer with clubbed PR lines, valuation sources, and suggested suppliers.
   - One-click approval and **audited manual overrides** requiring mandatory business justification comments.

5. **Preferred Supplier Explorer**:
   - Date-parameterized rankings (`2026-11-01`) evaluated using multi-factor composite scores.
   - One-click full catalog preferred supplier export.

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, Pandas, RapidFuzz, PyPDF.
- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons.
- **Database**: SQLite (default zero-config) / PostgreSQL (production-ready).
- **AI / LLM**: Google Gemini 2.5 Flash / Gemini 3.8 Flash via `google-genai` SDK with deterministic heuristic fallback.
- **Containerization**: Docker & Docker Compose.

---

## Quickstart

### Method 1: Single-Command Docker Run (Recommended)

```bash
docker compose up --build
```

- **Frontend Application**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Method 2: Local Development Setup

#### 1. Backend Setup
```bash
# From workspace root
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

pip install -r backend/requirements.txt

# Run initial seed (if procurement.db is not present)
$env:PYTHONPATH="backend"  # Windows PowerShell
python backend/app/db/seed.py

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) in your browser.

---

## Running Verification Test Suites

### 1. Worked Examples Test Suite (14 / 14 Verified)
```bash
$env:PYTHONPATH="backend"
python backend/tests/test_worked_examples.py
```
Outputs validation against all 14 Corvo Worked Examples (Contract PO, PDF Contract ingestion, Ceiling depletion, Anti-splitting, Free-text matching, Emergency PO, RFQ, RFP, Capex Sourcing, New Item Sourcing, PO Consolidation).

### 2. Full API Route Integration Test Suite
```bash
$env:PYTHONPATH="backend"
python backend/tests/test_all_routes.py
```
Validates the complete lifecycle: Policy Admin, Chat Intake, PR Submission, Buyer Workspace, Overrides, and CSV exports.

---

## Project Documentation

All documentation is in the [`docs/`](./docs/) folder:

- **`docs/README.md`** — Project overview and quickstart
- **`docs/APPROACH.md`** — AI tool usage disclosure, 7-stage deterministic pipeline architecture, and worked example validation.
- **`docs/DECISIONS.md`** — Complete log of 10 architectural and business ambiguity decisions with justifications.
- **`docs/MASTER_PLAN.md`** — Deep technical architecture specification.
- **`docs/HANDOVER_PROGRESS.md`** — Phase-by-phase completion log and handover status.
- **`docs/PRODUCTION_DECISIONS.md`** — Free-tier production deployment strategy (Render, Neon, Vercel).
- **`docs/QUICKSTART_AND_TEST_GUIDE.md`** — How to run locally and verify with test suites.
- **`docs/BUG_FIXES_AND_AUDIT.md`** — Complete log of bugs found, root causes, and fixes applied (critical for evaluator review).
- **`docs/detailed inspection/`** — Detailed inspection notes and extracted policy text.
