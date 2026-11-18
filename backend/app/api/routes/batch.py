"""
Batch processing API routes.
Implements:
- POST /api/process-batch: Ingests PR batch CSV, runs policy pipeline, persists batch, lines, execution run, and requirements in DB, returns decisions.
- GET /api/runs/{run_id}/export: Downloads decisions as CSV in the exact Section 4 format.
- GET /api/preferred-suppliers: Downloads or views preferred supplier rankings as CSV.
"""
import io
import csv
import uuid
import pandas as pd
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    PRBatch, PRLine, BatchExecutionRun, Requirement, RequirementLine,
    POHeader, POLine, ItemMaster
)
from app.engine.pipeline import process_pr_batch, load_system_state
from app.engine.supplier_ranker import compute_preferred_suppliers

router = APIRouter(tags=["Batch Processing"])

@router.post("/process-batch")
def process_batch_endpoint(
    file: UploadFile = File(...),
    policy_version: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    POST /api/process-batch
    Takes a PR batch CSV, evaluates deterministic policy decisions, persists to DB, and returns decisions JSON.
    """
    contents = file.file.read()
    try:
        df_raw = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
        
    # Create batch record
    batch_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    batch_record = PRBatch(
        batch_id=batch_id,
        batch_name=file.filename or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        source_type="CSV_UPLOAD"
    )
    db.add(batch_record)
    db.commit()
    
    # Run deterministic policy pipeline
    decision_rows, stats = process_pr_batch(df_raw, db, policy_version_id=policy_version)
    
    # Save execution run record
    pol_ver = decision_rows[0]["policy_version"] if decision_rows else (policy_version or "v5.0")
    exec_run = BatchExecutionRun(
        run_id=run_id,
        batch_id=batch_id,
        policy_version_id=pol_ver,
        status="COMPLETED",
        total_pr_lines=stats["total_lines"],
        total_requirements=stats["total_requirements"],
        total_pos=stats["total_pos"],
        total_sourcing_requests=stats["total_sourcing"],
        total_not_processed=stats["total_not_processed"]
    )
    db.add(exec_run)

    # Persist PRLines into DB
    pr_line_map = {}  # (pr_no, pr_line) -> PRLine.id
    for _, r in df_raw.iterrows():
        try:
            p_no = str(r["pr_no"]).strip()
            p_line = int(r["pr_line"])
            
            created_val = r.get("created_at")
            if isinstance(created_val, str):
                c_date = datetime.strptime(created_val.strip(), "%Y-%m-%d %H:%M")
            else:
                c_date = datetime.now()
                
            need_val = r.get("need_by_date")
            if isinstance(need_val, str):
                n_date = datetime.strptime(need_val.strip(), "%Y-%m-%d").date()
            else:
                n_date = c_date.date()

            pr_id = str(uuid.uuid4())
            pr_obj = PRLine(
                id=pr_id,
                batch_id=batch_id,
                pr_no=p_no,
                pr_line=p_line,
                created_at=c_date,
                requester=str(r.get("requester", "")),
                department=str(r.get("department", "")),
                plant=str(r.get("plant", "")).strip(),
                item_code=str(r.get("item_code", "")).strip() if pd.notna(r.get("item_code")) else None,
                description=str(r.get("description", "")),
                quantity=float(r.get("quantity", 0) or 0),
                uom=str(r.get("uom", "NOS")).strip(),
                estimated_unit_price=float(r.get("estimated_unit_price")) if pd.notna(r.get("estimated_unit_price")) and float(r.get("estimated_unit_price", 0) or 0) > 0 else None,
                need_by_date=n_date,
                urgency=str(r.get("urgency", "Normal")),
                ingestion_status="PROCESSED"
            )
            db.add(pr_obj)
            pr_line_map[(p_no, p_line)] = pr_id
        except Exception:
            continue

    # Group decision rows by group_id / requirement
    req_groups = {}
    for d in decision_rows:
        raw_gid = d["group_id"]
        scoped_gid = f"{run_id[:8]}-{raw_gid}"
        d["scoped_group_id"] = scoped_gid
        if scoped_gid not in req_groups:
            req_groups[scoped_gid] = {
                "raw_gid": raw_gid,
                "decision": d,
                "lines": []
            }
        req_groups[scoped_gid]["lines"].append(d)

    # Persist Requirements and RequirementLines
    for scoped_gid, gdata in req_groups.items():
        first_d = gdata["decision"]
        is_new = (first_d.get("resolved_item_code") == "NEW")
        
        # Calculate requirement date from first line if available (Bug Fix: was always date.today())
        req_date = date.today()
        first_line = gdata["lines"][0] if gdata["lines"] else None
        if first_line:
            # Use need_by_date if available, else fall back to created_at date
            if first_line.get("need_by_date"):
                try:
                    req_date = datetime.strptime(str(first_line["need_by_date"]), "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass
            elif first_line.get("created_at"):
                try:
                    if isinstance(first_line["created_at"], str):
                        req_date = datetime.strptime(first_line["created_at"].strip(), "%Y-%m-%d %H:%M").date()
                    elif isinstance(first_line["created_at"], datetime):
                        req_date = first_line["created_at"].date()
                except (ValueError, TypeError):
                    pass

        req_obj = Requirement(
            requirement_id=scoped_gid,
            run_id=run_id,
            resolved_item_code=first_d.get("resolved_item_code"),
            is_new_item=is_new,
            plant=first_d.get("plant"),
            requirement_date=req_date,
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
            policy_version_id=first_d.get("policy_version", pol_ver),
            reason=first_d.get("reason")
        )
        db.add(req_obj)

        for line in gdata["lines"]:
            key = (line["pr_no"], line["pr_line"])
            if key in pr_line_map:
                r_line = RequirementLine(
                    requirement_id=scoped_gid,
                    pr_line_id=pr_line_map[key]
                )
                db.add(r_line)

    db.commit()
    
    return {
        "run_id": run_id,
        "batch_id": batch_id,
        "policy_version": exec_run.policy_version_id,
        "stats": stats,
        "decisions": decision_rows
    }

@router.get("/runs/{run_id}/export")
def export_run_csv(
    run_id: str,
    db: Session = Depends(get_db)
):
    """
    GET /api/runs/{run_id}/export
    Downloads CSV in exact Section 4 output format with all decisions from the run.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = [
        "pr_no", "pr_line", "resolved_item_code", "group_id", "po_id",
        "decision", "route", "supplier_id", "unit_price", "group_value_inr",
        "suggested_supplier_ids", "policy_version", "reason"
    ]
    writer.writerow(headers)

    # Query requirements and their PR lines
    reqs = db.query(Requirement).filter(Requirement.run_id == run_id).all()
    for req in reqs:
        # Get pr lines
        lines = (
            db.query(PRLine)
            .join(RequirementLine, PRLine.id == RequirementLine.pr_line_id)
            .filter(RequirementLine.requirement_id == req.requirement_id)
            .all()
        )
        if lines:
            for l in lines:
                writer.writerow([
                    l.pr_no,
                    l.pr_line,
                    req.resolved_item_code or "",
                    req.requirement_id,
                    req.po_id or "",
                    req.decision or "",
                    req.route or "",
                    req.supplier_id or "",
                    f"{req.unit_price:.2f}" if req.unit_price is not None else "",
                    f"{req.group_value_inr:.2f}" if req.group_value_inr is not None else "",
                    req.suggested_supplier_ids or "",
                    req.policy_version_id or "",
                    req.reason or ""
                ])
        else:
            # Fallback row
            writer.writerow([
                "", "",
                req.resolved_item_code or "",
                req.requirement_id,
                req.po_id or "",
                req.decision or "",
                req.route or "",
                req.supplier_id or "",
                f"{req.unit_price:.2f}" if req.unit_price is not None else "",
                f"{req.group_value_inr:.2f}" if req.group_value_inr is not None else "",
                req.suggested_supplier_ids or "",
                req.policy_version_id or "",
                req.reason or ""
            ])

    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=decisions_{run_id}.csv"}
    )

@router.get("/preferred-suppliers")
def export_preferred_suppliers(
    as_of_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Export preferred supplier list as CSV (item_code, rank, supplier_id, reference_price, top 3).
    """
    target_date = datetime.strptime(as_of_date, "%Y-%m-%d").date() if as_of_date else date(2026, 11, 1)
    state = load_system_state(db)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["item_code", "rank", "supplier_id", "reference_price"])
    
    for item in state["items_list"]:
        icode = item["item_code"]
        ranked = compute_preferred_suppliers(
            icode, target_date, state["active_suppliers"],
            state["po_history_by_item"], state["contract_history_by_item"]
        )
        for idx, sup in enumerate(ranked[:3], 1):
            writer.writerow([icode, idx, sup["supplier_id"], f"{sup['reference_price']:.2f}"])
            
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=preferred_suppliers_{target_date}.csv"}
    )
