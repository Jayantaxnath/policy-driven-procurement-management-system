"""
Preferred Supplier Ranking and Sourcing Suggestions Module.
Implements Clauses 6.1, 6.2, 6.3, 6.4, and 5.7.
"""
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

def compute_preferred_suppliers(
    item_code: str,
    as_of_date: date,
    active_suppliers: Dict[str, Dict[str, Any]],
    po_history_by_item: Dict[str, List[Dict[str, Any]]],
    contract_history_by_item: Dict[str, List[Dict[str, Any]]],
    lookback_days: int = 548,
    weights: Optional[Dict[str, float]] = None
) -> List[Dict[str, Any]]:
    """
    Returns ranked list of preferred suppliers for the item as of as_of_date.
    """
    if weights is None:
        weights = {
            "po_frequency": 0.25,
            "recency": 0.25,
            "contract_held": 0.20,
            "on_time_delivery": 0.15,
            "quality_rating": 0.15
        }
        
    start_548 = as_of_date - timedelta(days=lookback_days)
    
    # 1. Active supplier POs for this item in lookback_days
    pos = po_history_by_item.get(item_code, [])
    sup_pos: Dict[str, List[Dict[str, Any]]] = {}
    for p in pos:
        sid = p["supplier_id"]
        if sid in active_suppliers and start_548 <= p["po_date"] < as_of_date:
            sup_pos.setdefault(sid, []).append(p)
            
    # 2. Active supplier contracts covering the item starting on or before as_of_date
    contracts = contract_history_by_item.get(item_code, [])
    sup_contracts: Dict[str, List[Dict[str, Any]]] = {}
    for c in contracts:
        sid = c["supplier_id"]
        # Bug Fix: also check end_date to exclude expired contracts
        if sid in active_suppliers and c["start_date"] <= as_of_date and c["end_date"] >= as_of_date:
            sup_contracts.setdefault(sid, []).append(c)
            
    candidate_ids = set(sup_pos.keys()) | set(sup_contracts.keys())
    if not candidate_ids:
        return []
        
    scored = []
    for sid in candidate_ids:
        sup = active_suppliers[sid]
        po_list = sup_pos.get(sid, [])
        po_count = len(po_list)
        
        # Recency score
        recency = 0.0
        latest_po_price = None
        if po_list:
            sorted_pos = sorted(po_list, key=lambda x: (x["po_date"], int(x["po_number"])), reverse=True)
            days_ago = (as_of_date - sorted_pos[0]["po_date"]).days
            if days_ago <= 90:
                recency = 1.0
            elif days_ago <= 365:
                recency = 0.5
            else:
                recency = 0.0
            latest_po_price = float(sorted_pos[0]["unit_price"])
            
        has_contract = 1.0 if sid in sup_contracts else 0.0
        
        # Clause 6.3: Reference price
        if latest_po_price is not None:
            ref_price = latest_po_price
        elif sid in sup_contracts:
            sorted_c = sorted(sup_contracts[sid], key=lambda x: x["start_date"], reverse=True)
            ref_price = float(sorted_c[0]["rate"])
        else:
            ref_price = 0.0
            
        ot_norm = float(sup["on_time_pct"]) / 100.0
        q_norm = float(sup["quality_rating"]) / 5.0
        
        score = (
            weights.get("po_frequency", 0.25) * min(po_count / 5.0, 1.0) +
            weights.get("recency", 0.25) * recency +
            weights.get("contract_held", 0.20) * has_contract +
            weights.get("on_time_delivery", 0.15) * ot_norm +
            weights.get("quality_rating", 0.15) * q_norm
        )
        
        scored.append({
            "supplier_id": sid,
            "name": sup["name"],
            "po_count": po_count,
            "recency": recency,
            "has_contract": bool(has_contract),
            "on_time_pct": sup["on_time_pct"],
            "quality_rating": sup["quality_rating"],
            "score": score,
            "reference_price": ref_price
        })
        
    # Sort: score DESC, on_time_pct DESC, quality_rating DESC, supplier_id ASC
    scored.sort(
        key=lambda x: (x["score"], x["on_time_pct"], x["quality_rating"], -int(x["supplier_id"][1:]) if x["supplier_id"][1:].isdigit() else x["supplier_id"]),
        reverse=True
    )
    return scored


def suggest_suppliers_for_sourcing(
    item_code: str,
    item_category: str,
    as_of_date: date,
    count_needed: int,
    active_suppliers: Dict[str, Dict[str, Any]],
    po_history_by_item: Dict[str, List[Dict[str, Any]]],
    contract_history_by_item: Dict[str, List[Dict[str, Any]]],
    weights: Optional[Dict[str, float]] = None
) -> List[str]:
    """
    Implements Clause 6.4:
    Take preferred list in order. If fewer than needed, add other Active suppliers
    listing the item's category in supplier master, best delivery and quality record first.
    New items get no suggestions.
    """
    if item_code == "NEW":
        return []
        
    preferred = compute_preferred_suppliers(
        item_code, as_of_date, active_suppliers,
        po_history_by_item, contract_history_by_item,
        weights=weights
    )
    
    suggested = [p["supplier_id"] for p in preferred]
    
    if len(suggested) < count_needed:
        # Backfill from active suppliers in same category
        category_sups = []
        for sid, s in active_suppliers.items():
            if sid not in suggested:
                cats = s.get("categories", [])
                if item_category in cats:
                    category_sups.append(s)
                    
        # Sort category suppliers: best delivery and quality record first
        category_sups.sort(
            key=lambda x: (float(x["on_time_pct"]), float(x["quality_rating"]), -int(x["supplier_id"][1:]) if x["supplier_id"][1:].isdigit() else x["supplier_id"]),
            reverse=True
        )
        
        for cs in category_sups:
            suggested.append(cs["supplier_id"])
            if len(suggested) >= count_needed:
                break
                
    return suggested[:count_needed]

