"""
Tests for Chat Intake fixes - reproducing and verifying all 6 reported failures.
"""
import sys
import os
import json
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SyncSessionLocal
from app.db.models import PolicyVersion
from app.api.routes import chat
from app.engine.pipeline import load_system_state
from app.engine.item_matcher import ItemMatcher


def setup_module():
    """Seed database and set v5.0 active before tests."""
    session = SyncSessionLocal()
    session.query(PolicyVersion).filter(PolicyVersion.status == "ACTIVE").update({"status": "SUPERSEDED"})
    v50 = session.query(PolicyVersion).filter(PolicyVersion.version_id == "v5.0").first()
    if v50:
        v50.status = "ACTIVE"
    session.commit()
    session.close()


def test_case_1_markdown_in_item_extraction():
    """
    Case 1: "Emergency breakdown replacement ball bearings for Pune plant today"
    Expected: Item should be "ball bearings", not "breakdown replacement ball bearings plant"
    """
    session = SyncSessionLocal()
    try:
        state = load_system_state(session)
        matcher = ItemMatcher(state["items_list"])

        message = "Emergency breakdown replacement ball bearings for Pune plant today"
        slots = chat.extract_slots_heuristics(message, {})

        print(f"\nTest 1 - Input: '{message}'")
        print(f"  Extracted item_description: '{slots.get('item_description')}'")
        print(f"  Extracted plant: '{slots.get('plant')}'")
        print(f"  Extracted urgency: '{slots.get('urgency')}'")
        print(f"  Extracted need_by_date: '{slots.get('need_by_date')}'")

        assert slots.get("plant") == "PUN1", f"Expected plant PUN1, got {slots.get('plant')}"
        assert slots.get("urgency") == "Emergency", f"Expected urgency Emergency, got {slots.get('urgency')}"
        # Item should NOT contain "breakdown", "replacement", "plant", "today"
        item_desc = slots.get("item_description", "")
        assert "breakdown" not in item_desc.lower(), f"Item description should not contain 'breakdown': {item_desc}"
        assert "replacement" not in item_desc.lower(), f"Item description should not contain 'replacement': {item_desc}"
        assert "plant" not in item_desc.lower(), f"Item description should not contain 'plant': {item_desc}"
        assert "today" not in item_desc.lower(), f"Item description should not contain 'today': {item_desc}"
        assert "ball bearings" in item_desc.lower(), f"Item description should contain 'ball bearings': {item_desc}"
        assert slots.get("need_by_date") is not None, "need_by_date should be set for 'today'"
        print("  [PASS] Test 1 passed")
    finally:
        session.close()


def test_case_2_price_interpretation():
    """
    Case 2: "Estimated price is 50k" then "Total price is 50000"
    Expected: 
    - First message: estimated_unit_price should NOT be 50 (it's 50k = 50000)
    - Second message with total=50000: unit_price should be recalculated to 1000 for 50 units
    """
    session = SyncSessionLocal()
    try:
        state = load_system_state(session)
        matcher = ItemMatcher(state["items_list"])

        # Message 1: "Estimated price is 50k"
        slots = {}
        slots = chat.extract_slots_heuristics("Estimated price is 50k", slots)
        print(f"\nTest 2a - Input: 'Estimated price is 50k'")
        print(f"  estimated_unit_price: {slots.get('estimated_unit_price')}")
        print(f"  estimated_total_price: {slots.get('estimated_total_price')}")
        assert slots.get("estimated_total_price") == 50000, f"Expected estimated_total_price=50000, got {slots.get('estimated_total_price')}"
        assert slots.get("estimated_unit_price") is None, f"estimated_unit_price should be None for total price, got {slots.get('estimated_unit_price')}"
        print("  [PASS] Test 2a passed - 50k correctly treated as total price")

        # Message 2: "Total price is 50000" with quantity 50
        slots["quantity"] = 50
        slots = chat.extract_slots_heuristics("Total price is 50000", slots)
        print(f"\nTest 2b - Input: 'Total price is 50000' with quantity=50")
        print(f"  estimated_total_price: {slots.get('estimated_total_price')}")
        print(f"  estimated_unit_price: {slots.get('estimated_unit_price')}")
        assert slots.get("estimated_total_price") == 50000, f"Expected estimated_total_price=50000, got {slots.get('estimated_total_price')}"
        assert slots.get("estimated_unit_price") == 1000.0, f"Expected estimated_unit_price=1000.0, got {slots.get('estimated_unit_price')}"
        print("  [PASS] Test 2b passed - total price correctly converted to unit price")
    finally:
        session.close()


def test_case_3_date_in_item_name():
    """
    Case 3: "I need 20 ball bearings for Pune plant by Friday"
    Expected: Item should be "ball bearings", not "ball bearings plant by Friday"
    Delivery date should be Friday
    """
    session = SyncSessionLocal()
    try:
        slots = chat.extract_slots_heuristics("I need 20 ball bearings for Pune plant by Friday", {})
        print(f"\nTest 3 - Input: 'I need 20 ball bearings for Pune plant by Friday'")
        print(f"  Extracted item_description: '{slots.get('item_description')}'")
        print(f"  Extracted quantity: '{slots.get('quantity')}'")
        print(f"  Extracted plant: '{slots.get('plant')}'")
        print(f"  Extracted need_by_date: '{slots.get('need_by_date')}'")

        item_desc = slots.get("item_description", "")
        assert "plant" not in item_desc.lower(), f"Item description should not contain 'plant': {item_desc}"
        assert "friday" not in item_desc.lower(), f"Item description should not contain 'friday': {item_desc}"
        assert "ball bearings" in item_desc.lower(), f"Item description should contain 'ball bearings': {item_desc}"
        assert slots.get("quantity") == 20, f"Expected quantity 20, got {slots.get('quantity')}"
        assert slots.get("plant") == "PUN1", f"Expected plant PUN1, got {slots.get('plant')}"
        assert slots.get("need_by_date") is not None, f"need_by_date should be set for Friday"
        print("  [PASS] Test 3 passed")
    finally:
        session.close()


def test_case_4_plant_selection():
    """
    Case 4: "pun1" should be recognized as PUN1
    """
    session = SyncSessionLocal()
    try:
        # Test lowercase pun1
        slots = chat.extract_slots_heuristics("pun1", {})
        print(f"\nTest 4a - Input: 'pun1'")
        print(f"  Extracted plant: '{slots.get('plant')}'")
        assert slots.get("plant") == "PUN1", f"Expected PUN1, got {slots.get('plant')}"

        # Test uppercase PUN1
        slots = chat.extract_slots_heuristics("PUN1", {})
        print(f"\nTest 4b - Input: 'PUN1'")
        print(f"  Extracted plant: '{slots.get('plant')}'")
        assert slots.get("plant") == "PUN1", f"Expected PUN1, got {slots.get('plant')}"
        print("  [PASS] Test 4 passed")
    finally:
        session.close()


def test_case_5_new_item_extraction():
    """
    Case 5: "Request custom CNC tooling quote"
    Expected: Item should be "custom CNC tooling", not "Request custom CNC tooling quote"
    """
    session = SyncSessionLocal()
    try:
        slots = chat.extract_slots_heuristics("Request custom CNC tooling quote", {})
        print(f"\nTest 5 - Input: 'Request custom CNC tooling quote'")
        print(f"  Extracted item_description: '{slots.get('item_description')}'")

        item_desc = slots.get("item_description", "")
        assert "request" not in item_desc.lower(), f"Item description should not contain 'request': {item_desc}"
        assert "custom" not in item_desc.lower() or item_desc.lower() == "custom cnc tooling", \
            f"Item description should be 'custom CNC tooling', got: {item_desc}"
        assert "quote" not in item_desc.lower(), f"Item description should not contain 'quote': {item_desc}"
        assert "custom cnc tooling" in item_desc.lower(), f"Item description should contain 'custom CNC tooling': {item_desc}"
        print("  [PASS] Test 5 passed")
    finally:
        session.close()


def test_case_6_no_premature_decision():
    """
    Case 6: Missing slots should NOT trigger evaluation
    """
    session = SyncSessionLocal()
    try:
        # Missing quantity
        slots = {}
        slots = chat.extract_slots_heuristics("I need ball bearings for Pune plant", slots)
        print(f"\nTest 6a - Input: 'I need ball bearings for Pune plant' (missing quantity)")
        print(f"  Slots: {slots}")
        assert slots.get("quantity") is None or float(slots.get("quantity", 0)) <= 0, \
            f"Quantity should be missing/invalid, got {slots.get('quantity')}"

        # Missing plant
        slots = {}
        slots = chat.extract_slots_heuristics("I need 20 ball bearings", slots)
        print(f"\nTest 6b - Input: 'I need 20 ball bearings' (missing plant)")
        print(f"  Slots: {slots}")
        assert slots.get("plant") is None or slots.get("plant") not in ["PUN1", "CHK1"], \
            f"Plant should be missing, got {slots.get('plant')}"

        print("  [PASS] Test 6 passed - missing slots correctly identified")
    finally:
        session.close()


if __name__ == "__main__":
    setup_module()
    test_case_1_markdown_in_item_extraction()
    test_case_2_price_interpretation()
    test_case_3_date_in_item_name()
    test_case_4_plant_selection()
    test_case_5_new_item_extraction()
    test_case_6_no_premature_decision()
    print("\n" + "="*60)
    print("ALL 6 CHAT INTAKE TEST CASES PASSED!")
    print("="*60)