"""
Policy Administration API routes.
Implements:
- GET /api/policy/active: Fetches the currently active policy version and rules.
- GET /api/policy/versions: Lists all policy versions with status and metadata.
- GET /api/policy/{version_id}: Returns full rules definition and history for a version.
- POST /api/policy/upload: Ingests policy amendment document or text, generates structured diff against active policy, and saves as DRAFT.
- POST /api/policy/{version_id}/approve: Approves and activates the policy dynamically without code changes or restarts.
"""
import uuid
import copy
import re
import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import get_db
from app.db.models import PolicyVersion, PolicyApproval, AuditLog
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Policy Administration"])

class PolicyApprovalRequest(BaseModel):
    actor: str = Field(default="CPO / Head of Procurement", description="Name/title of approving authority")
    notes: Optional[str] = Field(None, description="Approval notes")

class PolicyAmendmentJSONRequest(BaseModel):
    version_id: str = Field(..., description="Unique version identifier, e.g. v5.1")
    name: str = Field(..., description="Policy name, e.g. Corvo Procurement Policy v5.1")
    effective_date: str = Field(..., description="Effective date (YYYY-MM-DD)")
    amendment_text: Optional[str] = Field(None, description="Text explanation of the amendment")
    rules_definition: Optional[Dict[str, Any]] = Field(None, description="Direct updated rules JSON if provided")
    created_by: str = Field(default="Policy Admin", description="Author of the amendment")

def compute_json_diff(old_dict: Any, new_dict: Any, path: str = "") -> List[Dict[str, Any]]:
    """
    Computes human-readable list of changes between old and new policy definitions.
    """
    diffs = []
    if isinstance(old_dict, dict) and isinstance(new_dict, dict):
        all_keys = set(old_dict.keys()).union(set(new_dict.keys()))
        for k in sorted(all_keys):
            sub_path = f"{path}.{k}" if path else k
            if k not in old_dict:
                diffs.append({"path": sub_path, "type": "ADDED", "old_value": None, "new_value": new_dict[k]})
            elif k not in new_dict:
                diffs.append({"path": sub_path, "type": "REMOVED", "old_value": old_dict[k], "new_value": None})
            elif old_dict[k] != new_dict[k]:
                if isinstance(old_dict[k], (dict, list)) and isinstance(new_dict[k], (dict, list)):
                    diffs.extend(compute_json_diff(old_dict[k], new_dict[k], sub_path))
                else:
                    diffs.append({"path": sub_path, "type": "MODIFIED", "old_value": old_dict[k], "new_value": new_dict[k]})
    elif isinstance(old_dict, list) and isinstance(new_dict, list):
        if old_dict != new_dict:
            # Check if list of dicts with rule_id
            if any(isinstance(x, dict) and "rule_id" in x for x in old_dict + new_dict):
                old_map = {x["rule_id"]: x for x in old_dict if isinstance(x, dict) and "rule_id" in x}
                new_map = {x["rule_id"]: x for x in new_dict if isinstance(x, dict) and "rule_id" in x}
                all_rids = sorted(set(old_map.keys()).union(set(new_map.keys())))
                for rid in all_rids:
                    r_path = f"{path}[Rule {rid}]"
                    if rid not in old_map:
                        diffs.append({"path": r_path, "type": "ADDED", "old_value": None, "new_value": new_map[rid]})
                    elif rid not in new_map:
                        diffs.append({"path": r_path, "type": "REMOVED", "old_value": old_map[rid], "new_value": None})
                    else:
                        diffs.extend(compute_json_diff(old_map[rid], new_map[rid], r_path))
            else:
                # Value or string list
                diffs.append({"path": path, "type": "MODIFIED", "old_value": old_dict, "new_value": new_dict})
    else:
        if old_dict != new_dict:
            diffs.append({"path": path, "type": "MODIFIED", "old_value": old_dict, "new_value": new_dict})
    return diffs

def get_active_policy_row(db: Session) -> PolicyVersion:
    """
    Returns the currently active policy version row.
    Consistent single source of truth used by upload, activate, /policy/active, and pipeline.
    Falls back to the most recently created version if none is ACTIVE.
    """
    active = db.query(PolicyVersion).filter(PolicyVersion.status == "ACTIVE").order_by(desc(PolicyVersion.created_at)).first()
    if not active:
        active = db.query(PolicyVersion).order_by(desc(PolicyVersion.created_at)).first()
    if not active:
        raise HTTPException(status_code=404, detail="No policy version found.")
    return active


def apply_parameter_overrides(rules: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync canonical operational parameters into the decision_rules AST so the engine
    actually evaluates the updated thresholds (not just the parameters dict).
    Canonical mapping:
      emergency_po_threshold -> rule 5.3 (EMERGENCY_PO) group_value_inr <= value
      rfq_threshold          -> rule 5.4 (SPOT_PO)    group_value_inr <  value
      rfp_threshold          -> rule 5.5 (RFQ)        group_value_inr <  value
                              -> rule 5.6 (RFP)       group_value_inr >= value
    """
    rules = copy.deepcopy(rules)
    for r in rules.get("decision_rules", []):
        rid = str(r.get("rule_id", ""))
        cond = r.get("condition", {})

        # Rule 5.3: Emergency PO threshold
        if rid == "5.3" and "emergency_po_threshold" in params:
            new_val = float(params["emergency_po_threshold"])
            if "AND" in cond:
                for c in cond["AND"]:
                    if c.get("field") == "requirement.group_value_inr":
                        c["value"] = new_val
            r["description"] = f"Emergency, value <= {int(new_val)}, bought from Active supplier in 365 days -> EMERGENCY_PO"

        # Rule 5.4: Spot PO threshold (rfq_threshold)
        if rid == "5.4" and "rfq_threshold" in params:
            new_val = float(params["rfq_threshold"])
            if "AND" in cond:
                for c in cond["AND"]:
                    if c.get("field") == "requirement.group_value_inr":
                        c["value"] = new_val
            r["description"] = f"Value below {int(new_val)}, bought from Active supplier in 365 days -> SPOT_PO"

        # Rule 5.5: RFQ upper threshold (rfp_threshold)
        if rid == "5.5" and "rfp_threshold" in params:
            new_val = float(params["rfp_threshold"])
            if cond.get("field") == "requirement.group_value_inr":
                cond["value"] = new_val
            r["description"] = f"Value below {int(new_val)} (including items never bought in 365d) -> RFQ, suggest 3 suppliers"

        # Rule 5.6: RFP lower threshold (rfp_threshold)
        if rid == "5.6" and "rfp_threshold" in params:
            new_val = float(params["rfp_threshold"])
            if cond.get("field") == "requirement.group_value_inr":
                cond["value"] = new_val
            r["description"] = f"Value {int(new_val)} or more -> RFP, suggest 5 suppliers"

    return rules


def parse_amendment_with_llm_or_heuristics(amendment_text: str, base_rules: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Parses amendment text and applies modifications onto base_rules.
    Uses Gemini Flash if configured, else applies robust heuristics.
    """
    import copy
    updated_rules = copy.deepcopy(base_rules)
    summary_notes = []

    # Check for Gemini LLM if key is configured
    if settings.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = f"""
You are an expert procurement policy parser for Corvo Engineering.
Given the current policy JSON and the following policy amendment text, produce ONLY a valid JSON object of the updated policy rules.
Do not include markdown fences, just pure JSON.

Current Policy:
{json.dumps(base_rules, indent=2)}

Amendment Text:
{amendment_text}
"""
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_PRIMARY,
                contents=prompt
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text)
            import json as json_mod
            parsed = json_mod.loads(raw_text)
            return parsed, f"Parsed via Gemini Flash ({settings.GEMINI_MODEL_PRIMARY}): {amendment_text[:100]}..."
        except Exception as e:
            summary_notes.append(f"LLM fallback used ({str(e)})")

    # Heuristic parsing for common amendments (thresholds, days, caps)
    params = updated_rules.get("parameters", {})
    text_lower = amendment_text.lower()

    # Helper: capture the target value for a keyword.
    # Looks at the text segment from the keyword up to the next threshold keyword
    # (or end of string) and returns the LAST number in that segment.
    # This correctly handles "from 500,000 to 750,000" -> 750,000.
    def _target_value(keyword: str) -> Optional[float]:
        idx = text_lower.find(keyword)
        if idx == -1:
            return None
        # Find the end of this keyword's segment (next threshold keyword or end)
        next_keywords = ["emergency", "rfq", "rfp", "anti-splitting", "split", "window"]
        end_idx = len(text_lower)
        for nk in next_keywords:
            if nk == keyword:
                continue
            nidx = text_lower.find(nk, idx + len(keyword))
            if nidx != -1 and nidx < end_idx:
                end_idx = nidx
        segment = text_lower[idx:end_idx]
        numbers = re.findall(r"(\d[\d,]+)", segment)
        if not numbers:
            return None
        return float(numbers[-1].replace(",", ""))

    # 1. Emergency threshold ("from 500,000 to 750,000" -> 750,000)
    val = _target_value("emergency")
    if val is not None:
        old_val = params.get("emergency_po_threshold")
        params["emergency_po_threshold"] = val
        summary_notes.append(f"Emergency PO threshold updated from {old_val} to {val}")

    # 2. RFQ threshold
    val = _target_value("rfq")
    if val is not None:
        old_val = params.get("rfq_threshold")
        params["rfq_threshold"] = val
        summary_notes.append(f"RFQ threshold updated from {old_val} to {val}")

    # 3. RFP threshold
    val = _target_value("rfp")
    if val is not None:
        old_val = params.get("rfp_threshold")
        params["rfp_threshold"] = val
        summary_notes.append(f"RFP threshold updated from {old_val} to {val}")

    # 4. Anti-splitting days
    m_split = re.search(r"(?:anti[- ]?splitting|split|window).*?(\d+)\s*days?", text_lower)
    if m_split:
        days = int(m_split.group(1))
        old_days = params.get("anti_splitting_window_days")
        params["anti_splitting_window_days"] = days
        summary_notes.append(f"Anti-splitting window days updated from {old_days} to {days}")

    updated_rules["parameters"] = params

    # Sync the canonical parameters into the decision_rules AST so the engine
    # evaluates the updated thresholds, not just the parameters dict.
    updated_rules = apply_parameter_overrides(updated_rules, params)

    note_str = "; ".join(summary_notes) if summary_notes else "General policy amendment ingested"
    return updated_rules, note_str

@router.get("/policy/active")
def get_active_policy(db: Session = Depends(get_db)):
    """
    Returns the currently active policy version and its complete rule tree.
    """
    active = db.query(PolicyVersion).filter(PolicyVersion.status == "ACTIVE").order_by(desc(PolicyVersion.created_at)).first()
    if not active:
        # Fallback to latest
        active = db.query(PolicyVersion).order_by(desc(PolicyVersion.created_at)).first()
        if not active:
            raise HTTPException(status_code=404, detail="No policy version found.")
            
    rules_def = copy.deepcopy(active.rules_definition or {})
    rules_def["policy_version"] = active.version_id

    return {
        "version_id": active.version_id,
        "name": active.name,
        "status": active.status,
        "document_ref": active.document_ref,
        "effective_date": active.effective_date.isoformat(),
        "created_at": active.created_at.isoformat(),
        "created_by": active.created_by,
        "rules_definition": rules_def
    }

@router.get("/policy/versions")
def list_policy_versions(db: Session = Depends(get_db)):
    """
    Lists all policy versions and approval history.
    """
    versions = db.query(PolicyVersion).order_by(desc(PolicyVersion.created_at)).all()
    results = []
    for v in versions:
        latest_approval = (
            db.query(PolicyApproval)
            .filter(PolicyApproval.version_id == v.version_id)
            .order_by(desc(PolicyApproval.performed_at))
            .first()
        )
        results.append({
            "version_id": v.version_id,
            "name": v.name,
            "status": v.status,
            "effective_date": v.effective_date.isoformat(),
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "document_ref": v.document_ref,
            "latest_action": latest_approval.action if latest_approval else None,
            "latest_actor": latest_approval.actor if latest_approval else None,
            "latest_action_at": latest_approval.performed_at.isoformat() if latest_approval else None,
            "change_summary": latest_approval.change_summary if latest_approval else None
        })
    return results

class PolicyParametersUpdateRequest(BaseModel):
    actor: str = Field(default="Policy Admin", description="Name of policy administrator")
    parameters: Dict[str, Any] = Field(..., description="Key-value pairs of operational rule parameters")

@router.get("/policy/{version_id}")
def get_policy_version_detail(version_id: str, db: Session = Depends(get_db)):
    """
    Returns full details, diff against parent, and approval log for a specific policy version.
    """
    ver = db.query(PolicyVersion).filter(PolicyVersion.version_id == version_id).first()
    if not ver:
        raise HTTPException(status_code=404, detail=f"Policy version '{version_id}' not found.")

    approvals = (
        db.query(PolicyApproval)
        .filter(PolicyApproval.version_id == version_id)
        .order_by(desc(PolicyApproval.performed_at))
        .all()
    )

    # Compute diff against parent if parent exists
    diff = []
    if ver.parent_version_id:
        parent = db.query(PolicyVersion).filter(PolicyVersion.version_id == ver.parent_version_id).first()
        if parent:
            diff = compute_json_diff(parent.rules_definition, ver.rules_definition)

    rules_def = copy.deepcopy(ver.rules_definition or {})
    rules_def["policy_version"] = ver.version_id

    return {
        "version_id": ver.version_id,
        "name": ver.name,
        "status": ver.status,
        "document_ref": ver.document_ref,
        "effective_date": ver.effective_date.isoformat(),
        "created_at": ver.created_at.isoformat(),
        "created_by": ver.created_by,
        "parent_version_id": ver.parent_version_id,
        "rules_definition": rules_def,
        "diff": diff,
        "approvals": [
            {
                "id": a.id,
                "action": a.action,
                "actor": a.actor,
                "performed_at": a.performed_at.isoformat(),
                "notes": a.notes,
                "change_summary": a.change_summary
            }
            for a in approvals
        ]
    }

@router.post("/policy/upload")
def upload_policy_amendment(
    payload: PolicyAmendmentJSONRequest,
    db: Session = Depends(get_db)
):
    """
    Upload an amendment (text or JSON) to create a new DRAFT policy version with automated diff generation.
    """
    logger.info(
        "Policy amendment upload started",
        extra={
            "version_id": payload.version_id,
            "name": payload.name,
            "created_by": payload.created_by,
            "has_amendment_text": bool(payload.amendment_text),
            "has_rules_definition": bool(payload.rules_definition),
        }
    )

    # Check if version_id already exists
    existing = db.query(PolicyVersion).filter(PolicyVersion.version_id == payload.version_id).first()
    if existing:
        logger.warning(
            "Policy amendment upload rejected: version_id already exists",
            extra={"version_id": payload.version_id}
        )
        raise HTTPException(status_code=400, detail=f"Policy version '{payload.version_id}' already exists.")

    active_policy = get_active_policy_row(db)
    base_rules = active_policy.rules_definition if active_policy else {}

    if payload.rules_definition:
        updated_rules = payload.rules_definition
        change_note = payload.amendment_text or "Direct rules definition JSON uploaded"
    elif payload.amendment_text:
        updated_rules, change_note = parse_amendment_with_llm_or_heuristics(payload.amendment_text, base_rules)
    else:
        logger.warning("Policy amendment upload rejected: neither rules_definition nor amendment_text provided")
        raise HTTPException(status_code=400, detail="Either rules_definition or amendment_text must be provided.")

    if isinstance(updated_rules, dict):
        updated_rules["policy_version"] = payload.version_id

    diff = compute_json_diff(base_rules, updated_rules)

    eff_date = datetime.strptime(payload.effective_date, "%Y-%m-%d").date()

    draft_version = PolicyVersion(
        version_id=payload.version_id,
        name=payload.name,
        document_ref=f"AMD-{payload.version_id}",
        effective_date=eff_date,
        status="DRAFT",
        rules_definition=updated_rules,
        parent_version_id=active_policy.version_id if active_policy else None,
        created_by=payload.created_by
    )
    db.add(draft_version)
    db.flush()  # Flush draft_version so version_id exists in policy_versions before approval references it

    approval = PolicyApproval(
        version_id=payload.version_id,
        action="SUBMITTED",
        actor=payload.created_by,
        notes=payload.amendment_text,
        change_summary=change_note
    )
    db.add(approval)
    db.commit()

    logger.info(
        "Policy amendment uploaded successfully",
        extra={
            "version_id": payload.version_id,
            "diff_count": len(diff),
            "change_summary": change_note,
        }
    )

    return {
        "status": "success",
        "message": f"Draft policy version {payload.version_id} created successfully.",
        "version_id": payload.version_id,
        "parent_version_id": active_policy.version_id if active_policy else None,
        "diff_count": len(diff),
        "diff": diff,
        "change_summary": change_note
    }

@router.post("/policy/{version_id}/approve")
def activate_policy_version(
    version_id: str,
    payload: PolicyApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve and dynamically activate a policy version.
    Marks previously active policy as SUPERSEDED.
    Changes take effect immediately without system restart.
    """
    target = db.query(PolicyVersion).filter(PolicyVersion.version_id == version_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Policy version '{version_id}' not found.")

    # Mark current active policies as SUPERSEDED
    current_active = db.query(PolicyVersion).filter(PolicyVersion.status == "ACTIVE").all()
    for p in current_active:
        if p.version_id != version_id:
            p.status = "SUPERSEDED"
            db.add(PolicyApproval(
                version_id=p.version_id,
                action="SUPERSEDED",
                actor=payload.actor,
                notes=f"Superseded by {version_id}"
            ))

    # Activate target
    target.status = "ACTIVE"
    if isinstance(target.rules_definition, dict):
        updated_def = copy.deepcopy(target.rules_definition)
        updated_def["policy_version"] = target.version_id
        target.rules_definition = updated_def

    db.add(PolicyApproval(
        version_id=version_id,
        action="ACTIVATED",
        actor=payload.actor,
        notes=payload.notes,
        change_summary=f"Activated by {payload.actor}"
    ))

    # Log audit entry
    db.add(AuditLog(
        event_type="POLICY_ACTIVATED",
        entity_type="PolicyVersion",
        entity_id=version_id,
        actor=payload.actor,
        payload={
            "activated_version": version_id,
            "superseded_versions": [p.version_id for p in current_active if p.version_id != version_id],
            "effective_date": target.effective_date.isoformat(),
            "notes": payload.notes
        }
    ))

    db.commit()

    return {
        "status": "success",
        "message": f"Policy version {version_id} is now ACTIVE and in effect dynamically.",
        "active_version": version_id,
        "activated_by": payload.actor,
        "effective_date": target.effective_date.isoformat()
    }

@router.put("/policy/{version_id}/parameters")
def update_policy_parameters(
    version_id: str,
    payload: PolicyParametersUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update operational rule parameters directly for a policy version.
    Allows Policy Admin with write access to modify parameters and operational thresholds.
    """
    target = db.query(PolicyVersion).filter(PolicyVersion.version_id == version_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Policy version '{version_id}' not found.")

    rules = copy.deepcopy(target.rules_definition or {})
    params = rules.get("parameters", {})
    for k, v in payload.parameters.items():
        try:
            params[k] = float(v) if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.', '', 1).isdigit()) else v
        except Exception:
            params[k] = v

    rules["parameters"] = params
    rules["policy_version"] = target.version_id

    # Synchronize operational thresholds into the decision rules AST (shared helper)
    rules = apply_parameter_overrides(rules, params)

    target.rules_definition = rules

    db.add(PolicyApproval(
        version_id=version_id,
        action="UPDATED",
        actor=payload.actor,
        notes=f"Operational rule parameters updated by {payload.actor}",
        change_summary=f"Updated parameters: {', '.join(payload.parameters.keys())}"
    ))
    db.commit()

    return {
        "status": "success",
        "message": f"Operational parameters for policy version '{version_id}' updated successfully.",
        "version_id": version_id,
        "parameters": params,
        "rules_definition": rules
    }
