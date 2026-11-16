"""
Contract PDF Parser for Corvo Engineering Rate Contracts.
Extracts contract details and Schedule A line items from contract PDFs.
"""
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional
import pypdf

def parse_contract_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Parses a signed rate contract PDF and returns structured data:
    {
        "contract_id": "RC-2026-031",
        "supplier_id": "S021",
        "supplier_name": "Pneumatic Point",
        "start_date": date(2026, 11, 15),
        "end_date": date(2027, 11, 14),
        "value_cap": 2000000.0,
        "consumed_value": 0.0,
        "lines": [
            {
                "item_code": "ITM-1036",
                "description": "Pneumatic cylinder 50x100",
                "uom": "NOS",
                "rate": 3537.76
            }, ...
        ]
    }
    """
    reader = pypdf.PdfReader(pdf_path)
    full_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    
    # Contract No.
    c_match = re.search(r"Contract No\.?\s*([A-Z0-9\-]+)", full_text, re.IGNORECASE)
    contract_id = c_match.group(1).strip() if c_match else ""
    
    # Supplier Name & ID: "between Corvo Engineering ... and Pneumatic Point, Pune (Supplier ID S021)"
    sup_match = re.search(r"and\s+([^,\n]+(?:,\s*[^,\n]+)?)\s*\(Supplier ID\s+([A-Z0-9]+)\)", full_text, re.IGNORECASE)
    if sup_match:
        supplier_name = sup_match.group(1).split(",")[0].strip()
        supplier_id = sup_match.group(2).strip()
    else:
        # Fallback search
        s_id_match = re.search(r"Supplier ID\s+([A-Z0-9]+)", full_text, re.IGNORECASE)
        supplier_id = s_id_match.group(1).strip() if s_id_match else ""
        supplier_name = ""
    
    # Term: "valid from 2026-11-15 to 2027-11-14"
    term_match = re.search(r"valid from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
    if term_match:
        start_date = datetime.strptime(term_match.group(1), "%Y-%m-%d").date()
        end_date = datetime.strptime(term_match.group(2), "%Y-%m-%d").date()
    else:
        start_date = date.today()
        end_date = date.today()
        
    # Ceiling: "shall not exceed INR 20,00,000" or similar
    cap_match = re.search(r"shall not exceed\s+INR\s+([\d,]+(?:\.\d+)?)", full_text, re.IGNORECASE)
    if cap_match:
        cap_str = cap_match.group(1).replace(",", "")
        value_cap = float(cap_str)
    else:
        value_cap = 0.0

    # Schedule A: Items and rates
    # Lines look like: "1 ITM-1036 Pneumatic cylinder 50x100 NOS 3,537.76"
    lines: List[Dict[str, Any]] = []
    # Pattern: optional line number, ITM-XXXX, description, UoM, rate
    line_pattern = re.compile(r"(?:^|\n)\s*(?:\d+\s+)?(ITM-\d{4})\s+(.+?)\s+([A-Z]{2,4})\s+([\d,]+\.?\d*)", re.MULTILINE)
    
    for match in line_pattern.finditer(full_text):
        item_code = match.group(1).strip()
        description = match.group(2).strip()
        uom = match.group(3).strip()
        rate_str = match.group(4).replace(",", "").strip()
        try:
            rate = float(rate_str)
        except ValueError:
            continue
            
        lines.append({
            "item_code": item_code,
            "description": description,
            "uom": uom,
            "rate": rate
        })
        
    return {
        "contract_id": contract_id,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "start_date": start_date,
        "end_date": end_date,
        "value_cap": value_cap,
        "consumed_value": 0.0,
        "lines": lines
    }

