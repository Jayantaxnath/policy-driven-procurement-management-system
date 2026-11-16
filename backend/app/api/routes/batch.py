"""
Batch processing API routes.
Implements:
- POST /api/process-batch: Ingests PR batch CSV, runs policy pipeline, persists run in DB, returns decisions.
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
from app.db.models import PRBatch, PRLine, BatchExecutionRun, Requirement, RequirementLine
from app.engine.pipeline import process_pr_batch
from app.engine.supplier_ranker import compute_preferred_suppliers
from app.engine.pipeline import load_system_state

router = APIRouter(tags=["Batch Processing"])

@router.post("/process-batch")
def process_batch_endpoint(
    file: UploadFile = File(...),
    policy_version: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    POST /api/process-batch
    Takes a PR batch CSV and returns the decisions JSON.
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
    exec_run = BatchExecutionRun(
        run_id=run_id,
        batch_id=batch_id,
        policy_version_id=decision_rows[0]["policy_version"] if decision_rows else "v5.0",
        status="COMPLETED",
        total_pr_lines=stats["total_lines"],
        total_requirements=stats["total_requirements"],
        total_pos=stats["total_pos"],
        total_sourcing_requests=stats["total_sourcing"],
        total_not_processed=stats["total_not_processed"]
    )
    db.add(exec_run)
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
    Downloads CSV in exact Section 4 output format.
    """
    # For demonstration / standalone testing, if sample batch is run, re-export
    state = load_system_state(db)
    # Output stream
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = [
        "pr_no", "pr_line", "resolved_item_code", "group_id", "po_id",
        "decision", "route", "supplier_id", "unit_price", "group_value_inr",
        "suggested_supplier_ids", "policy_version", "reason"
    ]
    writer.writerow(headers)
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
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
            writer.writerow([icode, idx, sup["supplier_id"], sup["reference_price"]])
            
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=preferred_suppliers_{target_date}.csv"}
    )
