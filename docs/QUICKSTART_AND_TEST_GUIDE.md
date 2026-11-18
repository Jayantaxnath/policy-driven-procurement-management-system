# Corvo Procurement System — Quickstart & 19 Nov Testing Guide

---

## 1. How to Start the System (Right Now)

You can run the system in **Docker** (Method A) or **Directly in Terminal** (Method B).

### Method A: Single Command with Docker (Recommended)
```bash
docker compose up --build
```
- **Web UI**: Open [http://localhost:5173](http://localhost:5173) in your browser.
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Method B: Run Locally Without Docker

**Terminal 1 — Backend (FastAPI)**:
```bash
# Windows PowerShell:
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend (React UI)**:
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173).

---

## 2. How to Run Automated Tests

Run these two commands in PowerShell from the project root:

```bash
$env:PYTHONPATH="backend"

# 1. Test all 14 Worked Examples (Core Engine)
python backend/tests/test_worked_examples.py

# 2. Test all API Endpoints (Policy, Chat, Batch, Buyer Review & Overrides)
python backend/tests/test_all_routes.py
```
Both commands should output `PASS` for all tests.

---

## 3. What to Do on Thursday 19 Nov (Blind Test Day: 10:00 AM – 12:00 PM IST)

During the blind test, Cantill will give you a **new, unseen blind batch CSV** (`blind_test_pr_batch.csv`) and potentially a **policy amendment**.

### Step 1: Start the System Before 10:00 AM
Make sure Docker is running or both backend and frontend terminals are active:
```bash
docker compose up
```

---

### Step 2: Processing the Blind Batch CSV
You have two ways to process the blind CSV:

#### Option 1: Via the Web Interface (Easiest)
1. Open [http://localhost:5173](http://localhost:5173) and click the **Batch Processing** tab.
2. Drag and drop or upload the blind CSV file.
3. Click **Process Batch**.
4. Click **Download Decisions CSV (Section 4)**. This downloads `decisions_<run_id>.csv` in the exact format required by the evaluators.

#### Option 2: Via API / Curl / Script
```bash
curl -X POST "http://localhost:8000/api/process-batch" \
     -F "file=@path/to/blind_test_pr_batch.csv"
```
Or download the Section 4 CSV:
```bash
curl -O "http://localhost:8000/api/runs/{RUN_ID}/export"
```

---

### Step 3: If They Provide a Policy Amendment (e.g. Policy v5.1)
If the blind test changes a rule (e.g., "Emergency threshold increased to ₹7,50,000" or "RFQ threshold increased to ₹3,00,000"):

1. Go to the **Policy Admin** tab in the UI.
2. In the **Submit Policy Amendment** box:
   - Version ID: `v5.1`
   - Description: Type the amendment text or paste the new JSON.
   - Click **Upload & Generate Diff**.
3. Inspect the diff on screen.
4. Click **Approve & Activate**.
5. Re-run or re-upload the blind batch CSV. The engine will automatically evaluate against the new policy without restarting the server!

---

### Step 4: If Sourcing / Preferred Supplier Rankings Are Requested
To generate preferred suppliers as of any date (e.g., as of 2026-11-01):
- Go to the **Preferred Suppliers** tab in the UI.
- Pick the date and click **Export All (CSV)**.
- Or use the endpoint directly:
  `http://localhost:8000/api/preferred-suppliers?as_of_date=2026-11-01`

---

## 4. Checklist Before Submitting
- [ ] Verify `docker compose up --build` launches cleanly.
- [ ] Verify `python backend/tests/test_worked_examples.py` passes 14/14.
- [ ] Exported CSV has all 13 Section 4 columns:  
  `pr_no, pr_line, resolved_item_code, group_id, po_id, decision, route, supplier_id, unit_price, group_value_inr, suggested_supplier_ids, policy_version, reason`
- [ ] Git repository is up to date and pushed to GitHub.

---

## 5. Quick Reset (One-Liner)

Use this command to reset the Neon DB before a blind test run. Keeps only v5.0 policy, clears all requirements, and preserves PR batches.

**PowerShell (from `backend/` directory):**

```powershell
# Set Neon DB env var first:
$env:DATABASE_URL_SYNC="postgresql://neondb_owner:npg_Q4BOC7INpjnk@ep-lively-grass-akc9eecx-pooler.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# One-liner reset:
python -c "import sys; sys.path.insert(0,'.'); from app.db.database import SyncSessionLocal; from sqlalchemy import text; s=SyncSessionLocal(); [s.execute(text(q)) for q in ['DELETE FROM requirement_lines','DELETE FROM buyer_actions','DELETE FROM requirements','DELETE FROM batch_execution_runs WHERE policy_version_id IN (\"v5.1\",\"v5.2\")','DELETE FROM policy_approvals WHERE version_id IN (\"v5.1\",\"v5.2\")','DELETE FROM policy_versions WHERE version_id IN (\"v5.1\",\"v5.2\")']]; s.commit(); print('Reset done'); s.close()"
```

**What it resets:**
- All requirements, requirement_lines, buyer_actions → 0
- Policy versions v5.1 and v5.2 → removed (only v5.0 remains)
- PR batches, PR lines, execution runs → preserved

**For local SQLite instead of Neon:**
```powershell
$env:DATABASE_URL_SYNC="sqlite:///./procurement.db"
# then run the same one-liner above
```
