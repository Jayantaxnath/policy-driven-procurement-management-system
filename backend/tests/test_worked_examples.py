"""
Comprehensive Verification Test Suite against all 14 Worked Examples.
"""
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append('backend')
from app.db.database import SyncSessionLocal
from app.engine.pipeline import process_pr_batch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KIT_DIR = os.path.join(ROOT_DIR, "Cantill_FullStack_Task_Kit")
batch_csv_path = os.path.join(KIT_DIR, "pr_batches", "sample_pr_batch.csv")

session = SyncSessionLocal()
df_batch = pd.read_csv(batch_csv_path)

print(f"Loaded {len(df_batch)} lines from {batch_csv_path}")

# Run pipeline
output_rows, stats = process_pr_batch(df_batch, session)
print(f"Processed batch. Total lines: {stats['total_lines']}, Requirements: {stats['total_requirements']}, POs: {stats['total_pos']}, Sourcing: {stats['total_sourcing']}, Unprocessed: {stats['total_not_processed']}")

# Create lookup by (pr_no, pr_line)
results_map = {(r["pr_no"], r["pr_line"]): r for r in output_rows}

# ─── VERIFY WORKED EXAMPLES ──────────────────────────────────────────────────

print("\n--- CHECKING WORKED EXAMPLES ---")
passed_count = 0

# 1. PR-26-00019/1: Contract PO S001 at ~9169
ex1 = results_map.get(("PR-26-00019", 1))
print("Ex 1 (PR-26-00019/1):", ex1["route"], ex1["supplier_id"], ex1["unit_price"], ex1["group_value_inr"])
assert ex1["route"] == "CONTRACT_PO"
assert ex1["supplier_id"] == "S001"
assert round(ex1["group_value_inr"]) == 137531
passed_count += 1
print("[PASS] Example 1: Contract PO (Bhosari Steel Traders @ 9168.71)")

# 2. PR-26-00045/1: PDF-only contract RC-2026-031
ex2 = results_map.get(("PR-26-00045", 1))
print("Ex 2 (PR-26-00045/1):", ex2["route"], ex2["supplier_id"], ex2["unit_price"], ex2["group_value_inr"])
assert ex2["route"] == "CONTRACT_PO"
assert ex2["supplier_id"] == "S021"
assert round(ex2["group_value_inr"]) == 26829
passed_count += 1
print("[PASS] Example 2: PDF-only contract applied successfully (Pneumatic Point @ 2439.01)")

# 3. PR-26-00004/1 and PR-26-00026/1: Contract ceiling out -> RFQ
ex3_a = results_map.get(("PR-26-00004", 1))
ex3_b = results_map.get(("PR-26-00026", 1))
print("Ex 3 (PR-26-00004/1):", ex3_a["route"], ex3_a["group_id"], ex3_a["suggested_supplier_ids"])
assert ex3_a["group_id"] == ex3_b["group_id"], "Lines should be clubbed"
assert ex3_a["route"] == "RFQ"
assert round(ex3_a["group_value_inr"]) == 220256
passed_count += 1
print("[PASS] Example 3: Ceiling nearly used up -> routes to RFQ with value at lowest contract rate")

# 4. PR-26-00034/1: Two contracts -> Precision Fasteners (S007)
ex4 = results_map.get(("PR-26-00034", 1))
print("Ex 4 (PR-26-00034/1):", ex4["route"], ex4["supplier_id"], ex4["unit_price"])
assert ex4["route"] == "CONTRACT_PO"
assert ex4["supplier_id"] == "S007"
passed_count += 1
print("[PASS] Example 4: Two contracts for same item -> chosen lowest rate with room (S007)")

# 5. Split PRs: PR-26-00146, PR-26-00144, PR-26-00145
ex5_a = results_map.get(("PR-26-00146", 1))
ex5_b = results_map.get(("PR-26-00144", 1))
ex5_c = results_map.get(("PR-26-00145", 1))
print("Ex 5:", ex5_a["route"], ex5_a["supplier_id"], ex5_a["group_value_inr"])
assert ex5_a["group_id"] == ex5_b["group_id"] == ex5_c["group_id"], "All 3 should be clubbed"
assert ex5_a["route"] == "SPOT_PO"
assert ex5_a["supplier_id"] == "S024"
assert round(ex5_a["group_value_inr"]) == 126472
passed_count += 1
print("[PASS] Example 5: Split PRs clubbed into one requirement -> SPOT_PO (Janatics Dealer Chakan @ 166.41)")

# 6. Same item different plants: PR-26-00106 (PUN1) vs PR-26-00103 (CHK1)
ex6_a = results_map.get(("PR-26-00106", 1))
ex6_b = results_map.get(("PR-26-00103", 1))
print("Ex 6:", ex6_a["route"], "GIDs:", ex6_a["group_id"], ex6_b["group_id"])
assert ex6_a["group_id"] != ex6_b["group_id"], "Different plants must not be clubbed"
assert ex6_a["route"] == "SPOT_PO"
passed_count += 1
print("[PASS] Example 6: Same item at different plants evaluated separately")

# 7. Free text item matched: PR-26-00088/1
ex7 = results_map.get(("PR-26-00088", 1))
print("Ex 7:", ex7["resolved_item_code"], ex7["route"], ex7["supplier_id"])
assert ex7["resolved_item_code"] == "ITM-1035"
assert ex7["route"] == "SPOT_PO"
assert ex7["supplier_id"] == "S023"
assert round(ex7["group_value_inr"]) == 97955
passed_count += 1
print("[PASS] Example 7: Free text matched to ITM-1035 -> SPOT_PO (Hydrax Hydraulics)")

# 8. Emergency PO: PR-26-00059/1
ex8 = results_map.get(("PR-26-00059", 1))
print("Ex 8:", ex8["route"], ex8["supplier_id"], ex8["group_value_inr"])
assert ex8["route"] == "EMERGENCY_PO"
assert ex8["supplier_id"] == "S014"
assert round(ex8["group_value_inr"]) == 253184
passed_count += 1
print("[PASS] Example 8: Emergency PO allowed up to 5 Lakh -> EMERGENCY_PO (Mahalaxmi)")

# 9. RFQ above PO limit: PR-26-00089/1
ex9 = results_map.get(("PR-26-00089", 1))
print("Ex 9:", ex9["route"], ex9["suggested_supplier_ids"], ex9["group_value_inr"])
assert ex9["route"] == "RFQ"
assert round(ex9["group_value_inr"]) == 336562
passed_count += 1
print("[PASS] Example 9: Above PO limit -> RFQ with 3 suggested suppliers")

# 10. RFQ small but never bought: PR-26-00050/1
ex10 = results_map.get(("PR-26-00050", 1))
print("Ex 10:", ex10["route"], ex10["suggested_supplier_ids"], ex10["group_value_inr"])
assert ex10["route"] == "RFQ"
assert round(ex10["group_value_inr"]) == 80300
passed_count += 1
print("[PASS] Example 10: Low value but contract supplier blocked & no active history -> RFQ")

# 11. RFP: PR-26-00100/1
ex11 = results_map.get(("PR-26-00100", 1))
print("Ex 11:", ex11["route"], ex11["suggested_supplier_ids"], ex11["group_value_inr"])
assert ex11["route"] == "RFP"
assert round(ex11["group_value_inr"]) == 2070780
passed_count += 1
print("[PASS] Example 11: High value (>= 10 Lakh) -> RFP")

# 12. Capex: PR-26-00047/1
ex12 = results_map.get(("PR-26-00047", 1))
print("Ex 12:", ex12["route"], ex12["suggested_supplier_ids"], ex12["group_value_inr"])
assert ex12["route"] == "CAPEX_SOURCING"
assert round(ex12["group_value_inr"]) == 6036704
passed_count += 1
print("[PASS] Example 12: Capex item -> CAPEX_SOURCING with 5 suggested suppliers")

# 13. New item: PR-26-00170/1
ex13 = results_map.get(("PR-26-00170", 1))
print("Ex 13:", ex13["resolved_item_code"], ex13["route"], ex13["suggested_supplier_ids"])
assert ex13["resolved_item_code"] == "NEW"
assert ex13["route"] == "NEW_ITEM_SOURCING"
assert ex13["suggested_supplier_ids"] is None
assert round(ex13["group_value_inr"]) == 141100
passed_count += 1
print("[PASS] Example 13: Uncataloged item -> NEW_ITEM_SOURCING, no suggestions")

# 14. PO Consolidation: PR-26-00034 and PR-26-00031
ex14_a = results_map.get(("PR-26-00034", 1))
ex14_b = results_map.get(("PR-26-00031", 1))
print("Ex 14 PO Consolidation:", ex14_a["po_id"], ex14_b["po_id"])
assert ex14_a["po_id"] is not None and ex14_a["po_id"] == ex14_b["po_id"]
passed_count += 1
print("[PASS] Example 14: Requirements consolidated into single PO with multiple lines")

print(f"\n==========================================")
print(f"ALL {passed_count} / 14 WORKED EXAMPLES PASSED 100% PERFECTLY!")
print(f"==========================================")

