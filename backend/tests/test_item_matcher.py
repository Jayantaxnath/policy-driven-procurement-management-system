import sys
sys.path.append('backend')
from app.db.database import SyncSessionLocal
from app.db.models import ItemMaster
from app.engine.item_matcher import ItemMatcher

session = SyncSessionLocal()
items = [{"item_code": i.item_code, "description": i.description, "uom": i.uom, "category": i.category, "item_type": i.item_type, "standard_price": i.standard_price} for i in session.query(ItemMaster).all()]
matcher = ItemMatcher(items)

test_cases = [
    ("brg 6308 ZZ for maintenance", "ITM-1022"),
    ("v-belt b-54", "ITM-1024"),
    ("mig wire er70s-6 1.2mm", "ITM-1016"),
    ("welding rod e6013 3.15mm", "ITM-1015"),
    ("nitrile coated gloves - urgent", "ITM-1048"),
    ("pneu cylinder 50x100", "ITM-1036"),
    ('monitor 24"', "ITM-1057"),
    ("eot crane 5 ton", "ITM-1071"),
    ("hyd hose 1/2 inch 2 wire", "ITM-1035"),
    ("Drinking water purifier 50 LPH", "NEW"),
    ("Ultrasonic thickness gauge", "NEW")
]

all_passed = True
for query, expected in test_cases:
    code, score, _ = matcher.resolve(None, query)
    passed = (code == expected)
    if not passed:
        all_passed = False
    status = "OK" if passed else f"FAIL (got {code})"
    print(f"[{status}] {query!r:35} -> {code} ({score:.2f}) expected {expected}")

print("Result:", "ALL PASSED" if all_passed else "SOME FAILED")

