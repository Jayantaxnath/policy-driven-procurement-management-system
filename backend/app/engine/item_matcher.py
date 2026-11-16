"""
Item Matcher Module.
Implements Clause 1.1 and 1.2:
- Matches given item_code against item_master.
- If missing, normalizes description and fuzzy matches against item_master descriptions.
- Distinguishes high-confidence matches vs ambiguous matches vs NEW items.
"""
import re
from typing import Tuple, Optional, List, Dict, Any
from rapidfuzz import fuzz

COMMON_ABBREVIATIONS = {
    r"\bbrg\b": "ball bearing",
    r"\bpneu\b": "pneumatic",
    r"\brod\b": "electrode",
    r"\bhyd\b": "hydraulic",
    r"\bsec\b": "security",
    r"\bhousekeep\b": "housekeeping",
    r"\bcalib\b": "calibration",
    r"\bmcb\b": "mcb",
    r"\bpt\b": "point",
}

CLEANUP_PHRASES = [
    r"\bfor maintenance\b",
    r"\burgent\b",
    r"\bas per sample\b",
    r"\brepeat\b",
    r"\bneeded\b",
    r"\brequired\b"
]

def normalize_description(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    
    # Remove quotes and non-alphanumeric noise (keep dimensions like 50x100, 6205-2rs)
    text = re.sub(r'["\']', " ", text)
    text = re.sub(r"[\(\)\[\]]", " ", text)
    
    # Expand known domain abbreviations
    for pattern, replacement in COMMON_ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text)
        
    # Strip contextual noise phrases
    for phrase in CLEANUP_PHRASES:
        text = re.sub(phrase, " ", text)
        
    # Replace multiple hyphens/underscores/slashes with spaces for token matching
    text = re.sub(r"[,\-_/]", " ", text)
    return " ".join(text.split())

class ItemMatcher:
    def __init__(self, master_items: List[Dict[str, Any]]):
        """
        master_items: list of dicts with keys:
          'item_code', 'description', 'uom', 'category', 'item_type', 'standard_price'
        """
        self.master_items = master_items
        self.code_map = {item["item_code"].strip(): item for item in master_items}
        
        # Pre-normalize catalog descriptions
        self.normalized_catalog = []
        for item in master_items:
            norm_desc = normalize_description(item["description"])
            self.normalized_catalog.append((item["item_code"], norm_desc, item))

    def resolve(
        self, 
        item_code: Optional[str], 
        description: Optional[str]
    ) -> Tuple[str, float, Optional[Dict[str, Any]]]:
        """
        Resolves item to (resolved_code, confidence, item_master_dict).
        If matched: ('ITM-XXXX', confidence_0_to_1, item_dict)
        If genuinely NEW item: ('NEW', 0.0, None)
        """
        # 1. Direct item code check
        if item_code:
            code_clean = str(item_code).strip()
            if code_clean in self.code_map:
                return code_clean, 1.0, self.code_map[code_clean]
        
        # 2. Description match
        if not description or not str(description).strip():
            return "NEW", 0.0, None
            
        norm_query = normalize_description(str(description))
        if not norm_query:
            return "NEW", 0.0, None

        best_score = 0.0
        best_match = None

        for code, norm_desc, item in self.normalized_catalog:
            # Token sort and token set ratios
            score_ts = fuzz.token_sort_ratio(norm_query, norm_desc)
            score_set = fuzz.token_set_ratio(norm_query, norm_desc)
            score = max(score_ts, score_set) / 100.0
            
            if score > best_score:
                best_score = score
                best_match = (code, item)

        # Thresholds:
        # Worked example 7: "hyd hose 1/2 inch 2 wire" -> matches ITM-1035
        # Worked example 13: "Drinking water purifier 50 LPH" -> NEW (score is low < 0.60)
        # Worked example 10: "Aluminium plate 6061 10mm" -> ITM-1006
        if best_score >= 0.70 and best_match:
            return best_match[0], best_score, best_match[1]
        
        return "NEW", best_score, None

