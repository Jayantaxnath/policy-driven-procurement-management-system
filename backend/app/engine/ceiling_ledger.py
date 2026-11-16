"""
Run-Isolated Contract Ceiling Ledger.
Implements Clauses 4.1, 4.2, 4.3, 4.4, and 5.7:
- Checks contract coverage, date validity, supplier Active status.
- Evaluates available ceiling.
- Picks lowest rate contract with sufficient ceiling (Clause 4.3).
- Tracks dynamic ceiling consumption during a batch run.
"""
from datetime import date
from typing import Dict, Any, List, Optional, Tuple

class ContractLedgerItem:
    def __init__(
        self,
        contract_id: str,
        supplier_id: str,
        supplier_name: str,
        start_date: date,
        end_date: date,
        value_cap: float,
        initial_consumed: float,
        is_supplier_active: bool,
        lines: Dict[str, float]  # item_code -> rate
    ):
        self.contract_id = contract_id
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name
        self.start_date = start_date
        self.end_date = end_date
        self.value_cap = value_cap
        self.current_consumed = initial_consumed
        self.is_supplier_active = is_supplier_active
        self.lines = lines  # item_code -> rate

    @property
    def remaining_ceiling(self) -> float:
        return max(0.0, self.value_cap - self.current_consumed)

    def applies_to(self, item_code: str, req_date: date) -> bool:
        # Clause 4.1:
        # 1. Covers the item
        # 2. Requirement date between start and end dates (inclusive)
        # 3. Contract supplier is Active in supplier master
        if item_code not in self.lines:
            return False
        if not (self.start_date <= req_date <= self.end_date):
            return False
        if not self.is_supplier_active:
            return False
        return True

    def can_cover(self, item_code: str, total_quantity: float) -> Tuple[bool, float, float]:
        """
        Returns (can_use, rate, total_cost).
        """
        rate = self.lines[item_code]
        total_cost = total_quantity * rate
        # Clause 4.2: consumed value + requirement's value must not exceed value_cap
        if self.current_consumed + total_cost <= self.value_cap:
            return True, rate, total_cost
        return False, rate, total_cost


class RunCeilingLedger:
    def __init__(self, contracts: List[ContractLedgerItem]):
        self.contracts = {c.contract_id: c for c in contracts}
        self.consumption_events: List[Dict[str, Any]] = []

    def get_applicable_contracts(self, item_code: str, req_date: date) -> List[ContractLedgerItem]:
        """
        Returns all contracts that cover item, are valid on req_date, and have Active supplier.
        """
        applicable = []
        for c in self.contracts.values():
            if c.applies_to(item_code, req_date):
                applicable.append(c)
        return applicable

    def get_lowest_applicable_contract_rate(self, item_code: str, req_date: date) -> Optional[float]:
        """
        Clause 3.1(a): If every applicable contract is out of ceiling, lowest applicable contract rate.
        """
        applicable = self.get_applicable_contracts(item_code, req_date)
        if not applicable:
            return None
        return min(c.lines[item_code] for c in applicable)

    def select_winning_contract(
        self, 
        item_code: str, 
        req_date: date, 
        total_quantity: float
    ) -> Optional[Tuple[ContractLedgerItem, float, float]]:
        """
        Implements Clause 4.3:
        If more than one contract applies, use the one with the lowest rate that still has enough ceiling.
        Returns (winning_contract, rate, total_cost) or None.
        """
        applicable = self.get_applicable_contracts(item_code, req_date)
        qualifying = []
        
        for c in applicable:
            can_use, rate, total_cost = c.can_cover(item_code, total_quantity)
            if can_use:
                qualifying.append((c, rate, total_cost))
                
        if not qualifying:
            return None
            
        # Clause 4.3: Lowest rate wins. Tie-breaker: earliest end date or contract_id
        qualifying.sort(key=lambda x: (x[1], x[0].contract_id))
        return qualifying[0]

    def consume_ceiling(
        self, 
        contract_id: str, 
        group_id: str, 
        amount: float
    ):
        """
        Deducts ceiling from the contract for this run.
        """
        c = self.contracts[contract_id]
        c.current_consumed += amount
        self.consumption_events.append({
            "contract_id": contract_id,
            "group_id": group_id,
            "amount": amount,
            "remaining": c.remaining_ceiling
        })

