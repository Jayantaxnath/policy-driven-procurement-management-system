"""
End-to-End Procurement Processing Pipeline.
Orchestrates Item Matching -> Clubbing -> Valuation -> Policy Evaluation -> Supplier Ranking -> PO Consolidation -> Output Generation.
"""
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.db.models import (
    Plant, ItemMaster, SupplierMaster, POHistory,
    ContractHeader, ContractLine, PolicyVersion
)
from app.engine.item_matcher import ItemMatcher
from app.engine.clubber import club_pr_lines, RequirementGroup
from app.engine.ceiling_ledger import RunCeilingLedger, ContractLedgerItem
from app.engine.valuator import value_requirement
from app.engine.decision_engine import PolicyDecisionEngine
from app.engine.po_consolidator import consolidate_purchase_orders

def load_system_state(session: Session, policy_version_id: Optional[str] = None):
    """
    Loads all master data, contracts, PO history and active policy from DB.
    """
    # 1. Plants
    plants = [p.plant_code for p in session.query(Plant).all()]
    if not plants:
        plants = ["PUN1", "CHK1"]
        
    # 2. Items
    items_raw = session.query(ItemMaster).all()
    items_list = [
        {
            "item_code": i.item_code,
            "description": i.description,
            "uom": i.uom,
            "category": i.category,
            "item_type": i.item_type,
            "standard_price": i.standard_price
        }
        for i in items_raw
    ]
    items_by_code = {i["item_code"]: i for i in items_list}
    
    # 3. Suppliers
    suppliers_raw = session.query(SupplierMaster).all()
    active_suppliers = {
        s.supplier_id: {
            "supplier_id": s.supplier_id,
            "name": s.name,
            "city": s.city,
            "categories": s.categories if isinstance(s.categories, list) else [],
            "status": s.status,
            "on_time_pct": s.on_time_pct,
            "quality_rating": s.quality_rating
        }
        for s in suppliers_raw if s.status == "Active"
    }
    all_suppliers = {
        s.supplier_id: {
            "supplier_id": s.supplier_id,
            "name": s.name,
            "status": s.status
        }
        for s in suppliers_raw
    }
    
    # 4. PO History
    po_raw = session.query(POHistory).all()
    po_history_by_item: Dict[str, List[Dict[str, Any]]] = {}
    for p in po_raw:
        sup_active = (p.supplier_id in active_suppliers)
        po_dict = {
            "po_number": p.po_number,
            "po_date": p.po_date,
            "supplier_id": p.supplier_id,
            "item_code": p.item_code,
            "quantity": p.quantity,
            "uom": p.uom,
            "unit_price": p.unit_price,
            "plant": p.plant,
            "delivered_on_time": p.delivered_on_time,
            "is_active_supplier": sup_active
        }
        po_history_by_item.setdefault(p.item_code, []).append(po_dict)
        
    # 5. Contracts & Lines
    contracts_raw = session.query(ContractHeader).all()
    contract_lines_raw = session.query(ContractLine).all()
    
    contract_lines_by_cid: Dict[str, Dict[str, float]] = {}
    contract_history_by_item: Dict[str, List[Dict[str, Any]]] = {}
    
    for cl in contract_lines_raw:
        contract_lines_by_cid.setdefault(cl.contract_id, {})[cl.item_code] = cl.rate
        
    contract_ledger_items = []
    for ch in contracts_raw:
        sup_is_active = (ch.supplier_id in active_suppliers)
        lines = contract_lines_by_cid.get(ch.contract_id, {})
        
        # Build ledger item
        item = ContractLedgerItem(
            contract_id=ch.contract_id,
            supplier_id=ch.supplier_id,
            supplier_name=ch.supplier_name,
            start_date=ch.start_date,
            end_date=ch.end_date,
            value_cap=ch.value_cap,
            initial_consumed=ch.consumed_value,
            is_supplier_active=sup_is_active,
            lines=lines
        )
        contract_ledger_items.append(item)
        
        for itm_code, rate in lines.items():
            contract_history_by_item.setdefault(itm_code, []).append({
                "contract_id": ch.contract_id,
                "supplier_id": ch.supplier_id,
                "start_date": ch.start_date,
                "end_date": ch.end_date,
                "rate": rate,
                "is_active_supplier": sup_is_active
            })
            
    ceiling_ledger = RunCeilingLedger(contract_ledger_items)
    
    # 6. Policy Definition
    if policy_version_id:
        pv = session.get(PolicyVersion, policy_version_id)
    else:
        pv = session.query(PolicyVersion).filter_by(status="ACTIVE").order_by(PolicyVersion.effective_date.desc()).first()
        
    policy_def = pv.rules_definition if pv else {}
    
    return {
        "plants": plants,
        "items_list": items_list,
        "items_by_code": items_by_code,
        "active_suppliers": active_suppliers,
        "all_suppliers": all_suppliers,
        "po_history_by_item": po_history_by_item,
        "contract_history_by_item": contract_history_by_item,
        "ceiling_ledger": ceiling_ledger,
        "policy_def": policy_def
    }

def process_pr_batch(
    df_raw: pd.DataFrame,
    session: Session,
    policy_version_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Processes a raw PR batch DataFrame end-to-end.
    Returns (decision_rows_list, summary_stats).
    """
    state = load_system_state(session, policy_version_id)
    matcher = ItemMatcher(state["items_list"])
    decision_engine = PolicyDecisionEngine(state["policy_def"])
    ceiling_ledger = state["ceiling_ledger"]
    
    # Convert DataFrame to records
    raw_lines = []
    for _, r in df_raw.iterrows():
        # Parse timestamp
        created_val = r["created_at"]
        if isinstance(created_val, str):
            created_at = datetime.strptime(created_val.strip(), "%Y-%m-%d %H:%M")
        elif isinstance(created_val, datetime):
            created_at = created_val
        else:
            created_at = datetime.now()
            
        # Parse need by date
        need_val = r["need_by_date"]
        if isinstance(need_val, str):
            need_by = datetime.strptime(need_val.strip(), "%Y-%m-%d").date()
        elif isinstance(need_val, date):
            need_by = need_val
        else:
            need_by = created_at.date()

        # Resolve item code
        raw_code = str(r["item_code"]).strip() if pd.notna(r.get("item_code")) and str(r.get("item_code")).strip() else None
        desc = str(r.get("description", "")).strip() if pd.notna(r.get("description")) else ""
        
        resolved_code, conf, item_info = matcher.resolve(raw_code, desc)
        
        raw_lines.append({
            "pr_no": str(r["pr_no"]).strip(),
            "pr_line": int(r["pr_line"]),
            "created_at": created_at,
            "requester": str(r.get("requester", "")),
            "department": str(r.get("department", "")),
            "plant": str(r.get("plant", "")).strip(),
            "item_code": raw_code,
            "resolved_item_code": resolved_code,
            "description": desc,
            "quantity": float(r.get("quantity", 0) or 0),
            "uom": str(r.get("uom", "NOS")).strip(),
            "estimated_unit_price": float(r["estimated_unit_price"]) if pd.notna(r.get("estimated_unit_price")) and str(r.get("estimated_unit_price")).strip() else None,
            "need_by_date": need_by,
            "urgency": str(r.get("urgency", "Normal")).strip()
        })
        
    # Clubbing
    groups, unproc_lines = club_pr_lines(
        raw_lines, 
        valid_plants=state["plants"],
        max_creation_days=state["policy_def"].get("parameters", {}).get("clubbing_window_days", 14),
        max_need_by_days=state["policy_def"].get("parameters", {}).get("need_by_window_days", 7)
    )
    
    # Process requirements in order of requirement_date (first line created_at)
    groups.sort(key=lambda g: g.first_line_created_at)
    
    req_decisions: Dict[str, Dict[str, Any]] = {}
    
    for group in groups:
        # Value requirement
        unit_price, group_val, price_source, win_cid, win_rate = value_requirement(
            group,
            ceiling_ledger,
            state["po_history_by_item"],
            state["items_by_code"],
            lookback_days=state["policy_def"].get("parameters", {}).get("po_history_lookback_days", 365)
        )
        
        # Policy evaluation
        outcome = decision_engine.evaluate_requirement(
            group,
            unit_price=unit_price,
            group_value_inr=group_val,
            price_source=price_source,
            winning_contract_id=win_cid,
            contract_rate=win_rate,
            ceiling_ledger=ceiling_ledger,
            active_suppliers=state["active_suppliers"],
            po_history_by_item=state["po_history_by_item"],
            contract_history_by_item=state["contract_history_by_item"],
            item_master_by_code=state["items_by_code"]
        )
        
        req_decisions[group.group_id] = {
            "group": group,
            "outcome": outcome,
            "first_line_created_at": group.first_line_created_at,
            "plant": group.plant,
            "supplier_id": outcome.get("supplier_id"),
            "route": outcome.get("route"),
            "decision": outcome.get("decision")
        }
        
    # PO Consolidation (Clauses 7.1 and 7.2)
    po_eligible_reqs = [
        d for d in req_decisions.values() 
        if d.get("decision") == "PO"
    ]
    consolidate_purchase_orders(
        po_eligible_reqs, 
        max_window_hours=state["policy_def"].get("parameters", {}).get("po_consolidation_window_hours", 24)
    )
    
    # Generate final per-PR-line output table
    final_output_rows = []
    
    # Map from (pr_no, pr_line) to result
    for gid, d in req_decisions.items():
        grp = d["group"]
        out = d["outcome"]
        po_id = d.get("po_id")
        
        for line in grp.lines:
            row = {
                "pr_no": line["pr_no"],
                "pr_line": line["pr_line"],
                "resolved_item_code": grp.resolved_item_code,
                "group_id": grp.group_id,
                "po_id": po_id if out["decision"] == "PO" else None,
                "decision": out["decision"],
                "route": out["route"],
                "supplier_id": out["supplier_id"],
                "unit_price": out["unit_price"],
                "group_value_inr": out["group_value_inr"],
                "suggested_supplier_ids": out["suggested_supplier_ids"],
                "policy_version": out["policy_version"],
                "reason": out["reason"]
            }
            final_output_rows.append(row)
            
    # Add NOT_PROCESSED rows
    for unproc in unproc_lines:
        row = {
            "pr_no": unproc["pr_no"],
            "pr_line": unproc["pr_line"],
            "resolved_item_code": unproc["resolved_item_code"],
            "group_id": f"UNPROC-{unproc['pr_no']}-{unproc['pr_line']}",
            "po_id": None,
            "decision": "NOT_PROCESSED",
            "route": "NOT_PROCESSED",
            "supplier_id": None,
            "unit_price": None,
            "group_value_inr": 0.0,
            "suggested_supplier_ids": None,
            "policy_version": decision_engine.version,
            "reason": unproc["reason"]
        }
        final_output_rows.append(row)
        
    # Sort output to match input order or pr_no / pr_line
    # We sort by pr_no, pr_line for stable deterministic ordering
    final_output_rows.sort(key=lambda x: (x["pr_no"], x["pr_line"]))
    
    stats = {
        "total_lines": len(final_output_rows),
        "total_requirements": len(req_decisions),
        "total_pos": len(set(r["po_id"] for r in final_output_rows if r["po_id"])),
        "total_sourcing": len([r for r in final_output_rows if r["decision"] == "SOURCING_REQUEST"]),
        "total_not_processed": len(unproc_lines)
    }
    
    return final_output_rows, stats

