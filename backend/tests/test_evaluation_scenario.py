"""
Thursday 19 Nov Evaluation Scenario Simulation.

Run 1: Process sample_pr_batch.csv under v5.0 -> verify every row outputs v5.0 -> export decisions CSV.
Run 2: Upload amendment v5.1 (emergency threshold 750000, RFQ threshold 300000) -> approve & activate
       -> reprocess the exact same batch -> verify every row outputs v5.1 and routes reflect new rules
       -> export decisions CSV -> export preferred suppliers CSV.

Both runs must work correctly, and exported results must accurately reflect the policy version used.
"""
import sys
import os
import io
import csv
import uuid
import asyncio
import pandas as pd
from datetime import date, datetime

# Ensure backend in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SyncSessionLocal
from app.engine.pipeline import process_pr_batch
from app.db.models import (
    PolicyVersion, PolicyApproval, BatchExecutionRun,
    PRBatch, PRLine, Requirement, RequirementLine,
)
from app.api.routes import policy, batch
from fastapi.responses import StreamingResponse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KIT_DIR = os.path.join(ROOT_DIR, "Cantill_FullStack_Task_Kit")
BATCH_CSV = os.path.join(KIT_DIR, "pr_batches", "sample_pr_batch.csv")
EXPORT_DIR = os.path.join(ROOT_DIR, "submission")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def save_csv(content_bytes, filename):
    ensure_dir(EXPORT_DIR)
    path = os.path.join(EXPORT_DIR, filename)
    with open(path, "wb") as f:
        f.write(content_bytes)
    print(f"   Exported: {path}")


def get_body_bytes(response: StreamingResponse) -> bytes:
    chunks = []

    async def _collect():
        async for chunk in response.body_iterator:
            chunks.append(chunk)

    asyncio.run(_collect())
    return b"".join(chunks)


def parse_created(val):
    if isinstance(val, str):
        return datetime.strptime(val.strip(), "%Y-%m-%d %H:%M")
    if isinstance(val, datetime):
        return val
    return datetime.now()


def parse_need_by(val, created_at):
    if isinstance(val, str):
        return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    if isinstance(val, date):
        return val
    return created_at.date()


def persist_batch_run(session, run_id, batch_id, df_batch, decision_rows, policy_version_id):
    """
    Replicates the DB persistence done by the /api/process-batch route handler
    (batch.py lines 44-170) so that export_run_csv can query Requirements.
    """
    # PRBatch record
    batch_rec = PRBatch(batch_id=batch_id, batch_name=f"eval-batch-{batch_id[:8]}", source_type="CSV_UPLOAD")
    session.add(batch_rec)
    session.commit()

    # Execution run record
    exec_run = BatchExecutionRun(
        run_id=run_id,
        batch_id=batch_id,
        policy_version_id=policy_version_id,
        status="COMPLETED",
        total_pr_lines=len(decision_rows),
        total_requirements=len(set(d["group_id"] for d in decision_rows)),
        total_pos=len(set(d["po_id"] for d in decision_rows if d.get("po_id"))),
        total_sourcing_requests=len([d for d in decision_rows if d.get("decision") == "SOURCING_REQUEST"]),
        total_not_processed=len([d for d in decision_rows if d.get("decision") == "NOT_PROCESSED"]),
    )
    session.add(exec_run)
    session.commit()

    # Persist PR lines
    pr_line_map = {}
    for _, r in df_batch.iterrows():
        p_no = str(r["pr_no"]).strip()
        p_line = int(r["pr_line"])
        pr_id = str(uuid.uuid4())
        pr_obj = PRLine(
            id=pr_id,
            batch_id=batch_id,
            pr_no=p_no,
            pr_line=p_line,
            created_at=parse_created(r.get("created_at")),
            plant=str(r.get("plant", "")).strip() if pd.notna(r.get("plant")) else None,
            item_code=str(r.get("item_code", "")).strip() if pd.notna(r.get("item_code")) else None,
            description=str(r.get("description", "")),
            quantity=float(r.get("quantity", 0) or 0),
            uom=str(r.get("uom", "NOS")).strip(),
            estimated_unit_price=float(r.get("estimated_unit_price", 0) or 0) if pd.notna(r.get("estimated_unit_price")) else None,
            need_by_date=parse_need_by(r.get("need_by_date"), parse_created(r.get("created_at"))),
            urgency=str(r.get("urgency", "Normal")),
            ingestion_status="PROCESSED",
        )
        session.add(pr_obj)
        pr_line_map[(p_no, p_line)] = pr_id

    # Group decision rows by scoped group_id (same scoping as route handler)
    req_groups = {}
    for d in decision_rows:
        raw_gid = d["group_id"]
        scoped_gid = f"{run_id[:8]}-{raw_gid}"
        d["_scoped_gid"] = scoped_gid
        if scoped_gid not in req_groups:
            req_groups[scoped_gid] = {"raw_gid": raw_gid, "decision": d, "lines": []}
        req_groups[scoped_gid]["lines"].append(d)

    # Persist Requirements and RequirementLines
    for scoped_gid, gdata in req_groups.items():
        first_d = gdata["decision"]
        is_new = (first_d.get("resolved_item_code") == "NEW")
        req_obj = Requirement(
            requirement_id=scoped_gid,
            run_id=run_id,
            resolved_item_code=first_d.get("resolved_item_code"),
            is_new_item=is_new,
            plant=first_d.get("plant"),
            requirement_date=date.today(),
            total_quantity=sum([float(l.get("quantity", 0) or 0) for l in gdata["lines"]]) or 1.0,
            uom=first_d.get("uom", "NOS"),
            urgency=first_d.get("urgency", "Normal"),
            unit_price=first_d.get("unit_price"),
            group_value_inr=first_d.get("group_value_inr"),
            price_source="WATERFALL",
            decision=first_d.get("decision"),
            route=first_d.get("route"),
            supplier_id=first_d.get("supplier_id"),
            po_id=first_d.get("po_id"),
            suggested_supplier_ids=first_d.get("suggested_supplier_ids"),
            policy_version_id=first_d.get("policy_version", policy_version_id),
            reason=first_d.get("reason"),
        )
        session.add(req_obj)

        for line in gdata["lines"]:
            key = (line["pr_no"], line["pr_line"])
            if key in pr_line_map:
                r_line = RequirementLine(
                    requirement_id=scoped_gid,
                    pr_line_id=pr_line_map[key],
                )
                session.add(r_line)

    session.commit()


def run_scenario():
    session = SyncSessionLocal()
    try:
        # ------------------------------------------------------------------
        # Sanity: ensure v5.0 is the active baseline
        # ------------------------------------------------------------------
        v50 = session.query(PolicyVersion).filter(PolicyVersion.version_id == "v5.0").first()
        assert v50 is not None, "v5.0 must be seeded in the database"
        session.query(PolicyVersion).filter(PolicyVersion.status == "ACTIVE").update({"status": "SUPERSEDED"})
        v50.status = "ACTIVE"
        session.commit()
        print("[INFO] Baseline active policy: v5.0")

        df_batch = pd.read_csv(BATCH_CSV)
        print(f"[INFO] Loaded {len(df_batch)} lines from {BATCH_CSV}")

        # ==================================================================
        # RUN 1 — Process under v5.0
        # ==================================================================
        print("\n===== RUN 1: Process batch under v5.0 =====")
        rows_v50, stats_v50 = process_pr_batch(df_batch, session, policy_version_id="v5.0")

        # Verify every row reports v5.0
        bad = [r for r in rows_v50 if r.get("policy_version") != "v5.0"]
        assert len(bad) == 0, f"{len(bad)} rows do not report v5.0 in Run 1"
        print(f"[PASS] All {len(rows_v50)} rows report policy_version = v5.0")

        # Persist run record so we can export the decisions CSV
        run_id_v50 = str(uuid.uuid4())
        batch_id_v50 = str(uuid.uuid4())
        persist_batch_run(session, run_id_v50, batch_id_v50, df_batch, rows_v50, "v5.0")

        # Export decisions CSV for Run 1
        csv_resp = batch.export_run_csv(run_id_v50, session)
        assert csv_resp.status_code == 200
        csv_bytes = get_body_bytes(csv_resp)
        save_csv(csv_bytes, f"decisions_run1_v50_{run_id_v50[:8]}.csv")

        # Verify exported CSV reflects v5.0
        csv_text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(csv_text))
        csv_rows = list(reader)
        bad_csv = [row for row in csv_rows if row.get("policy_version") != "v5.0"]
        assert len(bad_csv) == 0, f"{len(bad_csv)} CSV rows do not report v5.0"
        print(f"[PASS] Run 1 decisions CSV exported ({len(csv_bytes)} bytes), all rows = v5.0")

        # ==================================================================
        # RUN 2 — Upload v5.1 amendment, activate, reprocess
        # ==================================================================
        print("\n===== RUN 2: Upload v5.1 amendment, activate, reprocess =====")

        v51_id = "v5.1"
        existing = session.query(PolicyVersion).filter(PolicyVersion.version_id == v51_id).first()
        if existing:
            session.delete(existing)
            session.commit()

        # Upload amendment v5.1
        draft_req = policy.PolicyAmendmentJSONRequest(
            version_id=v51_id,
            name="Corvo Procurement Policy v5.1 (Evaluation Amendment)",
            effective_date="2026-12-01",
            amendment_text="Increase emergency PO threshold from 500000 to 750000 INR and increase RFQ threshold to 300000 INR",
            created_by="Evaluation Suite",
        )
        upload_res = policy.upload_policy_amendment(draft_req, session)
        assert upload_res["version_id"] == v51_id
        assert upload_res["diff_count"] > 0, "Amendment should produce a diff"
        print(f"[PASS] Uploaded draft v5.1 with {upload_res['diff_count']} diffs")

        # Activate v5.1
        app_req = policy.PolicyApprovalRequest(actor="Head of Procurement", notes="Eval activation")
        act_res = policy.activate_policy_version(v51_id, app_req, session)
        assert act_res["active_version"] == v51_id
        print(f"[PASS] Activated {act_res['active_version']}")

        # Verify the active policy now reflects v5.1 thresholds in the AST
        active_pol = policy.get_active_policy(session)
        assert active_pol["version_id"] == v51_id
        rules = active_pol["rules_definition"]

        def cond_value(rule):
            cond = rule.get("condition", {})
            if "AND" in cond:
                for c in cond["AND"]:
                    if c.get("field") == "requirement.group_value_inr":
                        return c["value"]
            return cond.get("value")

        rule53 = next(r for r in rules["decision_rules"] if r["rule_id"] == "5.3")
        rule54 = next(r for r in rules["decision_rules"] if r["rule_id"] == "5.4")
        assert cond_value(rule53) == 750000, f"Rule 5.3 threshold should be 750000, got {cond_value(rule53)}"
        assert cond_value(rule54) == 300000, f"Rule 5.4 threshold should be 300000, got {cond_value(rule54)}"
        print(f"[PASS] v5.1 AST thresholds synced: 5.3<=750000, 5.4<300000")

        # Reprocess the exact same batch under v5.1
        rows_v51, stats_v51 = process_pr_batch(df_batch, session, policy_version_id="v5.1")

        # Verify every row reports v5.1
        bad = [r for r in rows_v51 if r.get("policy_version") != "v5.1"]
        assert len(bad) == 0, f"{len(bad)} rows do not report v5.1 in Run 2"
        print(f"[PASS] All {len(rows_v51)} rows report policy_version = v5.1")

        # Verify at least one route changed due to the new thresholds
        routes_v50 = {(r["pr_no"], r["pr_line"]): r["route"] for r in rows_v50}
        routes_v51 = {(r["pr_no"], r["pr_line"]): r["route"] for r in rows_v51}
        changed = [k for k in routes_v50 if routes_v50[k] != routes_v51.get(k)]
        print(f"[INFO] Routes changed between v5.0 and v5.1: {len(changed)} lines")
        assert len(changed) > 0, "No routes changed after threshold amendment — expected route shifts"
        for k in changed[:5]:
            print(f"   {k[0]}/{k[1]}: {routes_v50[k]} -> {routes_v51[k]}")

        # Persist run record for Run 2 export
        run_id_v51 = str(uuid.uuid4())
        batch_id_v51 = str(uuid.uuid4())
        persist_batch_run(session, run_id_v51, batch_id_v51, df_batch, rows_v51, "v5.1")

        # Export decisions CSV for Run 2
        csv_resp2 = batch.export_run_csv(run_id_v51, session)
        assert csv_resp2.status_code == 200
        csv_bytes2 = get_body_bytes(csv_resp2)
        save_csv(csv_bytes2, f"decisions_run2_v51_{run_id_v51[:8]}.csv")

        # Verify exported CSV reflects v5.1
        csv_text2 = csv_bytes2.decode("utf-8")
        reader2 = csv.DictReader(io.StringIO(csv_text2))
        csv_rows2 = list(reader2)
        bad_csv2 = [row for row in csv_rows2 if row.get("policy_version") != "v5.1"]
        assert len(bad_csv2) == 0, f"{len(bad_csv2)} CSV rows do not report v5.1"
        print(f"[PASS] Run 2 decisions CSV exported ({len(csv_bytes2)} bytes), all rows = v5.1")

        # Export preferred suppliers CSV as of specified date
        pref_resp = batch.export_preferred_suppliers(as_of_date="2026-11-01", db=session)
        assert pref_resp.status_code == 200
        pref_bytes = get_body_bytes(pref_resp)
        save_csv(pref_bytes, f"preferred_suppliers_2026-11-01.csv")
        print(f"[PASS] Preferred suppliers CSV exported ({len(pref_bytes)} bytes)")

        print("\n=========================================")
        print("EVALUATION SCENARIO PASSED 100%!")
        print("Run 1 (v5.0) and Run 2 (v5.1) both verified.")
        print("=========================================\n")

    finally:
        session.close()


if __name__ == "__main__":
    run_scenario()
