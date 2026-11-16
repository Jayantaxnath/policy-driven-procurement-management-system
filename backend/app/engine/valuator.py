"""
Requirement Valuation Module.
Implements Clause 3.1 and 1.2.
"""
from datetime import date, timedelta
from typing import Dict, Any, Optional, Tuple, List
from app.engine.ceiling_ledger import RunCeilingLedger

def value_requirement(
    group, # RequirementGroup
    ceiling_ledger: RunCeilingLedger,
    po_history_by_item: Dict[str, List[Dict[str, Any]]],
    item_master_by_code: Dict[str, Dict[str, Any]],
    lookback_days: int = 365
) -> Tuple[float, float, str, Optional[str], Optional[float]]:
    """
    Returns (unit_price, group_value_inr, price_source, winning_contract_id, contract_rate).
    
    Price sources:
    - 'CONTRACT_RATE' (from winning contract or lowest applicable contract rate)
    - 'PO_HISTORY' (from most recent PO in lookback_days)
    - 'STANDARD_PRICE' (from item master)
    - 'ESTIMATED_PRICE' (for NEW items)
    """
    # Clause 1.2: New items
    if group.is_new_item or group.resolved_item_code == "NEW":
        est_price = 0.0
        # Check first line estimated price
        for line in group.lines:
            if line.get("estimated_unit_price") is not None:
                est_price = float(line["estimated_unit_price"])
                break
        total_val = group.total_quantity * est_price
        return est_price, total_val, "ESTIMATED_PRICE", None, None

    item_code = group.resolved_item_code
    req_date = group.requirement_date
    qty = group.total_quantity
    
    # Clause 3.1(a): Check rate contracts
    winning = ceiling_ledger.select_winning_contract(item_code, req_date, qty)
    if winning:
        win_contract, rate, total_val = winning
        return rate, total_val, "CONTRACT_RATE", win_contract.contract_id, rate
        
    # Check if there are applicable contracts that are out of ceiling
    lowest_rate = ceiling_ledger.get_lowest_applicable_contract_rate(item_code, req_date)
    if lowest_rate is not None:
        # All contracts out of ceiling, but policy 3.1(a) says use lowest applicable contract rate
        total_val = qty * lowest_rate
        return lowest_rate, total_val, "CONTRACT_RATE", None, lowest_rate
        
    # Clause 3.1(b): Price on most recent PO for the item in 365 days before requirement date
    pos = po_history_by_item.get(item_code, [])
    start_365 = req_date - timedelta(days=lookback_days)
    recent_pos = [
        p for p in pos 
        if start_365 <= p["po_date"] < req_date and p.get("is_active_supplier", True)
    ]
    if recent_pos:
        recent_pos.sort(key=lambda x: (x["po_date"], int(x["po_number"])), reverse=True)
        po_price = float(recent_pos[0]["unit_price"])
        total_val = qty * po_price
        return po_price, total_val, "PO_HISTORY", None, None
        
    # Clause 3.1(c): Item master standard price
    item_info = item_master_by_code.get(item_code)
    if item_info and item_info.get("standard_price") is not None:
        std_price = float(item_info["standard_price"])
        total_val = qty * std_price
        return std_price, total_val, "STANDARD_PRICE", None, None
        
    # Fallback to estimated unit price if present
    est_price = 0.0
    for line in group.lines:
        if line.get("estimated_unit_price") is not None:
            est_price = float(line["estimated_unit_price"])
            break
    total_val = qty * est_price
    return est_price, total_val, "ESTIMATED_PRICE", None, None

