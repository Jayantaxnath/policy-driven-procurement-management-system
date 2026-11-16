# DECISIONS.md — Architecture & Policy Judgment Log
**Company**: Corvo Engineering Pvt Ltd  
**Project**: Policy-Driven PR-to-PO Platform  
**Author**: Full-Stack Development Team  
**Evaluation Reference**: Cantill.ai Full-Stack Intern Task Brief Section 3 & Policy v5.0

> *"The policy does not cover every situation you will meet in the data, and that is deliberate. When it is silent or ambiguous, make a sensible business decision, implement it, and record it in DECISIONS.md: what you noticed, what you decided, and why."*

---

## 1. Zero-Quantity Requisition Line (`PR-26-00172`)

- **Observation in Data**: Row 182 of `sample_pr_batch.csv` contains `quantity = 0` for `ITM-1020` (Cutting wheel 14 inch).
- **Ambiguity**: The policy does not specify whether to reject, ask for clarification, or treat zero quantity as a cancelled PR.
- **Decision**: Mark route as `NOT_PROCESSED`, decision as `NOT_PROCESSED`, with reason: `"Invalid quantity: 0. Requisition line rejected."`
- **Justification**: A purchase order or quotation cannot legally or operationally be raised for zero units. Ingesting this into clubbing would corrupt requirement valuation. Section 4 of the Task Brief explicitly provides the `NOT_PROCESSED` route for lines not processed.

---

## 2. Unrecognized Factory Plant (`PR-26-00173`)

- **Observation in Data**: Row 183 of `sample_pr_batch.csv` contains `plant = PUN2` for `ITM-1045` (PP strapping roll).
- **Ambiguity**: `plants.csv` lists only `PUN1` (Bhosari) and `CHK1` (Chakan). Policy Header states jurisdiction applies strictly to `PUN1` and `CHK1`.
- **Decision**: Do not club. Emit `decision: NOT_PROCESSED`, `route: NOT_PROCESSED`, reason: `"Invalid plant: PUN2 not recognized in Corvo operating plants."`
- **Justification**: Procurement cannot dispatch purchase orders or delivery schedules to an unchartered plant location without master data registration.

---

## 3. Disqualification of Active Contract with Blocked Supplier (`RC-2026-005` / `S004`)

- **Observation in Data**: In `contract_register.csv`, contract `RC-2026-005` covers `ITM-1006` (Aluminium plate) and `ITM-1007` (MS flat) with ₹26,00,000 ceiling remaining. However, `supplier_master.csv` lists supplier `S004` (Metalink Alloys) with `status = 'Blocked'`.
- **Ambiguity**: Does an existing, signed rate contract supersede a supplier's blocked status?
- **Decision**: Contract `RC-2026-005` is completely disqualified from receiving direct POs. Requisitions for `ITM-1006` and `ITM-1007` cannot use this contract and route to competitive RFQ.
- **Justification**: Policy Clause 4.1 explicitly states: *"the contract supplier is Active in the supplier master."* Clause 5.7 reinforces: *"Blocked or Inactive suppliers must never receive a PO or be suggested for a sourcing event."* A blocked supplier may have failed quality, safety, or legal audits. Awarding POs solely based on contract register data is a critical compliance breach. This is proven by Worked Example 10 (`PR-26-00050/1`).

---

## 4. Valuation Waterfall vs. Eligibility Filter on PO History

- **Observation in Data**: Policy Clause 3.1(b) states valuation uses the price on the most recent PO in the 365 days before requirement date. Policy Clauses 5.3 and 5.4 require that the item was bought from an *Active* supplier in the last 365 days.
- **Ambiguity**: When evaluating price in Clause 3.1(b), should POs from Blocked/Inactive suppliers be used if they were the most recent?
- **Decision**: Filter out Blocked/Inactive suppliers from the valuation PO lookup as well, using the most recent PO from an **Active** supplier.
- **Justification**: Using prices negotiated with now-blocked suppliers may reflect compromised or non-market pricing. Applying the Active supplier filter across both valuation and eligibility ensures internal consistency.

---

## 5. PO History Tie-Breaking on Identical Dates (Worked Example 11 Reconciliation)

- **Observation in Data**: For `ITM-1034` (Worked Example 11, `PR-26-00100/1`), on date `2026-04-10`, two historical POs exist: `7300215` (unit price ₹40,929.88) and `7300220` (unit price ₹41,415.60).
- **Ambiguity**: Which PO represents the "most recent" when multiple POs occur on the same day?
- **Decision**: Sort historical POs by `(po_date DESC, po_number DESC)`.
- **Justification**: PO numbers are sequentially issued by the ERP. Higher PO numbers on the same date reflect the later chronological transaction. This yields unit price ₹41,415.60, resulting in requirement value $50 \times 41,415.60 = ₹20,70,780$, which matches Worked Example 11 to the exact rupee.

---

## 6. Calendar Days Truncation vs. Exact Timestamps for Clubbing

- **Observation in Data**: Policy Clause 2.2 defines the clubbing window as "created within 14 calendar days of the requirement's first line" and need-by date "within 7 days (either side)".
- **Ambiguity**: Does "14 calendar days" mean $14 \times 24 = 336$ hours from the first line's timestamp, or calendar date difference?
- **Decision**: Compare dates strictly at calendar date level:  
  $0 \le (\text{line.created\_at.date}() - \text{first\_line.created\_at.date}()).\text{days} \le 14$  
  and  
  $|\text{line.need\_by\_date} - \text{first\_line.need\_by\_date}| \le 7\text{ days}$.
- **Justification**: In factory operations, procurement requisitions are scheduled on daily manufacturing shifts. Truncating to calendar dates prevents shift-timing discrepancies and replicates Worked Example 5.

---

## 7. Multi-Factor Supplier Ranking Formulation (Section 6)

- **Observation in Data**: Policy Clause 6.2 mandates ranking based on PO frequency, recency, contract history, on-time delivery %, and quality rating, but deliberately leaves the exact weighting to system design.
- **Decision**: Implemented the following normalized composite score:
  $$S = 0.25 \cdot \min\left(\frac{N_{\text{po}}}{5}, 1.0\right) + 0.25 \cdot R + 0.20 \cdot C + 0.15 \cdot \left(\frac{\text{on\_time\_pct}}{100}\right) + 0.15 \cdot \left(\frac{\text{quality\_rating}}{5.0}\right)$$
  - **Recency ($R$)**: $1.0$ if most recent PO $\le 90$ days; $0.5$ if $\le 365$ days; $0.0$ if older.
  - **Contract ($C$)**: $1.0$ if supplier holds or held a contract for item starting on or before requirement date; else $0.0$.
  - **Tie-Breaker**: Score DESC $\to$ On-time % DESC $\to$ Quality rating DESC $\to$ Supplier ID ASC.
- **Justification & Verification**: This formula was validated against all three example preferred supplier lists in `Worked_Examples.pdf` (page 5):
  - `ITM-1048`: S029 (Rank 1), S030 (Rank 2), S031 (Excluded — Inactive).
  - `ITM-1036`: S023 (Rank 1), S022 (Rank 2), S024 (Rank 3).
  - `ITM-1016`: S009 (Rank 1), S010 (Rank 2).
  Every ranking matches Corvo's procurement ground truth 100%.

---

## 8. Sourcing Suggestion Backfill Limit & Zero-Padding Policy

- **Observation in Data**: Clause 6.4 requires suggesting 3 suppliers for RFQ and 5 for RFP/Capex. However, in `supplier_master.csv`, some categories have fewer active suppliers than requested (e.g., Worked Example 11, `Electrical Spares` has only 4 active suppliers).
- **Ambiguity**: Should the engine pad suggestions with fake IDs, duplicate suppliers, or cross into unrelated categories?
- **Decision**: Return all available unique active suppliers in that category without padding duplicates. For Worked Example 11, the engine suggests 4 suppliers (`S020;S019;S017;S018`).
- **Justification**: Suggesting duplicate suppliers or unqualified vendors from other trades impairs commercial bidding. Worked Example 11 explicitly confirms Corvo accepts fewer than 5 when the supplier base is exhausted.

---

## 9. Run-Specific Contract Ceiling Ledger (Isolation Guarantee)

- **Observation in Data**: Contract ceiling consumption is sequential by requirement date across a batch.
- **Ambiguity**: If a user runs batch reprocessing (e.g., during blind test Run 1 vs Run 2) or runs tests, database updates would double-consume ceiling.
- **Decision**: Implemented an in-memory `RunCeilingLedger` initialized fresh from persistent database state at the beginning of each batch run. Dynamic deductions occur in this ledger and are recorded in `contract_consumption_log` tied to the specific `run_id`.
- **Justification**: Guarantees deterministic reproducibility. Rerunning a batch or simulating amendments does not mutate master contract caps until approved.

---

## 10. Valuation of Uncataloged NEW Items (`Clause 1.2`)

- **Observation in Data**: Free-text items not matching `item_master` route to `NEW_ITEM_SOURCING`.
- **Ambiguity**: If an uncataloged item lacks an `estimated_unit_price` in the PR, how is it valued?
- **Decision**: If `estimated_unit_price` is provided, value = $\text{quantity} \times \text{estimated\_unit\_price}$. If missing, group value is recorded as $0.0$ and flagged for buyer price estimation during sourcing.
- **Justification**: Matches Clause 1.2 and Worked Example 13 (`PR-26-00170/1`, Drinking water purifier valued at ₹1,41,100).
