# Cantill Full-Stack Task — Master Plan
## Policy-Driven PR-to-PO Platform for Corvo Engineering

> [!IMPORTANT]
> This plan supersedes the previous failed blueprint. Every correction from the review is addressed and labelled. Assumptions requiring human sign-off are marked **[ASSUMPTION — REVIEW REQUIRED]**.

---

## 1. What I Read & What I Understood

### 1.1 The Business Problem (In My Own Words)

Corvo Engineering (fictional), two plants — **PUN1 (Bhosari)** and **CHK1 (Chakan)** — raises hundreds of purchase requisitions (PRs) daily. Today, buyers manually decide:
- Should this become a Purchase Order (PO) directly?
- Or does it need competitive sourcing (RFQ/RFP)?

The manual process has three failure modes:
1. **Splitting abuse**: Requesters split one large need into many small PRs to stay under limits and avoid quotation requirements.
2. **Inconsistent policy application**: Policy changes require retraining; human buyers apply old rules.
3. **Supplier governance lapses**: Blocked/inactive suppliers still receive orders.

**The app must**: Automate this decision deterministically by applying a versioned, structured policy — not hardcoded business logic.

---

### 1.2 The Policy Engine Logic (Corvo Procurement Policy v5.0)

I read every clause carefully. Here is the complete decision logic:

#### Step 1 — Item Identification (Clauses 1.1, 1.2)
- If `item_code` is given and exists in item_master → use it.
- If only a description is given → fuzzy-match against item_master descriptions (e.g., "brg 6205 2rs" → ITM-1021).
- If no match → it's a **NEW item**. Routes directly to `NEW_ITEM_SOURCING`. Never clubbed. Valued at `qty × estimated_unit_price`. No supplier suggestions.

#### Step 2 — Clubbing (Clauses 2.1, 2.2, 2.3)
Anti-splitting: treat multiple PRs for the same need as ONE requirement.

**Clubbing conditions** (ALL must be true):
- Same `resolved_item_code`
- Same `plant`
- Line's `created_at.date()` is within **14 calendar days** of the group's first line's `created_at.date()`
- `|line.need_by_date - group.first_line.need_by_date| ≤ 7 calendar days`

**Ordering rule**: Sort all PR lines by `created_at ASC, pr_no ASC, pr_line ASC` **before** clubbing. If a line could join multiple groups, it joins the **earliest** one.

**Requirement metadata**:
- `requirement_date` = `created_at.date()` of the first line
- `urgency` = Emergency if **any** constituent line is Emergency
- `total_quantity` = sum of all constituent line quantities

#### Step 3 — Valuation (Clause 3.1)
Unit price waterfall (take first applicable):
1. **Contract rate** of the winning contract (Clause 4.3). If all applicable contracts are out of ceiling → use the **lowest applicable contract rate** (even though the contract can't be used).
2. **Most recent PO price** for the item in the **365 days before** requirement_date, from an **Active** supplier.
3. **Item master standard_price**.

`group_value_inr = total_quantity × unit_price`

#### Step 4 — Contract Check (Clauses 4.1–4.4)
A contract **applies** if:
- It covers the item (via `contract_lines`)
- `start_date ≤ requirement_date ≤ end_date`
- `supplier.status == 'Active'` ← **critical: must check supplier status at this step**

A contract **can be used** (has ceiling) if:
- `consumed_value + (total_quantity × contract_rate) ≤ value_cap`

Requirements consume ceiling in **order of requirement_date** (earliest first).

**Multi-contract rule (4.3)**: If multiple contracts qualify with sufficient ceiling → pick the one with the **lowest rate**.

**PDF-only contracts (4.4)**: Contracts signed after the last register update exist **only as PDFs**. They are binding from their start date. Must be parsed and loaded at system setup. `consumed_value = 0` (they start fresh).

**Two PDF-only contracts found**:
- `RC-2026-031`: S021 (Pneumatic Point), valid 2026-11-15 to 2027-11-14, cap ₹20L
  - ITM-1036 @ ₹3,537.76
  - ITM-1037 @ ₹2,439.01
  - ITM-1039 @ ₹2,746.87
- `RC-2026-033`: S035 (Infoline Systems), valid 2026-11-20 to 2027-11-19, cap ₹50L
  - ITM-1056 @ ₹64,654.36
  - ITM-1057 @ ₹10,689.51

#### Step 5 — Decision Rules (Clauses 5.1–5.7)
Evaluated in this exact order. First rule that fits wins:

| Clause | Condition | Decision | Route | Supplier |
|--------|-----------|----------|-------|----------|
| 5.1 | `item_type == 'Capex'` | SOURCING_REQUEST | CAPEX_SOURCING | Top 5 from category |
| 5.2 | Valid contract with ceiling room | PO | CONTRACT_PO | Contract supplier @ contract rate |
| 5.3 | Emergency AND value ≤ ₹5,00,000 AND bought from Active supplier in 365d | PO | EMERGENCY_PO | 1st preferred supplier @ reference price |
| 5.4 | value < ₹2,00,000 AND bought from Active supplier in 365d | PO | SPOT_PO | 1st preferred supplier @ reference price |
| 5.5 | value < ₹10,00,000 | SOURCING_REQUEST | RFQ | Top 3 suppliers |
| 5.6 | value ≥ ₹10,00,000 | SOURCING_REQUEST | RFP | Top 5 suppliers |

> [!CAUTION]
> **Clause 5.7** is NOT a separate route. It is a **global constraint** applied before any rule evaluation: Blocked/Inactive suppliers must never receive a PO, be used as the basis for contract awards, or appear in sourcing suggestions. This applies at the supplier master check in Step 4, and in all supplier-suggestion logic.

#### Step 6 — Preferred Supplier List (Clauses 6.1–6.4)
**Who is on the list (6.1)**: Active suppliers with:
- ≥ 1 PO for the item in **548 days** before `requirement_date`, OR
- A contract for the item that started on or before `requirement_date` (even if expired)

**Ranking (6.2)**: The policy says "how often, how recently, whether they held a contract, on-time delivery, quality" — but leaves exact weights to the system design. The worked examples show the expected ordering.

**[ASSUMPTION — REVIEW REQUIRED]**: Proposed composite scoring formula:

$$S = 0.25 \cdot \min\left(\frac{N_{PO}}{5}, 1.0\right) + 0.25 \cdot R + 0.20 \cdot C + 0.15 \cdot \frac{\text{on\_time\_pct}}{100} + 0.15 \cdot \frac{\text{quality\_rating}}{5.0}$$

Where:
- $N_{PO}$ = number of POs in 548 days
- $R$ (Recency): 1.0 if most recent PO ≤ 90 days ago; 0.5 if ≤ 365 days; 0.0 if older
- $C$ (Contract): 1.0 if supplier held a contract for item on or before `requirement_date`; else 0.0

**Validation against worked examples**: The weights must be validated against all 3 worked example preferred supplier lists (ITM-1048, ITM-1036, ITM-1016). Adjustments will be recorded in DECISIONS.md.

**Reference price (6.3)**: Most recent PO price from that supplier in 548 days. If none, the rate in their most recent contract for the item.

**Sourcing suggestions (6.4)**: Take preferred list in rank order. If fewer than K (3 for RFQ, 5 for RFP/Capex), **backfill** from other Active suppliers listing the item's category, ordered by on-time delivery DESC, quality_rating DESC.

#### Step 7 — PO Consolidation (Clauses 7.1, 7.2)
Requirements that result in a PO are **consolidated into one PO with multiple lines** when:
- Same `supplier_id`
- Same `plant`
- Same `route`
- Creation time of first line of Req B within **24 hours** of creation time of first line of Req A (exact timestamp comparison)

Process requirements in order of `created_at` of their first line. Join earliest open qualifying PO; otherwise create new PO.

**Sourcing requests are NEVER consolidated.**

---

### 1.3 Data Inventory — What I Verified

#### Critical Data Traps Found

| # | Trap | Affected Data | Decision |
|---|------|---------------|----------|
| 1 | **PR rows not sorted chronologically** | `sample_pr_batch.csv` row 0 is 2026-11-19, row 3 is 2026-11-02 | Must sort by `created_at ASC, pr_no ASC, pr_line ASC` before any processing |
| 2 | **Zero quantity** (`PR-26-00172`, ITM-1020, qty=0) | Row 182 | `route: NOT_PROCESSED`, reason: "Invalid quantity: 0" |
| 3 | **Unknown plant** (`PR-26-00173`, plant=PUN2) | Row 183 | `route: NOT_PROCESSED`, reason: "Plant PUN2 not in policy scope" |
| 4 | **Blocked supplier with active contract** | `RC-2026-005` → S004 (Metalink Alloys, Blocked) | Contract disqualified at Clause 4.1 check. Items ITM-1006, ITM-1007 get no contract. |
| 5 | **Two PDF-only contracts** | `RC-2026-031`, `RC-2026-033` | Must parse from PDFs, load with `consumed_value=0`, valid from their start dates |
| 6 | **Near-depleted contract ceiling** | `RC-2026-002`: ₹38,000 remaining; `RC-2026-015`: ₹12,000 remaining | Engine must dynamically track consumed ceiling during batch run |
| 7 | **39 missing `item_code`** in PR batch | Rows with only descriptions | 37 likely match master items (fuzzy match); 2 are genuine NEW items (drinking water purifier, ultrasonic thickness gauge) |
| 8 | **60 missing `estimated_unit_price`** | Rows with known item codes | Pricing resolved via policy waterfall (contract → PO history → std price) |
| 9 | **Multi-category suppliers** | S020: "Electrical Spares;Capital Equipment" | Parse semicolon-separated categories into array for category-based supplier suggestions |

#### Dataset Statistics (Verified from Files)
- **Plants**: 2 (PUN1, CHK1)
- **Items**: 73 (ITM-1001 to ITM-1073): 60 Material, 8 Service, 5 Capex
- **Suppliers**: 48 total — 43 Active, 3 Blocked (S004, S008, S011), 2 Inactive (S031, S034)
- **PO History**: 468 rows (2025-06-01 to 2026-10-28)
- **Contracts in register**: 10 (some with critically low ceilings)
- **PDF-only contracts**: 2 (RC-2026-031, RC-2026-033)
- **PR Batch**: 186 rows; composite key (pr_no, pr_line)

---

## 2. Architecture Decisions (Corrected)

### 2.1 Core Principle — What LLM Does vs. What Code Does

| Concern | Who Handles It |
|---------|---------------|
| Parse "need 200 gloves for Chakan by Friday" into structured JSON | LLM (Gemini Flash / GPT-4o-mini) |
| Parse policy amendment document into structured JSON diff | LLM |
| Fuzzy item match | Deterministic (normalized token overlap, NO LLM) |
| Clubbing, valuation, contract check, decision rules, PO consolidation | Deterministic Python engine |
| Supplier scoring | Deterministic formula |
| All math and rule evaluations | Deterministic — reproducible bit-for-bit given same DB state |

### 2.2 Technology Stack

| Tier | Choice | Reason |
|------|--------|--------|
| Backend | **Python 3.11 + FastAPI** | Native pandas/numpy, pdfplumber, LLM SDKs, async IO |
| Frontend | **React 18 + Vite + Tailwind CSS** | Fast SPA, chat UI, buyer workspace, tabular diffs |
| Database | **PostgreSQL 16** | ACID relational + JSONB for policy rule trees and audit logs |
| PDF Parsing | **pdfplumber** | Contracts are vector PDFs, not scans — no OCR needed |
| LLM | **Gemini 1.5 Flash** (primary) | Low latency, structured JSON output, free tier available |
| Deployment | **Docker Compose** (local) + **Railway/Render** (hosted) | One-command local run, free managed Postgres |

### 2.3 Key Architectural Invariants
1. **Policy-as-Data**: Every threshold (₹2L, ₹5L, ₹10L, 14-day clubbing window, 24-hour PO consolidation, 365-day history lookback, 548-day supplier eligibility) lives in a **versioned JSON policy document** in the database — not in Python `if/else` statements.
2. **Deterministic Reproducibility**: Given the same database state and batch CSV, `POST /api/process-batch` produces bit-for-bit identical output every time.
3. **Run-Specific Contract Ledger**: Each batch execution run initializes a **private in-memory ceiling ledger** from the persistent contract state at the time of the run. Ceiling consumption during a run is tracked in this ledger and committed to DB only upon run completion. This prevents double-consumption during reruns or parallel test runs.
4. **LLM never makes procurement decisions**: The LLM only produces structured candidate data for human or deterministic engine confirmation.
5. **Clause 5.7 as global constraint**: Supplier status validation is a gate applied before all supplier selection, suggestion, or contract awarding logic — not a separate decision route.
6. **Separation of price-lookup from eligibility-check**: Two different lookups on PO history:
   - **Valuation (Step 3)**: Find the most recent PO price for the item in 365 days (from ANY supplier, since we're asking what the market price was). **[ASSUMPTION — REVIEW REQUIRED]**: The policy says "most recent PO for the item in the 365 days" without specifying active-only for valuation. I'll apply active-supplier filter here too for consistency with clause 5.4, but this is a judgment call that will be in DECISIONS.md.
   - **Eligibility (Steps 5.3, 5.4)**: Specifically check if item was purchased from an **Active** supplier in 365 days (the "proven supplier" test).

---

## 3. Full Database Schema (Corrected & Expanded)

### 3.1 Master Data Tables

```sql
-- Plants
CREATE TABLE plants (
  plant_code VARCHAR(10) PRIMARY KEY,
  name VARCHAR(100) NOT NULL
);

-- Item Master
CREATE TABLE item_master (
  item_code VARCHAR(20) PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  uom VARCHAR(20) NOT NULL,
  category VARCHAR(100) NOT NULL,
  item_type VARCHAR(20) NOT NULL CHECK (item_type IN ('Material', 'Service', 'Capex')),
  standard_price NUMERIC(14, 2) NOT NULL
);

-- Supplier Master
CREATE TABLE supplier_master (
  supplier_id VARCHAR(20) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  city VARCHAR(100) NOT NULL,
  categories TEXT[] NOT NULL,         -- parsed from semicolon-delimited string
  status VARCHAR(20) NOT NULL CHECK (status IN ('Active', 'Blocked', 'Inactive')),
  on_time_pct NUMERIC(5,2) NOT NULL,
  quality_rating NUMERIC(3, 2) NOT NULL
);

-- PO History
CREATE TABLE po_history (
  po_number BIGINT PRIMARY KEY,
  po_date DATE NOT NULL,
  supplier_id VARCHAR(20) NOT NULL REFERENCES supplier_master(supplier_id),
  item_code VARCHAR(20) NOT NULL REFERENCES item_master(item_code),
  quantity NUMERIC(12, 3) NOT NULL,
  uom VARCHAR(20) NOT NULL,
  unit_price NUMERIC(14, 4) NOT NULL,
  plant VARCHAR(10) NOT NULL REFERENCES plants(plant_code),
  delivered_on_time BOOLEAN NOT NULL
);
```

### 3.2 Contract Tables

```sql
-- Contract Headers (register + PDF-extracted)
CREATE TABLE contract_headers (
  contract_id VARCHAR(50) PRIMARY KEY,
  supplier_id VARCHAR(20) NOT NULL REFERENCES supplier_master(supplier_id),
  supplier_name VARCHAR(255) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  value_cap NUMERIC(14, 2) NOT NULL,
  consumed_value NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
  source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('REGISTER_CSV', 'PDF_EXTRACTED', 'MANUAL')),
  pdf_filename VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Contract Lines
CREATE TABLE contract_lines (
  id SERIAL PRIMARY KEY,
  contract_id VARCHAR(50) NOT NULL REFERENCES contract_headers(contract_id) ON DELETE CASCADE,
  item_code VARCHAR(20) NOT NULL REFERENCES item_master(item_code),
  description VARCHAR(255) NOT NULL,
  uom VARCHAR(20) NOT NULL,
  rate NUMERIC(14, 4) NOT NULL,
  UNIQUE (contract_id, item_code)
);

-- Run-Specific Contract Consumption Ledger
-- Tracks ceiling changes WITHIN a single batch run; committed after run completes
CREATE TABLE contract_consumption_log (
  id SERIAL PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES batch_execution_runs(run_id) ON DELETE CASCADE,
  contract_id VARCHAR(50) NOT NULL REFERENCES contract_headers(contract_id),
  requirement_group_id VARCHAR(100) NOT NULL,
  amount_consumed NUMERIC(14, 2) NOT NULL,
  consumed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 Policy Versioning Tables

```sql
-- Policy Versions
CREATE TABLE policy_versions (
  version_id VARCHAR(20) PRIMARY KEY,              -- e.g., 'v5.0', 'v5.1'
  name VARCHAR(255) NOT NULL,
  document_ref VARCHAR(100),
  effective_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL CHECK (status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')),
  rules_definition JSONB NOT NULL,                 -- full policy JSON (see Section 4)
  parent_version_id VARCHAR(20) REFERENCES policy_versions(version_id),
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  created_by VARCHAR(100)
);

-- Policy Approvals (audit trail)
CREATE TABLE policy_approvals (
  id SERIAL PRIMARY KEY,
  version_id VARCHAR(20) NOT NULL REFERENCES policy_versions(version_id),
  action VARCHAR(20) NOT NULL CHECK (action IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'ACTIVATED', 'SUPERSEDED')),
  actor VARCHAR(100) NOT NULL,
  performed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  change_summary TEXT                              -- plain-language diff auto-generated by LLM
);
```

### 3.4 Operational Tables (PR Batches → Requirements → POs)

```sql
-- PR Batches (uploaded CSVs or collected chat PRs)
CREATE TABLE pr_batches (
  batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_name VARCHAR(255) NOT NULL,
  source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('CSV_UPLOAD', 'CHAT', 'API')),
  uploaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  uploaded_by VARCHAR(100),
  raw_file_path TEXT
);

-- Individual PR Lines (immutable after ingestion)
CREATE TABLE pr_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id UUID NOT NULL REFERENCES pr_batches(batch_id),
  pr_no VARCHAR(50) NOT NULL,
  pr_line INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  requester VARCHAR(100),
  department VARCHAR(100),
  plant VARCHAR(10),
  item_code VARCHAR(20),                          -- raw from CSV; may be null
  description TEXT,
  quantity NUMERIC(12, 3),
  uom VARCHAR(20),
  estimated_unit_price NUMERIC(14, 4),
  need_by_date DATE,
  urgency VARCHAR(20),
  ingestion_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
    CHECK (ingestion_status IN ('PENDING', 'VALID', 'NOT_PROCESSED')),
  not_processed_reason TEXT,
  UNIQUE (batch_id, pr_no, pr_line)
);

-- Batch Execution Runs
CREATE TABLE batch_execution_runs (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id UUID NOT NULL REFERENCES pr_batches(batch_id),
  policy_version_id VARCHAR(20) NOT NULL REFERENCES policy_versions(version_id),
  executed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  executed_by VARCHAR(100),
  status VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
    CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
  total_pr_lines INT,
  total_requirements INT,
  total_pos INT,
  total_sourcing_requests INT,
  total_not_processed INT,
  error_log TEXT
);

-- Requirement Groups (after clubbing)
CREATE TABLE requirements (
  requirement_id VARCHAR(100) PRIMARY KEY,        -- e.g., REQ-001, REQ-002
  run_id UUID NOT NULL REFERENCES batch_execution_runs(run_id) ON DELETE CASCADE,
  resolved_item_code VARCHAR(20),                 -- NULL if NEW item
  is_new_item BOOLEAN NOT NULL DEFAULT FALSE,
  plant VARCHAR(10),
  requirement_date DATE NOT NULL,                 -- created_at.date() of first line
  total_quantity NUMERIC(12, 3) NOT NULL,
  uom VARCHAR(20),
  urgency VARCHAR(20) NOT NULL DEFAULT 'Normal',
  unit_price NUMERIC(14, 4),
  group_value_inr NUMERIC(14, 2),
  price_source VARCHAR(50),                       -- 'CONTRACT_RATE', 'PO_HISTORY', 'STD_PRICE', 'ESTIMATED'
  winning_contract_id VARCHAR(50),
  decision VARCHAR(30),
  route VARCHAR(30),
  supplier_id VARCHAR(20),
  po_id VARCHAR(50),
  suggested_supplier_ids TEXT,                    -- semicolon-separated
  policy_version_id VARCHAR(20),
  policy_clause VARCHAR(20),
  reason TEXT
);

-- Individual PR lines linked to their requirement group
CREATE TABLE requirement_lines (
  id SERIAL PRIMARY KEY,
  requirement_id VARCHAR(100) NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
  pr_line_id UUID NOT NULL REFERENCES pr_lines(id),
  UNIQUE (requirement_id, pr_line_id)
);

-- PO Headers (consolidated)
CREATE TABLE po_headers (
  po_id VARCHAR(50) PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES batch_execution_runs(run_id) ON DELETE CASCADE,
  supplier_id VARCHAR(20) NOT NULL REFERENCES supplier_master(supplier_id),
  plant VARCHAR(10) NOT NULL REFERENCES plants(plant_code),
  route VARCHAR(30) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- PO Lines (one per requirement that joined a PO)
CREATE TABLE po_lines (
  id SERIAL PRIMARY KEY,
  po_id VARCHAR(50) NOT NULL REFERENCES po_headers(po_id) ON DELETE CASCADE,
  requirement_id VARCHAR(100) NOT NULL REFERENCES requirements(requirement_id),
  item_code VARCHAR(20),
  quantity NUMERIC(12, 3),
  uom VARCHAR(20),
  unit_price NUMERIC(14, 4),
  line_value_inr NUMERIC(14, 2)
);

-- Buyer Actions (approvals, overrides, audit trail)
CREATE TABLE buyer_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES batch_execution_runs(run_id),
  requirement_id VARCHAR(100) REFERENCES requirements(requirement_id),
  action VARCHAR(30) NOT NULL CHECK (action IN ('APPROVED', 'OVERRIDDEN', 'REJECTED', 'HELD')),
  buyer_id VARCHAR(100) NOT NULL,
  performed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  override_reason TEXT,                           -- mandatory if action = 'OVERRIDDEN'
  previous_route VARCHAR(30),
  new_route VARCHAR(30),
  previous_supplier_id VARCHAR(20),
  new_supplier_id VARCHAR(20)
);

-- Immutable Audit Log (append-only)
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR(50) NOT NULL,
  entity_type VARCHAR(50),
  entity_id TEXT,
  actor VARCHAR(100),
  event_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  payload JSONB NOT NULL
);
```

---

## 4. Policy JSON Schema (Corrected — Supports Nested Logic)

The policy is stored as JSONB in `policy_versions.rules_definition`. The schema supports:
- **Nested AND/OR/NOT** condition expressions
- **Priority ordering** via `priority` field (lower = evaluated first)
- **Configurable outcomes** with parameterized supplier counts
- **Plant-specific conditions** via `plant_scope`
- **Category-specific conditions**

### 4.1 Canonical v5.0 Policy JSON Structure

```json
{
  "policy_version": "v5.0",
  "document_ref": "CORVO-PROC-POL-04",
  "effective_date": "2026-04-01",
  "parameters": {
    "clubbing_window_days": 14,
    "need_by_window_days": 7,
    "po_history_lookback_days": 365,
    "preferred_supplier_lookback_days": 548,
    "po_consolidation_window_hours": 24,
    "supplier_ranking_weights": {
      "po_frequency": 0.25,
      "recency": 0.25,
      "contract_held": 0.20,
      "on_time_delivery": 0.15,
      "quality_rating": 0.15
    },
    "recency_buckets": [
      {"max_days": 90, "score": 1.0},
      {"max_days": 365, "score": 0.5},
      {"otherwise": 0.0}
    ]
  },
  "global_constraints": [
    {
      "constraint_id": "5.7",
      "description": "Blocked/Inactive suppliers must never be used",
      "applies_to": "ALL_SUPPLIER_SELECTION",
      "condition": {"field": "supplier.status", "operator": "NOT_IN", "value": ["Blocked", "Inactive"]}
    }
  ],
  "decision_rules": [
    {
      "rule_id": "5.1",
      "priority": 1,
      "clause": "Clause 5.1",
      "description": "Capex items always route to sourcing",
      "plant_scope": null,
      "condition": {
        "AND": [
          {"field": "item.item_type", "operator": "EQUALS", "value": "Capex"}
        ]
      },
      "outcome": {
        "decision": "SOURCING_REQUEST",
        "route": "CAPEX_SOURCING",
        "suggest_suppliers_count": 5,
        "flags": ["REQUIRES_CAPEX_APPROVAL"]
      }
    },
    {
      "rule_id": "5.2",
      "priority": 2,
      "clause": "Clause 5.2",
      "description": "Valid rate contract with ceiling room",
      "condition": {
        "AND": [
          {"field": "contract.has_valid_active_contract", "operator": "EQUALS", "value": true},
          {"field": "contract.has_ceiling_room", "operator": "EQUALS", "value": true}
        ]
      },
      "outcome": {
        "decision": "PO",
        "route": "CONTRACT_PO",
        "supplier_source": "WINNING_CONTRACT",
        "price_source": "CONTRACT_RATE"
      }
    },
    {
      "rule_id": "5.3",
      "priority": 3,
      "clause": "Clause 5.3",
      "condition": {
        "AND": [
          {"field": "requirement.urgency", "operator": "EQUALS", "value": "Emergency"},
          {"field": "requirement.group_value_inr", "operator": "LESS_THAN_OR_EQUAL", "value": 500000},
          {"field": "history.bought_from_active_in_365d", "operator": "EQUALS", "value": true}
        ]
      },
      "outcome": {
        "decision": "PO",
        "route": "EMERGENCY_PO",
        "supplier_source": "FIRST_PREFERRED",
        "price_source": "SUPPLIER_REFERENCE_PRICE"
      }
    },
    {
      "rule_id": "5.4",
      "priority": 4,
      "clause": "Clause 5.4",
      "condition": {
        "AND": [
          {"field": "requirement.group_value_inr", "operator": "LESS_THAN", "value": 200000},
          {"field": "history.bought_from_active_in_365d", "operator": "EQUALS", "value": true}
        ]
      },
      "outcome": {
        "decision": "PO",
        "route": "SPOT_PO",
        "supplier_source": "FIRST_PREFERRED",
        "price_source": "SUPPLIER_REFERENCE_PRICE"
      }
    },
    {
      "rule_id": "5.5",
      "priority": 5,
      "clause": "Clause 5.5",
      "condition": {
        "AND": [
          {"field": "requirement.group_value_inr", "operator": "LESS_THAN", "value": 1000000}
        ]
      },
      "outcome": {
        "decision": "SOURCING_REQUEST",
        "route": "RFQ",
        "suggest_suppliers_count": 3
      }
    },
    {
      "rule_id": "5.6",
      "priority": 6,
      "clause": "Clause 5.6",
      "condition": {
        "AND": [
          {"field": "requirement.group_value_inr", "operator": "GREATER_THAN_OR_EQUAL", "value": 1000000}
        ]
      },
      "outcome": {
        "decision": "SOURCING_REQUEST",
        "route": "RFP",
        "suggest_suppliers_count": 5
      }
    }
  ]
}
```

### 4.2 Policy Engine Interpreter Design
The engine never hardcodes any rule. It:
1. Loads the active `policy_versions.rules_definition` JSON
2. Sorts `decision_rules` by `priority` ascending
3. For each requirement, evaluates conditions using a recursive expression interpreter supporting `AND`, `OR`, `NOT`
4. Returns the outcome of the first matching rule
5. This means: changing ₹2L to ₹3L requires only a JSON edit and policy version bump — no code change

### 4.3 Policy Amendment Workflow
1. Procurement Admin uploads amendment document (PDF or text) or describes change in chat
2. LLM extracts structured diff (new/changed parameter values or rule conditions)
3. System generates **plain-language diff** shown to admin: "Spot PO limit changing from ₹2,00,000 to ₹3,00,000; RFQ window changing from ₹10L to ₹15L"
4. Admin reviews and approves → system creates new `policy_versions` row with `status='DRAFT'` → Head of Procurement activates → `status='ACTIVE'`, old version becomes `status='SUPERSEDED'`
5. All subsequent batch runs pick up the new active policy

> [!IMPORTANT]
> **Blind-test policy version selection**: During blind-test Run 1, process under `v5.0`. During Run 2 (after uploading amendment), the app reprocesses using the **explicitly selected policy version** (not date-based lookup). The UI allows selecting a specific version for reprocessing. The API also accepts an optional `policy_version_id` parameter.

---

## 5. Module Interfaces

### 5.1 Core Engine Python Modules

```
engine/
├── ingestion.py          — parse & validate CSV; sort; flag NOT_PROCESSED rows
├── item_matcher.py       — deterministic fuzzy match (normalized token overlap score)
│                           must flag confidence < threshold for buyer confirmation
├── clubber.py            — anti-splitting requirement grouping
├── valuator.py           — price waterfall (contract rate → PO history → std price)
├── contract_checker.py   — 4.1-4.4 logic; supplier status gate; ceiling ledger
├── decision_engine.py    — loads policy JSON; evaluates rules 5.1-5.6; applies 5.7 gate
├── supplier_ranker.py    — 6.1-6.4 logic; composite score; backfill logic
├── po_consolidator.py    — 7.1-7.2 logic; 24-hour window; PO ID assignment
├── policy_loader.py      — loads active/specified policy version from DB
├── ceiling_ledger.py     — run-specific in-memory ceiling state; init from DB; commit on completion
└── batch_runner.py       — orchestrates all stages in order for a given run
```

### 5.2 LLM Gateway Modules

```
llm/
├── chat_extractor.py     — slot-filling: extract item, qty, plant, need_by_date, urgency
│                           from conversational input; returns structured JSON + confidence
├── policy_parser.py      — parse policy amendment doc; return structured diff JSON
└── prompts/
    ├── chat_intake.txt
    └── policy_amendment.txt
```

### 5.3 API Endpoints

```
POST /api/process-batch         — Upload PR batch CSV; returns run_id
GET  /api/runs/{run_id}         — Get run status and summary
GET  /api/runs/{run_id}/export  — Download decision CSV
POST /api/chat                  — Submit chat message; returns assistant response + PR draft
POST /api/chat/{pr_id}/confirm  — Confirm and create PR from chat session
POST /api/contracts             — Upload new contract (PDF or manual entry)
POST /api/policy/upload         — Upload policy amendment doc; returns diff preview
POST /api/policy/{version_id}/approve — Approve and activate policy version
GET  /api/preferred-suppliers   — Get preferred supplier list as of a date (CSV export)
POST /api/requirements/{id}/approve — Buyer approves a decision
POST /api/requirements/{id}/override — Buyer overrides with mandatory reason
```

### 5.4 Item Matching — Confidence Handling

**[ASSUMPTION — REVIEW REQUIRED]**: The following confidence thresholds were not specified by the policy. They are design decisions:

| Confidence Score | Handling |
|-----------------|----------|
| ≥ 0.90 | Auto-resolve; log match in audit |
| 0.60–0.89 | Present top 3 candidates to requester; require confirmation before PR is created |
| < 0.60 | Treat as NEW item; ask requester if they want to flag as new item |

The chat intake assistant will never invent an item code. If it cannot confidently match, it shows candidates and asks.

---

## 6. Output Format

One row per PR line in the input:

| Column | Content |
|--------|---------|
| `pr_no` | As in input |
| `pr_line` | As in input |
| `resolved_item_code` | Matched item code, or `NEW` |
| `group_id` | Requirement group ID. Clubbed lines share it. |
| `po_id` | PO number for lines ending in a PO. Consolidated POs share it. |
| `decision` | `PO`, `SOURCING_REQUEST`, or `NOT_PROCESSED` |
| `route` | `CONTRACT_PO`, `EMERGENCY_PO`, `SPOT_PO`, `RFQ`, `RFP`, `CAPEX_SOURCING`, `NEW_ITEM_SOURCING`, `NOT_PROCESSED` |
| `supplier_id` | For POs |
| `unit_price` | For POs |
| `group_value_inr` | Value of whole requirement |
| `suggested_supplier_ids` | For sourcing, ranked, semicolon-separated |
| `policy_version` | Version applied |
| `reason` | Clause applied and contract/PO relied on |

---

## 7. Processing Pipeline (Corrected Stage Count)

```
Stage 0: Seed database with master data (item master, supplier master, plants, PO history, contracts)
Stage 1: Load PDF-only contracts (parse RC-2026-031 and RC-2026-033 from PDFs)
Stage 2: Ingest PR batch CSV → validate → sort → flag NOT_PROCESSED (qty=0, invalid plant)
Stage 3: Item matching → deterministic fuzzy match → resolve item_code or mark NEW
Stage 4: Requirement clubbing → group by (item, plant, 14-day window, 7-day need-by)
Stage 5: Initialize run-specific ceiling ledger from current DB state
Stage 6: Valuation → price waterfall per group → group_value_inr
Stage 7: Policy rule evaluation → apply rules 5.1→5.6 in order (5.7 is gate, not rule)
Stage 8: Supplier ranking → composite score → preferred supplier list → suggestions
Stage 9: PO consolidation → 24-hour same-supplier/plant/route grouping
Stage 10: Persist results → commit ceiling ledger to DB → generate audit records
Stage 11: Buyer workspace → present decisions → await approve/override
Stage 12: Export → CSV in required format
```

---

## 8. UI Screens

### Screen 1: Employee Chat (Requester)
- Conversational chat interface
- Assistant extracts item/qty/plant/need_by/urgency
- Shows matched item with confidence indicator; asks if ambiguous
- Confirms PR details before creating
- Also accepts: "upload a batch CSV"

### Screen 2: Buyer Workspace
- List of all requirements from active runs
- Per-requirement card: PR lines, decision, route, value, supplier, reason (clause + contract/PO reference)
- One clear CTA per card: **[Approve PO]** or **[Approve Sourcing Request]**
- **[Override]** button → requires mandatory typed reason
- Filter by: status (pending/approved/overridden), route, plant, value range

### Screen 3: Policy & Contract Admin
- Current active policy version + history
- **[Upload Amendment]** → shows plain-language diff → **[Approve & Activate]**
- Contract list; **[Add PDF Contract]** → auto-extracts or manual entry

### Screen 4: Batch Processing
- Upload CSV → Run processing → View progress → Export CSV
- Run history with ability to re-export any prior run
- Policy version selector for reprocessing

### Screen 5: Preferred Supplier Lists
- Select item + as-of date → view ranked supplier list with scores
- Export as CSV

---

## 9. DECISIONS.md Items (Pre-planned)

The following are ambiguities I've identified where the policy is silent or unclear. Each will be documented in `DECISIONS.md` with reasoning:

1. **Valuation active-supplier filter**: Policy 3.1 says "most recent PO for the item in 365 days" for pricing. It does not say "from Active supplier" (that's the eligibility test in 5.3/5.4). **Decision**: Apply active-supplier filter to price lookup too, to avoid using prices from blocked/inactive suppliers. Reason: policy 5.7 intent is to exclude compromised suppliers from all aspects of procurement.

2. **Rounding of group_value_inr**: Policy math produces decimal values (e.g., ₹1,37,530.65). Worked example shows "₹1,37,531". **Decision**: Round to nearest rupee for group_value_inr in output. Use full precision for internal ceiling comparisons.

3. **Zero-quantity PR line (PR-26-00172)**: Policy doesn't address. **Decision**: NOT_PROCESSED.

4. **Unknown plant PUN2 (PR-26-00173)**: Policy applies only to PUN1 and CHK1. **Decision**: NOT_PROCESSED.

5. **Insufficient sourcing suggestions (Worked Example 11, Electrical Spares has 4 suppliers)**: **Decision**: Output all available active suppliers in category; never duplicate IDs to reach target count.

6. **Supplier ranking weights**: The policy mandates factors but not weights. **Decision**: Use composite formula above; validate against 3 worked examples; if any ranking disagrees, adjust weights and document.

7. **24-hour PO consolidation boundary — same-day vs. timestamp precision**: **Decision**: Use exact timestamp difference in total seconds ≤ 86,400.

8. **Missing estimated_unit_price on NEW items**: **Decision**: If `estimated_unit_price` is null on a NEW item, the value cannot be computed. Mark as NOT_PROCESSED with reason "Missing estimated unit price for unmatched item."

9. **Policy effective-date vs. explicit version for reprocessing**: **Decision**: The API and UI both accept an explicit `policy_version_id` for reprocessing. If not supplied, use the policy version that was ACTIVE on the batch's processing date. This handles the blind-test requirement cleanly.

10. **Multi-line PRs (e.g., PR-26-00164 has 4 lines)**: Each line is treated independently through item matching and clubbing. They may end up in different requirement groups.

---

## 10. Implementation Roadmap (Realistic — 3 Days)

> [!IMPORTANT]
> Build deadline: **Thursday 19 Nov 10:00 AM IST** (~68 hours from now). Prioritize working end-to-end over feature completeness. A correct engine with basic UI beats an impressive UI with broken decisions.

### Day 1 (Today, Mon 16 Nov): Foundation + Decision Engine

**Morning (Hours 0–4)**:
- [ ] Project scaffold: `docker-compose.yml`, FastAPI app, React app
- [ ] PostgreSQL schema creation (all tables from Section 3)
- [ ] Data seeding: load all CSVs (items, suppliers, plants, PO history, contracts)
- [ ] Parse PDF-only contracts (RC-2026-031, RC-2026-033) using pdfplumber

**Afternoon (Hours 4–8)**:
- [ ] `ingestion.py`: CSV parse, sort, flag NOT_PROCESSED
- [ ] `item_matcher.py`: Deterministic token-overlap match with confidence scoring
- [ ] `clubber.py`: Requirement grouping algorithm
- [ ] `valuator.py`: Price waterfall

**Evening (Hours 8–14)**:
- [ ] `contract_checker.py`: 4.1–4.4 logic + supplier status gate
- [ ] `ceiling_ledger.py`: Run-specific in-memory ledger
- [ ] `policy_loader.py`: Load JSON from DB; seed v5.0 JSON
- [ ] `decision_engine.py`: Recursive condition evaluator; rule priority loop
- [ ] `supplier_ranker.py`: Composite score + backfill
- [ ] `po_consolidator.py`: 24-hour window grouping
- [ ] `batch_runner.py`: Full pipeline integration
- [ ] **Test against all 14 worked examples** — verify each one matches expected output

### Day 2 (Tue 17 Nov): API + UI + Policy-as-Data

**Morning (Hours 0–6)**:
- [ ] FastAPI endpoints: `/api/process-batch`, `/api/runs/{id}/export`, `/api/preferred-suppliers`
- [ ] `POST /api/process-batch` integration test with sample_pr_batch.csv
- [ ] React frontend: Batch upload screen, results table, CSV export
- [ ] Buyer workspace: requirement cards with approve/override

**Afternoon (Hours 6–12)**:
- [ ] Policy version management: upload amendment → LLM diff extraction → plain-language preview → approve/activate
- [ ] Contract admin: PDF upload → pdfplumber extraction → manual confirmation
- [ ] Policy admin screens in UI

**Evening (Hours 12–18)**:
- [ ] Chat intake: LLM slot-filling, confidence-based item matching, confirmation flow
- [ ] `DECISIONS.md` — write all decisions
- [ ] `APPROACH.md` — document tools used

### Day 3 (Wed 18 Nov): Polish, Tests, Deploy

**Morning (Hours 0–6)**:
- [ ] Unit tests: clubber edge cases, ceiling depletion, 24-hour PO consolidation
- [ ] Regression test suite against all 14 worked examples (automated)
- [ ] Validate supplier ranking weights against 3 example preferred supplier lists
- [ ] Fix any bugs found

**Afternoon (Hours 6–12)**:
- [ ] Deploy to Railway/Render; configure hosted Postgres
- [ ] End-to-end smoke test on hosted app
- [ ] README with docker compose up instruction
- [ ] Final DECISIONS.md review

**Day 3 Evening / Thu Morning**:
- [ ] Final review; ensure hosted app is live and stable
- [ ] Submit GitHub repo link + hosted app link via submission form by 10:00 AM IST

### Blind Test (Thu 19 Nov 10:00 AM – 12:00 Noon)
1. Receive new PR batch + policy amendment
2. **Run 1**: Process new batch under v5.0 → export CSV
3. **Run 2**: Upload amendment → approve → reprocess same batch → export CSV
4. Export preferred supplier lists as of given date
5. Push 3 CSVs to `submission/` folder in GitHub repo by **12:00 noon IST**

---

## 11. Risk Register

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Clubbing algorithm bug (wrong ordering) | Critical | Test against worked examples 3, 5, 14 specifically |
| PDF contract parsing failure | High | Manual fallback: hardcode RC-2026-031 and RC-2026-033 data as seed migration |
| Ceiling ledger not run-isolated (double-consumption) | High | Ceiling ledger initialized per run_id; never shared between runs |
| Blocked supplier slipping through | Critical | Supplier status check is the first gate in ALL supplier selection paths |
| LLM hallucinating item codes | High | LLM only extracts fields; item matching is always deterministic code |
| Policy JSON too rigid for amendment | Medium | JSON schema supports nested conditions; validate with hypothetical amendment before submission |
| Hosted deployment down during blind test | High | Test deployment 24h before deadline; have Railway backup |

---

## 12. What the Previous Blueprint Got Wrong (Corrections Applied)

| Feedback Item | What Was Wrong | What We Fixed |
|---------------|----------------|---------------|
| 1. Clause 5.7 placement | Treated as an independent DISQUALIFIED route | Now a global constraint gate applied before ALL supplier selection |
| 2. PO price vs. eligibility | Mixed up price lookup with active-history eligibility check | Separated: price waterfall (3.1) vs. eligibility flag (5.3/5.4) — both documented as assumptions in DECISIONS.md |
| 3. Supplier ranking weights | Presented as confirmed policy | Explicitly marked as [ASSUMPTION — REVIEW REQUIRED]; validated against 3 worked examples |
| 4. Contract consumption ledger | No mention of run isolation | Added `contract_consumption_log` table + run-specific in-memory ledger |
| 5. Policy effective-date vs. version | Date-only selection | UI + API support explicit `policy_version_id` for reprocessing |
| 6. Incomplete database schema | Missing: PR batches, PR lines, requirements, requirement_lines, PO headers, PO lines, consumption log, policy approvals, audit_log | Full schema provided in Section 3 |
| 7. Policy JSON too flat | No nested conditions, no plant-scope | JSON schema redesigned with AND/OR/NOT, plant_scope, priority, global_constraints |
| 8. Data verification gaps | Fabricated some statistics | All statistics now verified directly from files (Section 1.3) |
| 9. Item match confidence | No handling for ambiguous matches | Confidence scoring + 3-tier handling + requester confirmation flow |
| 10. Pipeline stage count | Fabricated "14 stages" | Accurate 12-stage pipeline with correct descriptions |
| 11. Implementation roadmap | Fantasy timeline | Realistic 3-day roadmap prioritizing working engine over features |