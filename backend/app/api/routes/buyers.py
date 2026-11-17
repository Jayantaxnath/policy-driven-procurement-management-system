"""
Buyer Workspace API routes.
Implements:
- GET /api/requirements: Lists requirements with filters (run_id, plant, route, decision, search) and pagination.
- GET /api/requirements/{id}: Detailed view of requirement, lines, valuation trace, suggested suppliers, and buyer actions.
- POST /api/requirements/{id}/approve: Approves the policy decision and records audit log.
- POST /api/requirements/{id}/override: Buyer overrides route or supplier with mandatory comment justification.
- GET /api/buyers/actions: Recent buyer actions audit trail.
"""
import uuid
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.db.database import get_db
from app.db.models import (
    Requirement, RequirementLine, PRLine, BuyerAction,
    AuditLog, SupplierMaster, ItemMaster, BatchExecutionRun
)

router = APIRouter(tags=["Buyer Workspace"])

class ApproveRequest(BaseModel):
    buyer_id: str = Field(..., description="ID or name of the buyer approving the requirement")
    notes: Optional[str] = Field(None, description="Optional approval notes")

class OverrideRequest(BaseModel):
    buyer_id: str = Field(..., description="ID or name of the buyer performing the override")
    override_reason: str = Field(..., min_length=5, description="Mandatory business reason for overriding the policy decision")
    new_route: Optional[str] = Field(None, description="New route e.g. RFQ, SPOT_PO, CONTRACT_PO, RFP")
    new_supplier_id: Optional[str] = Field(None, description="New supplier ID if overriding supplier")
    new_decision: Optional[str] = Field(None, description="PO or SOURCING_REQUEST")

@router.get("/requirements")
def list_requirements(
    run_id: Optional[str] = Query(None, description="Filter by execution run ID"),
    plant: Optional[str] = Query(None, description="Filter by plant code"),
    decision: Optional[str] = Query(None, description="Filter by decision (PO, SOURCING_REQUEST, NOT_PROCESSED)"),
    route: Optional[str] = Query(None, description="Filter by route"),
    search: Optional[str] = Query(None, description="Search by item code, description, requirement ID, PR number or reason"),
    sort_by: Optional[str] = Query("date", description="Sort by 'date' (most recent first) or 'value'"),
    sort_order: Optional[str] = Query("desc", description="Sort order: 'desc' or 'asc'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all requirements with applied filters, valuation data, and current buyer approval status.
    Supports multi-column deep search and sorting by execution timestamp (most recent first by default).
    """
    q = db.query(Requirement)
    
    if run_id and isinstance(run_id, str):
        q = q.filter(Requirement.run_id == run_id)
    if plant and isinstance(plant, str):
        q = q.filter(Requirement.plant == plant)
    if decision and isinstance(decision, str):
        q = q.filter(Requirement.decision == decision)
    if route and isinstance(route, str):
        q = q.filter(Requirement.route == route)
    if search and isinstance(search, str):
        s = f"%{search.strip()}%"
        q = q.outerjoin(ItemMaster, Requirement.resolved_item_code == ItemMaster.item_code)\
             .outerjoin(RequirementLine, Requirement.requirement_id == RequirementLine.requirement_id)\
             .outerjoin(PRLine, RequirementLine.pr_line_id == PRLine.id)\
             .filter(
                 (Requirement.requirement_id.ilike(s)) |
                 (Requirement.resolved_item_code.ilike(s)) |
                 (Requirement.reason.ilike(s)) |
                 (Requirement.route.ilike(s)) |
                 (Requirement.supplier_id.ilike(s)) |
                 (ItemMaster.description.ilike(s)) |
                 (PRLine.pr_no.ilike(s)) |
                 (PRLine.description.ilike(s))
             ).distinct()

    # Join BatchExecutionRun for ordering by executed_at (most recent run first)
    q = q.outerjoin(BatchExecutionRun, Requirement.run_id == BatchExecutionRun.run_id)

    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    total_count = q.distinct().count()

    # Determine ordering
    is_asc = (isinstance(sort_order, str) and sort_order.lower() == "asc")
    if sort_by == "value":
        order_expr = asc(Requirement.group_value_inr) if is_asc else desc(Requirement.group_value_inr)
        items = q.order_by(order_expr, desc(BatchExecutionRun.executed_at), Requirement.requirement_id).offset(offset_val).limit(limit_val).all()
    else:
        # Default: Sort by date (most recent executed_at / requirement_date first)
        date_expr = asc(BatchExecutionRun.executed_at) if is_asc else desc(BatchExecutionRun.executed_at)
        req_date_expr = asc(Requirement.requirement_date) if is_asc else desc(Requirement.requirement_date)
        items = q.order_by(date_expr, req_date_expr, Requirement.requirement_id).offset(offset_val).limit(limit_val).all()
    
    # Enrich with latest buyer action status, execution timestamp and item description
    results = []
    for req in items:
        # Check latest buyer action
        latest_action = db.query(BuyerAction).filter(
            BuyerAction.requirement_id == req.requirement_id
        ).order_by(desc(BuyerAction.performed_at)).first()
        
        # Item info
        item = db.query(ItemMaster).filter(ItemMaster.item_code == req.resolved_item_code).first() if req.resolved_item_code else None
        
        # Supplier info
        supplier = db.query(SupplierMaster).filter(SupplierMaster.supplier_id == req.supplier_id).first() if req.supplier_id else None

        # Execution run info
        run_record = db.query(BatchExecutionRun).filter(BatchExecutionRun.run_id == req.run_id).first()
        
        results.append({
            "requirement_id": req.requirement_id,
            "run_id": req.run_id,
            "resolved_item_code": req.resolved_item_code,
            "item_description": item.description if item else ("Uncataloged Item" if req.is_new_item else None),
            "is_new_item": req.is_new_item,
            "plant": req.plant,
            "requirement_date": req.requirement_date.isoformat() if req.requirement_date else None,
            "submitted_at": run_record.executed_at.isoformat() if run_record and run_record.executed_at else None,
            "total_quantity": req.total_quantity,
            "uom": req.uom,
            "urgency": req.urgency,
            "unit_price": req.unit_price,
            "group_value_inr": req.group_value_inr,
            "decision": req.decision,
            "route": req.route,
            "supplier_id": req.supplier_id,
            "supplier_name": supplier.name if supplier else None,
            "po_id": req.po_id,
            "suggested_supplier_ids": req.suggested_supplier_ids,
            "policy_version_id": req.policy_version_id,
            "policy_clause": req.policy_clause,
            "reason": req.reason,
            "buyer_status": latest_action.action if latest_action else "PENDING_REVIEW",
            "last_action_by": latest_action.buyer_id if latest_action else None,
            "last_action_at": latest_action.performed_at.isoformat() if latest_action else None,
            "override_reason": latest_action.override_reason if latest_action else None
        })
        
    return {
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "requirements": results
    }

@router.get("/requirements/{requirement_id}")
def get_requirement_detail(
    requirement_id: str,
    db: Session = Depends(get_db)
):
    """
    Detailed requirement view including clubbed PR lines, pricing waterfall source,
    suggested suppliers with metadata, and complete audit history.
    """
    req = db.query(Requirement).filter(Requirement.requirement_id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Requirement '{requirement_id}' not found.")
        
    # Get clubbed PR lines
    lines = (
        db.query(PRLine)
        .join(RequirementLine, PRLine.id == RequirementLine.pr_line_id)
        .filter(RequirementLine.requirement_id == requirement_id)
        .all()
    )
    
    pr_lines_data = [
        {
            "id": line.id,
            "pr_no": line.pr_no,
            "pr_line": line.pr_line,
            "created_at": line.created_at.isoformat() if line.created_at else None,
            "requester": line.requester,
            "department": line.department,
            "plant": line.plant,
            "item_code": line.item_code,
            "description": line.description,
            "quantity": line.quantity,
            "uom": line.uom,
            "need_by_date": line.need_by_date.isoformat() if line.need_by_date else None,
            "urgency": line.urgency
        }
        for line in lines
    ]
    
    # Suggested suppliers details
    suggested_suppliers = []
    if req.suggested_supplier_ids:
        try:
            sup_ids = [s.strip() for s in req.suggested_supplier_ids.split(",") if s.strip()]
            for sid in sup_ids:
                sm = db.query(SupplierMaster).filter(SupplierMaster.supplier_id == sid).first()
                if sm:
                    suggested_suppliers.append({
                        "supplier_id": sm.supplier_id,
                        "name": sm.name,
                        "city": sm.city,
                        "status": sm.status,
                        "on_time_pct": sm.on_time_pct,
                        "quality_rating": sm.quality_rating,
                        "categories": sm.categories
                    })
                else:
                    suggested_suppliers.append({"supplier_id": sid, "name": sid})
        except Exception:
            pass

    # Buyer actions & audit log
    actions = (
        db.query(BuyerAction)
        .filter(BuyerAction.requirement_id == requirement_id)
        .order_by(desc(BuyerAction.performed_at))
        .all()
    )
    action_history = [
        {
            "id": a.id,
            "action": a.action,
            "buyer_id": a.buyer_id,
            "performed_at": a.performed_at.isoformat() if a.performed_at else None,
            "override_reason": a.override_reason,
            "previous_route": a.previous_route,
            "new_route": a.new_route,
            "previous_supplier_id": a.previous_supplier_id,
            "new_supplier_id": a.new_supplier_id
        }
        for a in actions
    ]

    item = db.query(ItemMaster).filter(ItemMaster.item_code == req.resolved_item_code).first() if req.resolved_item_code else None
    supplier = db.query(SupplierMaster).filter(SupplierMaster.supplier_id == req.supplier_id).first() if req.supplier_id else None

    return {
        "requirement_id": req.requirement_id,
        "run_id": req.run_id,
        "resolved_item_code": req.resolved_item_code,
        "item_description": item.description if item else ("Uncataloged Item" if req.is_new_item else None),
        "is_new_item": req.is_new_item,
        "plant": req.plant,
        "requirement_date": req.requirement_date.isoformat() if req.requirement_date else None,
        "total_quantity": req.total_quantity,
        "uom": req.uom,
        "urgency": req.urgency,
        "unit_price": req.unit_price,
        "group_value_inr": req.group_value_inr,
        "price_source": req.price_source,
        "winning_contract_id": req.winning_contract_id,
        "decision": req.decision,
        "route": req.route,
        "supplier_id": req.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "po_id": req.po_id,
        "suggested_suppliers": suggested_suppliers,
        "policy_version_id": req.policy_version_id,
        "policy_clause": req.policy_clause,
        "reason": req.reason,
        "clubbed_pr_lines": pr_lines_data,
        "action_history": action_history
    }

@router.post("/requirements/{requirement_id}/approve")
def approve_requirement(
    requirement_id: str,
    payload: ApproveRequest,
    db: Session = Depends(get_db)
):
    """
    Approve requirement policy decision. Logs buyer action and audit entry.
    """
    req = db.query(Requirement).filter(Requirement.requirement_id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Requirement '{requirement_id}' not found.")
        
    action_id = str(uuid.uuid4())
    buyer_action = BuyerAction(
        id=action_id,
        run_id=req.run_id,
        requirement_id=requirement_id,
        action="APPROVED",
        buyer_id=payload.buyer_id,
        override_reason=payload.notes,
        previous_route=req.route,
        new_route=req.route,
        previous_supplier_id=req.supplier_id,
        new_supplier_id=req.supplier_id
    )
    db.add(buyer_action)

    audit = AuditLog(
        event_type="REQUIREMENT_APPROVED",
        entity_type="Requirement",
        entity_id=requirement_id,
        actor=payload.buyer_id,
        payload={
            "action_id": action_id,
            "route": req.route,
            "decision": req.decision,
            "supplier_id": req.supplier_id,
            "notes": payload.notes
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Requirement {requirement_id} approved successfully by {payload.buyer_id}.",
        "requirement_id": requirement_id,
        "action": "APPROVED"
    }

@router.post("/requirements/{requirement_id}/override")
def override_requirement(
    requirement_id: str,
    payload: OverrideRequest,
    db: Session = Depends(get_db)
):
    """
    Buyer manual override of route or supplier.
    Requires mandatory business justification comment.
    """
    if not payload.override_reason or len(payload.override_reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="A mandatory, meaningful override reason (min 5 chars) is required.")

    req = db.query(Requirement).filter(Requirement.requirement_id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Requirement '{requirement_id}' not found.")

    prev_route = req.route
    prev_supplier_id = req.supplier_id
    prev_decision = req.decision

    # Apply changes
    if payload.new_route:
        req.route = payload.new_route
    if payload.new_supplier_id:
        req.supplier_id = payload.new_supplier_id
    if payload.new_decision:
        req.decision = payload.new_decision
    elif payload.new_route in ["CONTRACT_PO", "SPOT_PO", "EMERGENCY_PO"]:
        req.decision = "PO"
    elif payload.new_route in ["RFQ", "RFP", "CAPEX_SOURCING", "NEW_ITEM_SOURCING"]:
        req.decision = "SOURCING_REQUEST"

    req.reason = f"Buyer Override by {payload.buyer_id}: {payload.override_reason} (Original: {prev_route})"

    action_id = str(uuid.uuid4())
    buyer_action = BuyerAction(
        id=action_id,
        run_id=req.run_id,
        requirement_id=requirement_id,
        action="OVERRIDDEN",
        buyer_id=payload.buyer_id,
        override_reason=payload.override_reason,
        previous_route=prev_route,
        new_route=req.route,
        previous_supplier_id=prev_supplier_id,
        new_supplier_id=req.supplier_id
    )
    db.add(buyer_action)

    audit = AuditLog(
        event_type="REQUIREMENT_OVERRIDDEN",
        entity_type="Requirement",
        entity_id=requirement_id,
        actor=payload.buyer_id,
        payload={
            "action_id": action_id,
            "previous_route": prev_route,
            "new_route": req.route,
            "previous_supplier_id": prev_supplier_id,
            "new_supplier_id": req.supplier_id,
            "previous_decision": prev_decision,
            "new_decision": req.decision,
            "override_reason": payload.override_reason
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Requirement {requirement_id} successfully overridden by {payload.buyer_id}.",
        "requirement_id": requirement_id,
        "action": "OVERRIDDEN",
        "previous_route": prev_route,
        "new_route": req.route,
        "new_supplier_id": req.supplier_id,
        "override_reason": payload.override_reason
    }

@router.get("/buyers/actions")
def list_buyer_actions(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Audit log of all buyer actions and overrides.
    """
    limit_val = limit if isinstance(limit, int) else 50
    actions = db.query(BuyerAction).order_by(desc(BuyerAction.performed_at)).limit(limit_val).all()
    return [
        {
            "id": a.id,
            "run_id": a.run_id,
            "requirement_id": a.requirement_id,
            "action": a.action,
            "buyer_id": a.buyer_id,
            "performed_at": a.performed_at.isoformat() if a.performed_at else None,
            "override_reason": a.override_reason,
            "previous_route": a.previous_route,
            "new_route": a.new_route,
            "previous_supplier_id": a.previous_supplier_id,
            "new_supplier_id": a.new_supplier_id
        }
        for a in actions
    ]
