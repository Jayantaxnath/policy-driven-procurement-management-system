import sys
from datetime import date, timedelta
sys.path.append('backend')
from app.db.database import SyncSessionLocal
from app.db.models import POHistory, ContractHeader, ContractLine, SupplierMaster

session = SyncSessionLocal()

def get_preferred_suppliers(item_code, as_of_date):
    start_548 = as_of_date - timedelta(days=548)
    active_sups = {s.supplier_id: s for s in session.query(SupplierMaster).filter_by(status='Active').all()}
    
    pos = session.query(POHistory).filter(
        POHistory.item_code == item_code,
        POHistory.po_date >= start_548,
        POHistory.po_date < as_of_date
    ).all()
    
    sup_pos = {}
    for p in pos:
        if p.supplier_id in active_sups:
            sup_pos.setdefault(p.supplier_id, []).append(p)
            
    c_lines = session.query(ContractLine).filter(ContractLine.item_code == item_code).all()
    sup_contracts = {}
    for cl in c_lines:
        ch = session.get(ContractHeader, cl.contract_id)
        if ch and ch.start_date <= as_of_date and ch.supplier_id in active_sups:
            sup_contracts.setdefault(ch.supplier_id, []).append((ch, cl))
            
    candidate_ids = set(sup_pos.keys()) | set(sup_contracts.keys())
    
    scored = []
    for sid in candidate_ids:
        sup = active_sups[sid]
        po_list = sup_pos.get(sid, [])
        po_count = len(po_list)
        
        recency = 0.0
        latest_po_price = None
        if po_list:
            sorted_pos = sorted(po_list, key=lambda x: x.po_date, reverse=True)
            days_ago = (as_of_date - sorted_pos[0].po_date).days
            if days_ago <= 90:
                recency = 1.0
            elif days_ago <= 365:
                recency = 0.5
            else:
                recency = 0.0
            latest_po_price = sorted_pos[0].unit_price
            
        has_contract = 1.0 if sid in sup_contracts else 0.0
        
        if latest_po_price is not None:
            ref_price = latest_po_price
        elif sid in sup_contracts:
            sorted_c = sorted(sup_contracts[sid], key=lambda x: x[0].start_date, reverse=True)
            ref_price = sorted_c[0][1].rate
        else:
            ref_price = 0.0
            
        ot_norm = sup.on_time_pct / 100.0
        q_norm = sup.quality_rating / 5.0
        
        score = (
            0.25 * min(po_count / 5.0, 1.0) +
            0.25 * recency +
            0.20 * has_contract +
            0.15 * ot_norm +
            0.15 * q_norm
        )
        scored.append({
            'supplier_id': sid,
            'name': sup.name,
            'pos': po_count,
            'recency': recency,
            'contract': has_contract,
            'on_time': sup.on_time_pct,
            'quality': sup.quality_rating,
            'score': score,
            'ref_price': ref_price
        })
        
    scored.sort(key=lambda x: (x['score'], x['on_time'], x['quality']), reverse=True)
    return scored

# Check against Worked Examples Page 5:
# ITM-1048: Rank 1 S029, Rank 2 S030 (S031 excluded because Inactive)
res_1048 = get_preferred_suppliers('ITM-1048', date(2026, 11, 1))
print("ITM-1048 ranks:", [r['supplier_id'] for r in res_1048])
assert res_1048[0]['supplier_id'] == 'S029'
assert res_1048[1]['supplier_id'] == 'S030'
assert 'S031' not in [r['supplier_id'] for r in res_1048]
print("[OK] ITM-1048 ranking matches Worked Examples page 5 exactly!")

# ITM-1036: Rank 1 S023, Rank 2 S022, Rank 3 S024
res_1036 = get_preferred_suppliers('ITM-1036', date(2026, 11, 1))
print("ITM-1036 ranks:", [r['supplier_id'] for r in res_1036])
assert res_1036[0]['supplier_id'] == 'S023'
assert res_1036[1]['supplier_id'] == 'S022'
assert res_1036[2]['supplier_id'] == 'S024'
print("[OK] ITM-1036 ranking matches Worked Examples page 5 exactly!")

# ITM-1016: Rank 1 S009, Rank 2 S010
res_1016 = get_preferred_suppliers('ITM-1016', date(2026, 11, 1))
print("ITM-1016 ranks:", [r['supplier_id'] for r in res_1016])
assert res_1016[0]['supplier_id'] == 'S009'
assert res_1016[1]['supplier_id'] == 'S010'
print("[OK] ITM-1016 ranking matches Worked Examples page 5 exactly!")

