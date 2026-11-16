import sys
from datetime import datetime, date
sys.path.append('backend')
from app.engine.clubber import club_pr_lines

# Test Worked Example 5 lines
we5_lines = [
    {
        "pr_no": "PR-26-00146", "pr_line": 1,
        "created_at": datetime(2026, 11, 2, 9, 40),
        "plant": "CHK1", "resolved_item_code": "ITM-1038",
        "quantity": 270, "need_by_date": date(2026, 11, 19), "urgency": "Normal"
    },
    {
        "pr_no": "PR-26-00144", "pr_line": 1,
        "created_at": datetime(2026, 11, 3, 9, 30),
        "plant": "CHK1", "resolved_item_code": "ITM-1038",
        "quantity": 190, "need_by_date": date(2026, 11, 15), "urgency": "Normal"
    },
    {
        "pr_no": "PR-26-00145", "pr_line": 1,
        "created_at": datetime(2026, 11, 5, 8, 40),
        "plant": "CHK1", "resolved_item_code": "ITM-1038",
        "quantity": 300, "need_by_date": date(2026, 11, 21), "urgency": "Normal"
    }
]

# Test Worked Example 6 lines
we6_lines = [
    {
        "pr_no": "PR-26-00106", "pr_line": 1,
        "created_at": datetime(2026, 11, 2, 12, 0),
        "plant": "PUN1", "resolved_item_code": "ITM-1044",
        "quantity": 7370, "need_by_date": date(2027, 2, 19), "urgency": "Normal"
    },
    {
        "pr_no": "PR-26-00103", "pr_line": 1,
        "created_at": datetime(2026, 11, 5, 8, 50),
        "plant": "CHK1", "resolved_item_code": "ITM-1044",
        "quantity": 6480, "need_by_date": date(2027, 3, 4), "urgency": "Normal"
    }
]

# Test invalid lines
invalid_lines = [
    {
        "pr_no": "PR-26-00172", "pr_line": 1,
        "created_at": datetime(2026, 11, 10, 12, 45),
        "plant": "PUN1", "resolved_item_code": "ITM-1020",
        "quantity": 0, "need_by_date": date(2026, 11, 18), "urgency": "Normal"
    },
    {
        "pr_no": "PR-26-00173", "pr_line": 1,
        "created_at": datetime(2026, 11, 18, 11, 30),
        "plant": "PUN2", "resolved_item_code": "ITM-1045",
        "quantity": 24, "need_by_date": date(2026, 12, 5), "urgency": "Normal"
    }
]

# Run clubbing
groups, unproc = club_pr_lines(we5_lines + we6_lines + invalid_lines)

print("Total groups created:", len(groups))
print("Total unproc created:", len(unproc))

# Verify WE 5: 3 lines clubbed into 1 group, total qty 760
we5_group = [g for g in groups if g.resolved_item_code == "ITM-1038"][0]
assert len(we5_group.lines) == 3, f"Expected 3 lines in WE5 group, got {len(we5_group.lines)}"
assert we5_group.total_quantity == 760, f"Expected 760 qty, got {we5_group.total_quantity}"
print("[OK] Worked Example 5: 3 PRs clubbed into 1 requirement of 760 LTR.")

# Verify WE 6: 2 separate groups for PUN1 and CHK1
we6_groups = [g for g in groups if g.resolved_item_code == "ITM-1044"]
assert len(we6_groups) == 2, f"Expected 2 groups in WE6, got {len(we6_groups)}"
print("[OK] Worked Example 6: Same item at different plants kept in separate requirements.")

# Verify invalid lines:
assert len(unproc) == 2, f"Expected 2 unproc, got {len(unproc)}"
assert any("Invalid quantity: 0" in u["reason"] for u in unproc)
assert any("PUN2" in u["reason"] for u in unproc)
print("[OK] Data traps properly caught and flagged NOT_PROCESSED.")

