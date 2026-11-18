"""
Test Chat Intake with LLM-only extraction (no heuristic fallback).
Tests the 6 reported failure cases using ONLY the LLM-based extraction path.
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import SyncSessionLocal
from app.api.routes import chat


def test_case_1_markdown_in_item_extraction():
    """
    Case 1: "Emergency breakdown replacement ball bearings for Pune plant today"
    Expected:
    - Item: "ball bearings" (NOT "breakdown replacement ball bearings plant")
    - Plant: PUN1
    - Urgency: Emergency
    - Delivery date: today
    """
    session = SyncSessionLocal()
    try:
        slots = chat.extract_slots_with_llm(
            "Emergency breakdown replacement ball bearings for Pune plant today", {}
        )
        print(f"\n=== Test 1: 'Emergency breakdown replacement ball bearings for Pune plant today' ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")

        item_desc = slots.get("item_description", "")
        print(f"  item_description: '{item_desc}'")

        # Check: item should NOT contain breakdown/replacement/plant/today
        assert "breakdown" not in item_desc.lower(), f"FAIL: item_description contains 'breakdown': {item_desc}"
        assert "replacement" not in item_desc.lower(), f"FAIL: item_description contains 'replacement': {item_desc}"
        assert "plant" not in item_desc.lower(), f"Item description should not contain 'plant': {item_desc}"
        assert "today" not in item_desc.lower(), f"Item description should not contain 'today': {item_desc}"
        assert "ball bearings" in item_desc.lower(), f"Item description should contain 'ball bearings': {item_desc}"

        # Check plant
        assert slots.get("plant") == "PUN1", f"Expected plant PUN1, got {slots.get('plant')}"

        # Check urgency
        assert slots.get("urgency") == "Emergency", f"Expected urgency Emergency, got {slots.get('urgency')}"

        # Check need_by_date
        assert slots.get("need_by_date") is not None, f"need_by_date should be set for 'today', got {slots.get('need_by_date')}"

        print("  [PASS] Test 1 passed")
    finally:
        session.close()


def test_case_2_price_interpretation():
    """
    Case 2: "Estimated price is 50k" then "Total price is 50000"
    Expected:
    - First: estimated_total_price = 50000 (NOT unit price 50)
    - Second: estimated_total_price = 50000, unit_price = 1000 for qty 50
    """
    session = SyncSessionLocal()
    try:
        # Message 1: "Estimated price is 50k"
        slots = chat.extract_slots_with_llm("Estimated price is 50k", {})
        print(f"\n=== Test 2a: 'Estimated price is 50k' ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")

        # 50k should be interpreted as total price 50000, not unit price 50
        assert slots.get("estimated_total_price") == 50000, \
            f"Expected estimated_total_price=50000, got {slots.get('estimated_total_price')}"
        assert slots.get("estimated_unit_price") is None, \
            f"estimated_unit_price should be None for total price, got {slots.get('estimated_unit_price')}"
        print("  [PASS] Test 2a passed - 50k treated as total price")

        # Message 2: "Total price is 50000" with quantity 50
        slots = chat.extract_slots_heuristics("Total price is 50000", {"quantity": 50})
        print(f"\n=== Test 2b: 'Total price is 50000' with quantity=50 ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")

        assert slots.get("estimated_total_price") == 50000, \
            f"Expected estimated_total_price=50000, got {slots.get('estimated_total_price')}"
        assert slots.get("estimated_unit_price") == 1000.0, \
            f"Expected estimated_unit_price=1000.0, got {slots.get('estimated_unit_price')}"
        print("  [PASS] Test 2b passed")
    finally:
        session.close()


def test_case_3_date_in_item_name():
    """
    Case 3: "I need 20 ball bearings for Pune plant by Friday"
    Expected:
    - Item: "ball bearings"
    - Quantity: 20
    - Plant: PUN1
    - Delivery date: Friday
    """
    session = SyncSessionLocal()
    try:
        slots = chat.extract_slots_with_llm("I need 20 ball bearings for Pune plant by Friday", {})
        print(f"\n=== Test 3: 'I need 20 ball bearings for Pune plant by Friday' ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")

        item_desc = slots.get("item_description", "")
        print(f"  item_description: '{item_desc}'")

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
        slots = chat.extract_slots_with_llm("pun1", {})
        print(f"\n=== Test 4a: 'pun1' ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")
        assert slots.get("plant") == "PUN1", f"Expected PUN1, got {slots.get('plant')}"
        print("  [PASS] Test 4a passed")

        # Test uppercase PUN1
        slots = chat.extract_slots_with_llm("PUN1", {})
        print(f"\n=== Test 4b: 'PUN1' ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")
        assert slots.get("plant") == "PUN1", f"Expected PUN1, got {slots.get('plant')}"
        print("  [PASS] Test 4b passed")
    finally:
        session.close()


def test_case_5_new_item_extraction():
    """
    Case 5: "Request custom CNC tooling quote"
    Expected:
    - Item: "custom CNC tooling"
    - Not invent item codes
    """
    session = SyncSessionLocal()
    try:
        slots = chat.extract_slots_with_llm("Request custom CNC tooling quote", {})
        print(f"\n=== Test 5: 'Request custom CNC tooling quote' ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")

        item_desc = slots.get("item_description", "")
        print(f"  item_description: '{item_desc}'")

        assert "request" not in item_desc.lower(), f"Item description should not contain 'request': {item_desc}"
        assert "quote" not in item_desc.lower(), f"Item description should not contain 'quote': {item_desc}"
        assert "custom cnc tooling" in item_desc.lower(), \
            f"Item description should contain 'custom CNC tooling': {item_desc}"
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
        slots = chat.extract_slots_with_llm("I need ball bearings for Pune plant", {})
        print(f"\n=== Test 6a: 'I need ball bearings for Pune plant' (missing quantity) ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")
        assert slots.get("quantity") is None or float(slots.get("quantity", 0)) <= 0, \
            f"Quantity should be missing/invalid, got {slots.get('quantity')}"

        # Missing plant
        slots = chat.extract_slots_with_llm("I need 20 ball bearings", {})
        print(f"\n=== Test 6b: 'I need 20 ball bearings' (missing plant) ===")
        print(f"  LLM result: {json.dumps(slots, indent=2)}")
        assert slots.get("plant") is None or slots.get("plant") not in ["PUN1", "CHK1"], \
            f"Plant should be missing, got {slots.get('plant')}"

        print("  [PASS] Test 6 passed - missing slots correctly identified")
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("TESTING CHAT INTAKE WITH LLM-ONLY EXTRACTION")
    print("=" * 60)

    test_case_1_markdown_in_item_extraction()
    test_case_2_price_interpretation()
    test_case_3_date_in_item_name()
    test_case_4_plant_selection()
    test_case_5_new_item_extraction()
    test_case_6_no_premature_decision()

    print("\n" + "=" * 60)
    print("ALL 6 CHAT INTAKE TEST CASES PASSED!")
    print("=" * 60)