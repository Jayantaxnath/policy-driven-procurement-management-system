"""
Policy Decision Engine.
Evaluates procurement policy rules dynamically from Policy-as-Data JSON.
Applies Section 5 decision rules (5.1 - 5.6) and global constraint (5.7).
Zero hardcoded business thresholds.
"""
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from app.engine.condition_evaluator import evaluate_condition
from app.engine.ceiling_ledger import RunCeilingLedger
from app.engine.supplier_ranker import compute_preferred_suppliers, suggest_suppliers_for_sourcing

class PolicyDecisionEngine:
    def __init__(self, policy_definition: Dict[str, Any]):
        self.policy = policy_definition
        self.version = policy_definition.get("policy_version", "v5.0")
        self.parameters = policy_definition.get("parameters", {})
        self.global_constraints = policy_definition.get("global_constraints", [])
        
        # Sort rules by priority ascending (1 first, 6 last)
        raw_rules = policy_definition.get("decision_rules", [])
        self.rules = sorted(raw_rules, key=lambda x: int(x.get("priority", 999)))

    def evaluate_requirement(
        self,
        group, # RequirementGroup
        unit_price: float,
        group_value_inr: float,
        price_source: str,
        winning_contract_id: Optional[str],
        contract_rate: Optional[float],
        ceiling_ledger: RunCeilingLedger,
        active_suppliers: Dict[str, Dict[str, Any]],
        po_history_by_item: Dict[str, List[Dict[str, Any]]],
        contract_history_by_item: Dict[str, List[Dict[str, Any]]],
        item_master_by_code: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluates a requirement group and returns the decision outcome dict:
        {
            "decision": "PO" | "SOURCING_REQUEST",
            "route": "CONTRACT_PO" | "EMERGENCY_PO" | "SPOT_PO" | "RFQ" | "RFP" | "CAPEX_SOURCING" | "NEW_ITEM_SOURCING",
            "supplier_id": Optional[str],
            "unit_price": Optional[float],
            "group_value_inr": float,
            "suggested_supplier_ids": Optional[str],
            "policy_version": str,
            "policy_clause": str,
            "reason": str
        }
        """
        # Clause 1.2: Check if NEW item
        if group.is_new_item or group.resolved_item_code == "NEW":
            return {
                "decision": "SOURCING_REQUEST",
                "route": "NEW_ITEM_SOURCING",
                "supplier_id": None,
                "unit_price": None,
                "group_value_inr": round(group_value_inr, 2),
                "suggested_supplier_ids": None,
                "policy_version": self.version,
                "policy_clause": "Clause 1.2",
                "reason": "Uncataloged item not in item master; routes to sourcing without supplier suggestions."
            }
            
        item_code = group.resolved_item_code
        req_date = group.requirement_date
        item_info = item_master_by_code.get(item_code, {})
        category = item_info.get("category", "")
        item_type = item_info.get("item_type", "Material")
        
        # Check purchase history in last 365 days from ACTIVE suppliers
        pos = po_history_by_item.get(item_code, [])
        start_365 = req_date - timedelta(days=self.parameters.get("po_history_lookback_days", 365))
        active_pos_365 = [
            p for p in pos 
            if start_365 <= p["po_date"] < req_date and p["supplier_id"] in active_suppliers
        ]
        bought_from_active_in_365d = (len(active_pos_365) > 0)
        
        # Build evaluation context for the AST condition evaluator
        context = {
            "item": {
                "item_code": item_code,
                "item_type": item_type,
                "category": category,
                "standard_price": item_info.get("standard_price", 0.0)
            },
            "requirement": {
                "plant": group.plant,
                "urgency": group.urgency,
                "total_quantity": group.total_quantity,
                "group_value_inr": group_value_inr
            },
            "contract": {
                "can_be_used": (winning_contract_id is not None),
                "winning_contract_id": winning_contract_id,
                "winning_rate": contract_rate
            },
            "history": {
                "bought_from_active_in_365d": bought_from_active_in_365d,
                "has_purchase_history": len(pos) > 0
            }
        }
        
        # Evaluate rules in priority order
        for rule in self.rules:
            cond = rule.get("condition", {})
            if evaluate_condition(cond, context):
                outcome = rule.get("outcome", {})
                route = outcome.get("route")
                decision = outcome.get("decision")
                clause = rule.get("clause", f"Rule {rule.get('rule_id')}")
                
                # Rule 5.2: CONTRACT_PO
                if route == "CONTRACT_PO":
                    win_contract = ceiling_ledger.contracts[winning_contract_id]
                    # Consume ceiling
                    ceiling_ledger.consume_ceiling(winning_contract_id, group.group_id, group_value_inr)
                    return {
                        "decision": "PO",
                        "route": "CONTRACT_PO",
                        "supplier_id": win_contract.supplier_id,
                        "unit_price": contract_rate,
                        "group_value_inr": round(group_value_inr, 2),
                        "suggested_supplier_ids": None,
                        "policy_version": self.version,
                        "policy_clause": clause,
                        "reason": f"Contract {winning_contract_id} with {win_contract.supplier_name} valid with sufficient ceiling."
                    }
                    
                # Rule 5.3 & 5.4: EMERGENCY_PO or SPOT_PO
                elif route in ("EMERGENCY_PO", "SPOT_PO"):
                    preferred = compute_preferred_suppliers(
                        item_code, req_date, active_suppliers,
                        po_history_by_item, contract_history_by_item,
                        lookback_days=self.parameters.get("preferred_supplier_lookback_days", 548),
                        weights=self.parameters.get("supplier_ranking_weights")
                    )
                    first_preferred = preferred[0] if preferred else None
                    sup_id = first_preferred["supplier_id"] if first_preferred else None
                    ref_price = first_preferred["reference_price"] if first_preferred else unit_price
                    
                    # Compute total requirement value at supplier's reference price
                    final_val = group.total_quantity * ref_price
                    
                    reason_desc = (
                        f"Emergency requisition within limit; awarded to 1st preferred supplier {sup_id} at reference price."
                        if route == "EMERGENCY_PO"
                        else f"Spot PO within threshold with proven purchase history; awarded to 1st preferred supplier {sup_id} at reference price."
                    )
                    return {
                        "decision": "PO",
                        "route": route,
                        "supplier_id": sup_id,
                        "unit_price": ref_price,
                        "group_value_inr": round(final_val, 2),
                        "suggested_supplier_ids": None,
                        "policy_version": self.version,
                        "policy_clause": clause,
                        "reason": reason_desc
                    }
                    
                # Sourcing events: RFQ, RFP, CAPEX_SOURCING
                else:
                    count_needed = outcome.get("suggest_suppliers_count", 3)
                    suggested = suggest_suppliers_for_sourcing(
                        item_code, category, req_date, count_needed,
                        active_suppliers, po_history_by_item, contract_history_by_item,
                        weights=self.parameters.get("supplier_ranking_weights")
                    )
                    suggested_str = ";".join(suggested) if suggested else None
                    
                    if route == "CAPEX_SOURCING":
                        reason = f"Capex equipment procurement requires sourcing event and Capex approval. {len(suggested)} suppliers suggested."
                    elif route == "RFQ":
                        reason = f"Requisition value requires 3 quotations under {clause}. Suggested {len(suggested)} suppliers."
                    elif route == "RFP":
                        reason = f"Formal RFP required for high-value requisition (>= INR 10 Lakh) under {clause}. Suggested {len(suggested)} suppliers."
                    else:
                        reason = f"Sourcing request initiated under {clause}."
                        
                    return {
                        "decision": decision,
                        "route": route,
                        "supplier_id": None,
                        "unit_price": None,
                        "group_value_inr": round(group_value_inr, 2),
                        "suggested_supplier_ids": suggested_str,
                        "policy_version": self.version,
                        "policy_clause": clause,
                        "reason": reason
                    }
                    
        # Fallback if no rule matched
        return {
            "decision": "SOURCING_REQUEST",
            "route": "RFQ",
            "supplier_id": None,
            "unit_price": None,
            "group_value_inr": round(group_value_inr, 2),
            "suggested_supplier_ids": None,
            "policy_version": self.version,
            "policy_clause": "Fallback",
            "reason": "Default sourcing event."
        }

