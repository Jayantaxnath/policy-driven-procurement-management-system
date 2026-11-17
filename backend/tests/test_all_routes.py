"""
End-to-End API Routes Integration Test Suite.
Tests:
- Batch processing & CSV export
- Buyer workspace (list, get, approve, override with validation)
- Policy administration (active, versions, amendment upload, activation)
- Chat conversational PR intake (needs-info prompt & instant evaluation & submit)
"""
import sys
import os
import io
import pandas as pd
from datetime import datetime, date

# Ensure backend in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SyncSessionLocal
from app.api.routes import batch, buyers, policy, chat
from app.db.models import Requirement, PolicyVersion

def test_routes_directly():
    session = SyncSessionLocal()
    try:
        print("\n--- 1. Testing Policy Routes ---")
        # Ensure v5.0 is active
        session.query(PolicyVersion).filter(PolicyVersion.version_id == "v5.0").update({"status": "ACTIVE"})
        session.commit()

        # GET /api/policy/active
        active_pol = policy.get_active_policy(session)
        assert active_pol["version_id"] == "v5.0"
        print(f"[PASS] Active policy: {active_pol['version_id']} - {active_pol['name']}")

        # POST /api/policy/upload (Draft amendment)
        import uuid
        test_ver_id = f"v5.1-{uuid.uuid4().hex[:6]}"
        draft_req = policy.PolicyAmendmentJSONRequest(
            version_id=test_ver_id,
            name="Corvo Procurement Policy v5.1 (Test Amendment)",
            effective_date="2026-12-01",
            amendment_text="Increase emergency PO threshold from 500000 to 750000 INR and increase RFQ threshold to 300000 INR",
            created_by="Test Suite"
        )
        upload_res = policy.upload_policy_amendment(draft_req, session)
        assert upload_res["version_id"] == test_ver_id
        assert upload_res["diff_count"] > 0
        print(f"[PASS] Uploaded draft policy {upload_res['version_id']} with {upload_res['diff_count']} diffs: {upload_res['diff']}")

        # GET /api/policy/versions
        versions = policy.list_policy_versions(session)
        assert len(versions) >= 2
        print(f"[PASS] Total policy versions listed: {len(versions)}")

        # POST /api/policy/{version_id}/approve (Activate)
        app_req = policy.PolicyApprovalRequest(actor="Director of Sourcing", notes="Approved test policy")
        act_res = policy.activate_policy_version(test_ver_id, app_req, session)
        assert act_res["active_version"] == test_ver_id
        print(f"[PASS] Activated policy: {act_res['active_version']}")

        # Restore v5.0 to be ACTIVE for subsequent tests
        act_res2 = policy.activate_policy_version("v5.0", policy.PolicyApprovalRequest(actor="Test Suite", notes="Restoring v5.0"), session)
        assert act_res2["active_version"] == "v5.0"
        print("[PASS] Restored v5.0 to ACTIVE")

        print("\n--- 2. Testing Chat Conversational PR Intake ---")
        # Incomplete slot request -> should prompt for missing details
        msg_incomplete = chat.ChatMessageRequest(
            message="I need some ball bearings urgently"
        )
        intake_res1 = chat.chat_pr_intake(msg_incomplete, session)
        assert intake_res1["status"] == "NEEDS_INFO"
        print(f"[PASS] Missing slots prompt: {intake_res1['message']}")

        # Complete request with explicit item code, quantity, plant, and need by date
        msg_complete = chat.ChatMessageRequest(
            message="Please order 10 units of ITM-1001 for Pune plant by 2026-11-20, urgent"
        )
        intake_res2 = chat.chat_pr_intake(msg_complete, session)
        assert intake_res2["status"] == "EVALUATED"
        eval_data = intake_res2["evaluation"]
        assert eval_data["decision"] == "PO"
        assert eval_data["route"] == "CONTRACT_PO"
        assert eval_data["supplier_id"] == "S001"
        print(f"[PASS] Full chat evaluation: {eval_data['decision']} - {eval_data['route']} - Supplier: {eval_data['supplier_id']}")

        # POST /api/chat/submit-pr
        submit_req = chat.SubmitPRRequest(
            item_code="ITM-1001",
            description="Deep Groove Ball Bearing 6205",
            quantity=10,
            uom="NOS",
            plant="PUN1",
            need_by_date="2026-11-20",
            urgency="Normal",
            requester="Engineer Dave",
            department="Maintenance"
        )
        sub_res = chat.submit_chat_pr(submit_req, session)
        assert sub_res["status"] == "success"
        req_id = sub_res["requirement_id"]
        run_id = sub_res["run_id"]
        print(f"[PASS] Submitted PR: {sub_res['pr_no']}, Requirement ID: {req_id}")

        print("\n--- 3. Testing Buyer Workspace Routes ---")
        # GET /api/requirements
        req_list = buyers.list_requirements(run_id=run_id, limit=10, offset=0, db=session)
        assert req_list["total"] >= 1
        print(f"[PASS] Found {req_list['total']} requirement(s) for run {run_id}")

        # GET /api/requirements/{id}
        req_detail = buyers.get_requirement_detail(req_id, session)
        assert req_detail["requirement_id"] == req_id
        assert len(req_detail["clubbed_pr_lines"]) >= 1
        print(f"[PASS] Fetched requirement detail: {req_detail['resolved_item_code']}, route: {req_detail['route']}")

        # POST /api/requirements/{id}/approve
        app_buyer_req = buyers.ApproveRequest(buyer_id="Buyer Bob", notes="Confirmed standard contract rate")
        app_out = buyers.approve_requirement(req_id, app_buyer_req, session)
        assert app_out["status"] == "success"
        print(f"[PASS] Buyer approved requirement: {app_out['action']}")

        # POST /api/requirements/{id}/override
        override_req = buyers.OverrideRequest(
            buyer_id="Buyer Alice",
            override_reason="Strategic supplier allocation for plant testing",
            new_route="SPOT_PO",
            new_supplier_id="S024"
        )
        ovr_out = buyers.override_requirement(req_id, override_req, session)
        assert ovr_out["status"] == "success"
        assert ovr_out["new_route"] == "SPOT_PO"
        print(f"[PASS] Buyer override applied: new route {ovr_out['new_route']}, new supplier {ovr_out['new_supplier_id']}")

        # GET /api/buyers/actions
        actions = buyers.list_buyer_actions(limit=10, db=session)
        assert len(actions) >= 2
        print(f"[PASS] Buyer actions audit log count: {len(actions)}")

        print("\n--- 4. Testing CSV Export ---")
        csv_resp = batch.export_run_csv(run_id, session)
        assert csv_resp.status_code == 200
        assert csv_resp.media_type == "text/csv"
        assert f"filename=decisions_{run_id}.csv" in csv_resp.headers["Content-Disposition"]
        print(f"[PASS] Export run CSV returned status 200 with media_type {csv_resp.media_type} and valid Content-Disposition")

        print("\n=========================================")
        print("ALL API ROUTE INTEGRATION TESTS PASSED 100%!")
        print("=========================================\n")

    finally:
        session.close()

if __name__ == "__main__":
    test_routes_directly()
