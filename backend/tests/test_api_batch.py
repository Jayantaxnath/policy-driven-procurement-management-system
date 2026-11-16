"""
Test FastAPI Batch and Preferred Supplier Endpoints.
"""
import sys
import os
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.append('backend')
from fastapi.testclient import TestClient
from app.main import app

def test_endpoints():
    with TestClient(app) as client:
        # Health check
        res = client.get("/health")
        assert res.status_code == 200
        print("[PASS] /health returned 200 OK")

        # Preferred suppliers
        res_sup = client.get("/api/preferred-suppliers?as_of_date=2026-11-01")
        assert res_sup.status_code == 200
        lines = res_sup.text.strip().split("\n")
        print(f"[PASS] /api/preferred-suppliers returned {len(lines)} lines")

        # Process batch
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(root_dir, "Cantill_FullStack_Task_Kit", "pr_batches", "sample_pr_batch.csv")
        with open(csv_path, "rb") as f:
            res_batch = client.post("/api/process-batch", files={"file": ("sample_pr_batch.csv", f, "text/csv")})
        assert res_batch.status_code == 200
        data = res_batch.json()
        assert data["stats"]["total_lines"] == 186
        print(f"[PASS] /api/process-batch processed 186 lines. Run ID: {data['run_id']}")

if __name__ == "__main__":
    test_endpoints()
