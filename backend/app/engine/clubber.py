"""
Requirement Clubbing Module (Anti-Splitting).
Implements Clauses 2.1, 2.2, 2.3, and 1.2.
"""
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

class RequirementGroup:
    def __init__(self, group_id: str, first_line: Dict[str, Any]):
        self.group_id = group_id
        self.resolved_item_code: str = first_line["resolved_item_code"]
        self.is_new_item: bool = (self.resolved_item_code == "NEW")
        self.plant: str = first_line["plant"]
        
        # Requirement date is the creation date of its first line (Clause 2.3)
        self.first_line_created_at: datetime = first_line["created_at"]
        self.first_line_need_by_date: date = first_line["need_by_date"]
        self.requirement_date: date = self.first_line_created_at.date()
        
        self.uom: str = first_line.get("uom", "NOS")
        self.lines: List[Dict[str, Any]] = [first_line]
        self.total_quantity: float = float(first_line["quantity"])
        # Bug Fix: preserve "Urgent" instead of downgrading to "Normal"
        first_urgency = str(first_line.get("urgency", "Normal")).strip()
        self.urgency: str = first_urgency if first_urgency else "Normal"

    def can_join(self, line: Dict[str, Any], max_creation_days: int = 14, max_need_by_days: int = 7) -> bool:
        # Clause 1.2: New items are never clubbed
        if self.is_new_item or line["resolved_item_code"] == "NEW":
            return False
            
        # Same item
        if line["resolved_item_code"] != self.resolved_item_code:
            return False
            
        # Same plant
        if line["plant"] != self.plant:
            return False
            
        # Created within 14 calendar days of requirement's first line
        creation_diff = (line["created_at"].date() - self.requirement_date).days
        if not (0 <= creation_diff <= max_creation_days):
            return False
            
        # Need-by date within 7 days (either side) of first line's need-by date
        need_by_diff = abs((line["need_by_date"] - self.first_line_need_by_date).days)
        if need_by_diff > max_need_by_days:
            return False
            
        return True

    def add_line(self, line: Dict[str, Any]):
        self.lines.append(line)
        self.total_quantity += float(line["quantity"])
        # Clause 2.3: If any line is Emergency, requirement becomes Emergency.
        # Preserve Urgent over Normal (Bug Fix: was only checking for Emergency).
        line_urgency = str(line.get("urgency", "Normal")).strip()
        if line_urgency.lower() == "emergency":
            self.urgency = "Emergency"
        elif line_urgency.lower() == "urgent" and self.urgency.lower() not in ("emergency",):
            self.urgency = "Urgent"


def club_pr_lines(
    lines: List[Dict[str, Any]], 
    valid_plants: Optional[List[str]] = None,
    max_creation_days: int = 14,
    max_need_by_days: int = 7
) -> Tuple[List[RequirementGroup], List[Dict[str, Any]]]:
    """
    Sorts PR lines chronologically and groups them into requirements.
    Returns (valid_groups, not_processed_lines).
    """
    if valid_plants is None:
        valid_plants = ["PUN1", "CHK1"]
        
    valid_lines = []
    not_processed_lines = []
    
    # 1. Validation & Pre-filter
    for line in lines:
        qty = float(line.get("quantity", 0) or 0)
        plant = str(line.get("plant", "")).strip()
        
        if qty <= 0:
            unproc = dict(line)
            unproc["decision"] = "NOT_PROCESSED"
            unproc["route"] = "NOT_PROCESSED"
            unproc["reason"] = f"Invalid quantity: {qty}. Requisition line rejected."
            not_processed_lines.append(unproc)
            continue
            
        if plant not in valid_plants:
            unproc = dict(line)
            unproc["decision"] = "NOT_PROCESSED"
            unproc["route"] = "NOT_PROCESSED"
            unproc["reason"] = f"Invalid plant: {plant} not recognized in Corvo operating plants."
            not_processed_lines.append(unproc)
            continue
            
        valid_lines.append(line)
        
    # Clause 2.2: "Take PR lines in order of creation time (then PR number, then line number)."
    valid_lines.sort(key=lambda x: (x["created_at"], str(x["pr_no"]), int(x["pr_line"])))
    
    groups: List[RequirementGroup] = []
    group_counter = 1
    
    for line in valid_lines:
        joined = False
        # "If it could join more than one, it joins the earliest."
        for group in groups:
            if group.can_join(line, max_creation_days, max_need_by_days):
                group.add_line(line)
                line["group_id"] = group.group_id
                joined = True
                break
                
        if not joined:
            gid = f"REQ-{group_counter:04d}"
            group_counter += 1
            line["group_id"] = gid
            new_grp = RequirementGroup(gid, line)
            groups.append(new_grp)
            
    return groups, not_processed_lines
