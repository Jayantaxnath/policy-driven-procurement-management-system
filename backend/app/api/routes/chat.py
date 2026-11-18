"""
Chat & Conversational PR Intake API routes.
Implements:
- POST /api/chat/pr-intake: Natural language conversational slot extraction and real-time policy evaluation.
- POST /api/chat/submit-pr: Saves the verified conversational PR into the database.
"""
import uuid
import re
import json
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import PRBatch, PRLine, BatchExecutionRun, Requirement, RequirementLine
from app.core.config import settings
from app.engine.pipeline import process_pr_batch, load_system_state
from app.engine.item_matcher import ItemMatcher

router = APIRouter(tags=["Chat & Conversational PR Intake"])

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Employee's natural language request")
    conversation_id: Optional[str] = Field(None, description="Session ID")
    current_slots: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Previously accumulated slots")

class SubmitPRRequest(BaseModel):
    item_code: Optional[str] = None
    description: str
    quantity: float
    uom: str = "NOS"
    plant: str
    need_by_date: str
    urgency: str = "Normal"
    requester: str = "Employee"
    department: str = "Operations"
    estimated_unit_price: Optional[float] = None


def _strip_markdown(text: str) -> str:
    """Strip common markdown symbols so the chat UI renders plain text."""
    if not text:
        return text
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # **bold** -> bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)        # *italic* -> italic
    text = re.sub(r"\`(.*?)\`", r"\1", text)          # `code` -> code
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)  # headings
    return text


def extract_slots_with_llm(user_message: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
    """Uses Gemini Flash if configured to extract PR slots."""
    if not settings.GEMINI_API_KEY:
        return {}

    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        today_str = date.today().isoformat()
        prompt = f"""
You are an expert procurement intake assistant for Corvo Engineering.
Today is {today_str}.

You extract structured procurement request slots from a natural language message.

EXISTING SLOTS (already collected in this conversation):
{json.dumps(current_slots, indent=2) if current_slots else "{}"}

NEW USER MESSAGE:
"{user_message}"

RULES:
1. Extract ONLY the item name for "item_description". Do NOT include quantity, plant, urgency, dates, or intent/action words like "need", "want", "request", "buy", "emergency", "breakdown", "replacement".
   - Example: For "I need 20 ball bearings for Pune plant by Friday", return "ball bearings".
   - Example: For "Emergency breakdown replacement ball bearings for Pune plant today", return "ball bearings".
   - Example: For "Request custom CNC tooling quote for Pune plant, quantity 5, estimated price 50000 per unit", return "custom CNC tooling".
2. Valid plants: PUN1 (Pune), CHK1 (Chakan). Map "Pune" -> "PUN1", "Chakan" -> "CHK1".
3. Valid urgency: Normal, Urgent, Emergency. "Emergency" or "breakdown" -> "Emergency".
4. For dates: "today" -> {today_str}, "tomorrow" -> next day, "Friday" -> next Friday. Return YYYY-MM-DD.
5. For estimated_unit_price: extract numeric value. "50k" -> 50000, "5 lakh" -> 500000.
6. Only update slots that are explicitly mentioned in the new message. Keep existing slots for fields not mentioned.
7. Return ONLY a valid JSON object. No markdown, no explanation.

Return this JSON structure (use null for fields not present in message):
{{
  "item_description": string or null,
  "item_code": string or null,
  "quantity": float or null,
  "uom": string or null,
  "plant": "PUN1" | "CHK1" | null,
  "need_by_date": "YYYY-MM-DD" | null,
  "urgency": "Normal" | "Urgent" | "Emergency" | null,
  "estimated_unit_price": float or null,
  "requester": string or null,
  "department": string or null
}}
"""
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL_PRIMARY,
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except Exception:
        return {}


def extract_slots_heuristics(
    user_message: str, current_slots: Dict[str, Any]
) -> Dict[str, Any]:
    """Deterministic rule-based slot extraction fallback."""
    slots = dict(current_slots or {})
    text = user_message.strip()
    text_lower = text.lower()

    # 1. Plant extraction
    if "pun1" in text_lower or "pune" in text_lower:
        slots["plant"] = "PUN1"
    elif "chk1" in text_lower or "chakan" in text_lower:
        slots["plant"] = "CHK1"

    # 2. Urgency extraction
    if "emergency" in text_lower or "breakdown" in text_lower:
        slots["urgency"] = "Emergency"
    elif "urgent" in text_lower or "critical" in text_lower or "asap" in text_lower:
        slots["urgency"] = "Urgent"
    elif not slots.get("urgency"):
        slots["urgency"] = "Normal"

    # 3. Item Code explicit check (ITM-XXXX)
    itm_match = re.search(r"\b(ITM-\d{4})\b", text, re.IGNORECASE)
    if itm_match:
        slots["item_code"] = itm_match.group(1).upper()

    # 4. Quantity extraction
    qty_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:units?|nos?|pieces?|pcs?|kg|meters?|mtr|sets?)?\b", text_lower)
    if qty_match and not slots.get("quantity"):
        try:
            val = float(qty_match.group(1))
            if val > 0:
                slots["quantity"] = val
        except ValueError:
            pass

    # 5. Need by date extraction
    if "today" in text_lower:
        slots["need_by_date"] = date.today().isoformat()
    elif "tomorrow" in text_lower:
        slots["need_by_date"] = (date.today() + timedelta(days=1)).isoformat()
    elif "next week" in text_lower:
        slots["need_by_date"] = (date.today() + timedelta(days=7)).isoformat()
    else:
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        today_weekday = date.today().weekday()
        for day_name, day_num in day_map.items():
            if day_name in text_lower:
                days_ahead = (day_num - today_weekday) % 7
                if days_ahead == 0:
                    days_ahead = 7
                slots["need_by_date"] = (date.today() + timedelta(days=days_ahead)).isoformat()
                break
        if not slots.get("need_by_date"):
            date_match = re.search(r"\b(202\d[-/]\d{1,2}[-/]\d{1,2})\b", text)
            if date_match:
                try:
                    d_str = date_match.group(1).replace("/", "-")
                    parsed_d = datetime.strptime(d_str, "%Y-%m-%d").date()
                    slots["need_by_date"] = parsed_d.isoformat()
                except ValueError:
                    pass

    # 6. Item description extraction (simple word-by-word, no regex mangling)
    if not slots.get("item_description") and not slots.get("item_code"):
        # Words to remove (lowercase) - these are context/intent words, NOT item names
        remove_words = {
            "i", "need", "please", "order", "can", "we", "get", "require",
            "want", "to", "buy", "purchase", "request", "quote", "replacement",
            "for", "pune", "chakan", "pun1", "chk1", "emergency", "urgent",
            "urgency", "breakdown", "critical", "asap", "today", "tomorrow",
            "friday", "monday", "tuesday", "wednesday", "thursday", "saturday",
            "sunday", "next", "week", "units", "nos", "pieces", "pcs", "kg",
            "meters", "mtr", "sets", "liters", "litres", "price", "rate",
            "cost", "budget", "estimated", "unit", "per", "total", "k",
            "lakh", "lakhs", "some", "a", "an", "the", "by", "at", "of",
            "in", "and", "or", "plant", "quantity", "me",
        }
        words = text.split()
        kept = []
        for w in words:
            w_clean = w.strip(".,!?")
            # Skip pure numbers (with optional trailing punctuation)
            if re.match(r"^\d+(?:\.\d+)?$", w_clean):
                continue
            # Skip words in remove set (case-insensitive)
            if w_clean.lower() in remove_words:
                continue
            # Skip currency symbols
            if w_clean in ("₹", "$", "rs", "inr", "Rs", "INR"):
                continue
            # Skip price-like tokens (e.g., "50000")
            if re.match(r"^\d+(?:,\d+)*(?:\.\d+)?$", w_clean):
                continue
            kept.append(w_clean)
        cleaned = " ".join(kept).strip()
        # Remove any remaining currency symbols
        cleaned = cleaned.replace("₹", "").replace("$", "").strip()
        if len(cleaned) > 2:
            slots["item_description"] = cleaned

    # 7. Estimated Unit Price / Budget extraction
    if slots.get("estimated_unit_price") is None:
        price_patterns = [
            r"(?:price|rate|estimated(?:\s+price)?|budget|cost|unit\s+price)\s*(?:of|is|at|:|=)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|lakh|lakhs)?",
            r"(?:rs\.?|inr|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|lakh|lakhs)?",
            r"@\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)",
        ]
        for p in price_patterns:
            m = re.search(p, text_lower)
            if m:
                try:
                    p_val = float(m.group(1).replace(",", ""))
                    suffix = m.group(2) if m.lastindex >= 2 else ""
                    if suffix:
                        suffix = suffix.lower()
                        if suffix == "k":
                            p_val *= 1000
                        elif suffix in ("lakh", "lakhs"):
                            p_val *= 100000
                    text_before = text_lower[: m.start()]
                    is_total = bool(re.search(r"\btotal\b", text_before))
                    if is_total:
                        slots["estimated_total_price"] = p_val
                        if slots.get("quantity") and float(slots["quantity"]) > 0:
                            slots["estimated_unit_price"] = p_val / float(slots["quantity"])
                        else:
                            slots["estimated_unit_price"] = None
                    else:
                        slots["estimated_unit_price"] = p_val
                        slots["estimated_total_price"] = None
                    break
                except ValueError:
                    pass

    if not slots.get("uom"):
        slots["uom"] = "NOS"
    if not slots.get("requester"):
        slots["requester"] = "Employee"
    if not slots.get("department"):
        slots["department"] = "Operations"

    return slots


@router.post("/chat/pr-intake")
def chat_pr_intake(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Intelligent conversational agent for raising PRs.
    Extracts slots, prompts for missing information, and evaluates real-time policy outcome once complete.
    """
    slots = dict(payload.current_slots or {})

    # Extract via LLM first if available
    llm_slots = extract_slots_with_llm(user_message=payload.message, current_slots=slots)
    if llm_slots:
        for k, v in llm_slots.items():
            if v is not None:
                slots[k] = v

    # Run heuristics to fill any gaps LLM missed
    heuristic_slots = extract_slots_heuristics(payload.message, slots)
    for k, v in heuristic_slots.items():
        if v is not None and slots.get(k) is None:
            slots[k] = v

    # Calculate estimated_unit_price from estimated_total_price if quantity is known
    if slots.get("estimated_total_price") and slots.get("quantity") and float(slots["quantity"]) > 0:
        if not slots.get("estimated_unit_price"):
            slots["estimated_unit_price"] = slots["estimated_total_price"] / float(slots["quantity"])

    # Calculate estimated_total_price from estimated_unit_price if quantity is known
    if slots.get("estimated_unit_price") and slots.get("quantity") and float(slots["quantity"]) > 0:
        if not slots.get("estimated_total_price"):
            slots["estimated_total_price"] = slots["estimated_unit_price"] * float(slots["quantity"])

    # Validate slots and check what is missing
    missing = []
    if not slots.get("item_description") and not slots.get("item_code"):
        missing.append("item description or item code")
    if not slots.get("quantity") or float(slots.get("quantity", 0)) <= 0:
        missing.append("quantity")
    if not slots.get("plant") or slots.get("plant") not in ["PUN1", "CHK1"]:
        missing.append("target plant (Pune - PUN1 or Chakan - CHK1)")
    if not slots.get("need_by_date"):
        slots["need_by_date"] = (date.today() + timedelta(days=7)).isoformat()

    if missing:
        if "item description or item code" in missing:
            msg = "Could you please specify which item you need to procure?"
        elif "quantity" in missing:
            msg = f"How many units of '{slots.get('item_description') or slots.get('item_code')}' do you require?"
        elif "target plant (Pune - PUN1 or Chakan - CHK1)" in missing:
            msg = _strip_markdown("Which plant is this requirement for: Pune (PUN1) or Chakan (CHK1)?")
        else:
            msg = f"Please provide the following details to proceed: {', '.join(missing)}."
        return {
            "status": "NEEDS_INFO",
            "message": msg,
            "slots": slots,
            "missing_fields": missing,
            "evaluation": None
        }

    # All required slots present -> Run Deterministic Decision Engine
    state = load_system_state(db)
    matcher = ItemMatcher(state["items_list"])
    raw_code = slots.get("resolved_item_code") or slots.get("item_code")
    desc = slots.get("item_description", "")
    resolved_code, conf, item_info = matcher.resolve(raw_code, desc)

    # Build single-row PR DataFrame
    pr_row = {
        "pr_no": f"CHAT-{datetime.now().strftime('%H%M%S')}",
        "pr_line": 1,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "requester": slots.get("requester", "Employee"),
        "department": slots.get("department", "Operations"),
        "plant": slots["plant"],
        "item_code": raw_code or resolved_code or "",
        "description": desc or (item_info.get("description") if item_info else ""),
        "quantity": float(slots["quantity"]),
        "uom": slots.get("uom", "NOS"),
        "estimated_unit_price": float(slots["estimated_unit_price"]) if slots.get("estimated_unit_price") is not None else None,
        "need_by_date": slots["need_by_date"],
        "urgency": slots.get("urgency", "Normal")
    }

    df_single = pd.DataFrame([pr_row])
    decision_rows, stats = process_pr_batch(df_single, db)
    decision_res = decision_rows[0] if decision_rows else {}

    # Craft conversational explanation
    plant_name = "Pune (PUN1)" if slots["plant"] == "PUN1" else "Chakan (CHK1)"
    item_label = f"{resolved_code} ({item_info.get('description', desc)})" if resolved_code and item_info else (desc or "Custom Item")

    if decision_res.get("decision") == "PO":
        sup_id = decision_res.get("supplier_id")
        sup_info = state["active_suppliers"].get(sup_id, {})
        sup_name = sup_info.get("name", sup_id)
        u_price = decision_res.get("unit_price", 0.0)
        tot_val = decision_res.get("group_value_inr", 0.0)
        explanation = (
            f"✅ **Purchase Order Approved ({decision_res.get('route')})**\n\n"
            f"- **Item**: {item_label}\n"
            f"- **Plant**: {plant_name}\n"
            f"- **Quantity**: {slots['quantity']} {slots.get('uom', 'NOS')}\n"
            f"- **Assigned Supplier**: {sup_name} (`{sup_id}`)\n"
            f"- **Unit Price**: ₹{u_price:,.2f} | **Total Value**: ₹{tot_val:,.2f}\n"
            f"- **Policy Reason**: {decision_res.get('reason')}\n\n"
            f"You can submit now by clicking Submit to Buyer Workspace (green button) on the right side."
        )
        explanation = _strip_markdown(explanation)
    elif decision_res.get("decision") == "SOURCING_REQUEST":
        sugs = decision_res.get("suggested_supplier_ids", "None")
        tot_val = decision_res.get("group_value_inr", 0.0)
        u_val = decision_res.get("unit_price")
        u_price_text = f"₹{u_val:,.2f} per unit | " if u_val else ""
        explanation = (
            f"📋 **Sourcing Request Required ({decision_res.get('route')})**\n\n"
            f"- **Item**: {item_label}\n"
            f"- **Plant**: {plant_name}\n"
            f"- **Quantity**: {slots['quantity']} {slots.get('uom', 'NOS')}\n"
            f"- **Valuation**: {u_price_text}Total: ₹{tot_val:,.2f}\n"
            f"- **Suggested Suppliers**: `{sugs}`\n"
            f"- **Policy Reason**: {decision_res.get('reason')}\n\n"
            f"You can submit now by clicking Submit to Buyer Workspace (green button) on the right side."
        )
        explanation = _strip_markdown(explanation)
    else:
        explanation = (
            f"⚠️ **Could Not Process PR**: {decision_res.get('reason', 'Missing valid data')}"
        )
        explanation = _strip_markdown(explanation)

    return {
        "status": "EVALUATED",
        "message": explanation,
        "slots": slots,
        "missing_fields": [],
        "evaluation": decision_res,
        "resolved_item": {
            "resolved_item_code": resolved_code,
            "confidence": conf,
            "item_info": item_info
        }
    }


@router.post("/chat/submit-pr")
def submit_chat_pr(
    payload: SubmitPRRequest,
    db: Session = Depends(get_db)
):
    """
    Submits a conversational PR, evaluates and saves it into the database for buyer workspace review.
    """
    batch_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    batch_rec = PRBatch(
        batch_id=batch_id,
        batch_name=f"Chat_PR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        source_type="CHAT",
        uploaded_by=payload.requester
    )
    db.add(batch_rec)
    db.commit()

    pr_no = f"PR-CHAT-{datetime.now().strftime('%m%d-%H%M')}"
    pr_row = {
        "pr_no": pr_no,
        "pr_line": 1,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "requester": payload.requester,
        "department": payload.department,
        "plant": payload.plant,
        "item_code": payload.item_code or "",
        "description": payload.description,
        "quantity": payload.quantity,
        "uom": payload.uom,
        "estimated_unit_price": payload.estimated_unit_price,
        "need_by_date": payload.need_by_date,
        "urgency": payload.urgency
    }

    df_single = pd.DataFrame([pr_row])
    decision_rows, stats = process_pr_batch(df_single, db)
    decision = decision_rows[0] if decision_rows else {}

    # Save PR Line
    pr_line_id = str(uuid.uuid4())
    pr_line = PRLine(
        id=pr_line_id,
        batch_id=batch_id,
        pr_no=pr_no,
        pr_line=1,
        created_at=datetime.now(),
        requester=payload.requester,
        department=payload.department,
        plant=payload.plant,
        item_code=payload.item_code,
        description=payload.description,
        quantity=payload.quantity,
        uom=payload.uom,
        estimated_unit_price=payload.estimated_unit_price,
        need_by_date=payload.need_by_date,
        urgency=payload.urgency,
        ingestion_status="PROCESSED"
    )
    db.add(pr_line)

    # Save Batch Execution Run
    exec_run = BatchExecutionRun(
        run_id=run_id,
        batch_id=batch_id,
        policy_version_id=decision.get("policy_version", "v5.0"),
        status="COMPLETED",
        total_pr_lines=1,
        total_requirements=1,
        total_pos=1 if decision.get("decision") == "PO" else 0,
        total_sourcing_requests=1 if decision.get("decision") == "SOURCING_REQUEST" else 0,
        total_not_processed=0
    )
    db.add(exec_run)

    # Save Requirement
    raw_gid = decision.get("group_id", "REQ-0001")
    req_id = f"{run_id[:8]}-{raw_gid}"
    req = Requirement(
        requirement_id=req_id,
        run_id=run_id,
        resolved_item_code=decision.get("resolved_item_code"),
        is_new_item=(decision.get("resolved_item_code") == "NEW"),
        plant=payload.plant,
        requirement_date=datetime.strptime(payload.need_by_date, "%Y-%m-%d").date(),
        total_quantity=payload.quantity,
        uom=payload.uom,
        urgency=payload.urgency,
        unit_price=decision.get("unit_price") or payload.estimated_unit_price,
        group_value_inr=decision.get("group_value_inr"),
        price_source="ESTIMATED_PRICE" if (decision.get("resolved_item_code") == "NEW" and payload.estimated_unit_price) else "WATERFALL",
        decision=decision.get("decision"),
        route=decision.get("route"),
        supplier_id=decision.get("supplier_id"),
        po_id=decision.get("po_id"),
        suggested_supplier_ids=decision.get("suggested_supplier_ids"),
        policy_version_id=decision.get("policy_version", "v5.0"),
        reason=decision.get("reason")
    )
    db.add(req)

    # Link RequirementLine
    req_line = RequirementLine(
        requirement_id=req_id,
        pr_line_id=pr_line_id
    )
    db.add(req_line)
    db.commit()

    return {
        "status": "success",
        "message": f"PR {pr_no} submitted and registered successfully.",
        "pr_no": pr_no,
        "requirement_id": req_id,
        "run_id": run_id,
        "decision": decision
    }