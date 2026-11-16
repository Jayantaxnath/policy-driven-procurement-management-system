"""
Purchase Order Consolidation Module.
Implements Clauses 7.1 and 7.2:
- Combines requirements that end in a PO into consolidated POs.
- Condition: same supplier, same plant, same route, raised within 24 hours of the first requirement on that PO.
- Sourcing requests are NEVER consolidated.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional

class ConsolidatedPO:
    def __init__(self, po_id: str, first_requirement: Dict[str, Any]):
        self.po_id = po_id
        self.supplier_id: str = first_requirement["supplier_id"]
        self.plant: str = first_requirement["plant"]
        self.route: str = first_requirement["route"]
        self.first_created_at: datetime = first_requirement["first_line_created_at"]
        self.requirements: List[Dict[str, Any]] = [first_requirement]

    def can_consolidate(self, req: Dict[str, Any], max_window_hours: float = 24.0) -> bool:
        if req.get("decision") != "PO":
            return False
            
        if req.get("supplier_id") != self.supplier_id:
            return False
            
        if req.get("plant") != self.plant:
            return False
            
        if req.get("route") != self.route:
            return False
            
        # Raised within 24 hours of first requirement on that PO (measured from creation time of each requirement's first line)
        diff_seconds = abs((req["first_line_created_at"] - self.first_created_at).total_seconds())
        if diff_seconds > (max_window_hours * 3600):
            return False
            
        return True

    def add_requirement(self, req: Dict[str, Any]):
        self.requirements.append(req)


def consolidate_purchase_orders(
    requirements: List[Dict[str, Any]], 
    max_window_hours: float = 24.0
) -> Dict[str, ConsolidatedPO]:
    """
    Takes requirements ending in PO in order of creation time.
    A requirement joins the earliest open PO it qualifies for; otherwise starts a new PO.
    Assigns 'po_id' to each requirement.
    """
    # Filter PO requirements and sort by first line creation time
    po_reqs = [r for r in requirements if r.get("decision") == "PO"]
    po_reqs.sort(key=lambda x: x["first_line_created_at"])
    
    open_pos: List[ConsolidatedPO] = []
    po_counter = 1
    
    for req in po_reqs:
        joined = False
        for cpo in open_pos:
            if cpo.can_consolidate(req, max_window_hours):
                cpo.add_requirement(req)
                req["po_id"] = cpo.po_id
                joined = True
                break
                
        if not joined:
            new_po_id = f"PO-{po_counter:04d}"
            po_counter += 1
            req["po_id"] = new_po_id
            new_cpo = ConsolidatedPO(new_po_id, req)
            open_pos.append(new_cpo)
            
    return {cpo.po_id: cpo for cpo in open_pos}

