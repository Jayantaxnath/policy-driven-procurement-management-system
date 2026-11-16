"""
Generic AST Condition Evaluator for Policy-as-Data.
Evaluates nested AND, OR, NOT and comparison expressions against a context dictionary.
Zero hardcoded business limits.
"""
from typing import Dict, Any, List

def get_field_value(context: Dict[str, Any], field_path: str) -> Any:
    """
    Traverses dot-separated field paths like 'item.item_type' or 'requirement.group_value_inr'
    """
    parts = field_path.split(".")
    curr = context
    for p in parts:
        if isinstance(curr, dict):
            curr = curr.get(p)
        else:
            curr = getattr(curr, p, None)
        if curr is None:
            return None
    return curr

def evaluate_leaf_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    field = condition.get("field")
    operator = condition.get("operator", "EQUALS").upper()
    target_value = condition.get("value")
    
    actual_value = get_field_value(context, field)
    
    if operator == "EQUALS":
        return actual_value == target_value
    elif operator == "NOT_EQUALS":
        return actual_value != target_value
    elif operator == "LESS_THAN":
        if actual_value is None or target_value is None:
            return False
        return float(actual_value) < float(target_value)
    elif operator == "LESS_THAN_OR_EQUAL":
        if actual_value is None or target_value is None:
            return False
        return float(actual_value) <= float(target_value)
    elif operator == "GREATER_THAN":
        if actual_value is None or target_value is None:
            return False
        return float(actual_value) > float(target_value)
    elif operator == "GREATER_THAN_OR_EQUAL":
        if actual_value is None or target_value is None:
            return False
        return float(actual_value) >= float(target_value)
    elif operator == "IN":
        if not isinstance(target_value, list):
            return False
        return actual_value in target_value
    elif operator == "NOT_IN":
        if not isinstance(target_value, list):
            return True
        return actual_value not in target_value
    elif operator == "CONTAINS":
        if isinstance(actual_value, (list, str)):
            return target_value in actual_value
        return False
    else:
        # Unknown operator
        return False

def evaluate_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Recursively evaluates condition expressions:
    - {"AND": [cond1, cond2, ...]}
    - {"OR": [cond1, cond2, ...]}
    - {"NOT": cond}
    - {"field": "...", "operator": "...", "value": ...}
    """
    if not condition:
        return True
        
    if "AND" in condition:
        return all(evaluate_condition(sub, context) for sub in condition["AND"])
        
    if "OR" in condition:
        return any(evaluate_condition(sub, context) for sub in condition["OR"])
        
    if "NOT" in condition:
        return not evaluate_condition(condition["NOT"], context)
        
    return evaluate_leaf_condition(condition, context)

