"""
Seed master data into the database from Cantill_FullStack_Task_Kit and PDF contracts.
"""
import os
import json
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.database import SyncSessionLocal, Base, sync_engine
from app.db.models import (
    Plant, ItemMaster, SupplierMaster, POHistory,
    ContractHeader, ContractLine, PolicyVersion
)
from app.engine.pdf_parser import parse_contract_pdf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KIT_DIR = os.path.join(os.path.dirname(BASE_DIR), "Cantill_FullStack_Task_Kit")
if not os.path.exists(KIT_DIR):
    KIT_DIR = os.path.join(BASE_DIR, "Cantill_FullStack_Task_Kit")

def seed_all():
    print(f"Seeding database using data from: {KIT_DIR}")
    Base.metadata.create_all(sync_engine)
    session: Session = SyncSessionLocal()
    
    try:
        # 1. Plants
        plants_path = os.path.join(KIT_DIR, "master_data", "plants.csv")
        if os.path.exists(plants_path):
            df_plants = pd.read_csv(plants_path)
            for _, row in df_plants.iterrows():
                p = session.get(Plant, str(row["plant"]).strip())
                if not p:
                    p = Plant(plant_code=str(row["plant"]).strip(), name=str(row["name"]).strip())
                    session.add(p)
            session.commit()
            print(f"Seeded {len(df_plants)} plants.")

        # 2. Item Master
        items_path = os.path.join(KIT_DIR, "master_data", "item_master.csv")
        if os.path.exists(items_path):
            df_items = pd.read_csv(items_path)
            for _, row in df_items.iterrows():
                item_code = str(row["item_code"]).strip()
                item = session.get(ItemMaster, item_code)
                if not item:
                    item = ItemMaster(
                        item_code=item_code,
                        description=str(row["description"]).strip(),
                        uom=str(row["uom"]).strip(),
                        category=str(row["category"]).strip(),
                        item_type=str(row["item_type"]).strip(),
                        standard_price=float(row["standard_price"])
                    )
                    session.add(item)
            session.commit()
            print(f"Seeded {len(df_items)} items.")

        # 3. Supplier Master
        sup_path = os.path.join(KIT_DIR, "master_data", "supplier_master.csv")
        if os.path.exists(sup_path):
            df_sup = pd.read_csv(sup_path)
            for _, row in df_sup.iterrows():
                s_id = str(row["supplier_id"]).strip()
                sup = session.get(SupplierMaster, s_id)
                cats = [c.strip() for c in str(row["categories"]).split(";") if c.strip()]
                if not sup:
                    sup = SupplierMaster(
                        supplier_id=s_id,
                        name=str(row["name"]).strip(),
                        city=str(row["city"]).strip(),
                        categories=cats,
                        status=str(row["status"]).strip(),
                        on_time_pct=float(row["on_time_pct"]),
                        quality_rating=float(row["quality_rating"])
                    )
                    session.add(sup)
                else:
                    sup.categories = cats
                    sup.status = str(row["status"]).strip()
                    sup.on_time_pct = float(row["on_time_pct"])
                    sup.quality_rating = float(row["quality_rating"])
            session.commit()
            print(f"Seeded {len(df_sup)} suppliers.")

        # 4. PO History
        po_path = os.path.join(KIT_DIR, "master_data", "po_history.csv")
        if os.path.exists(po_path):
            df_po = pd.read_csv(po_path)
            existing_pos = set(r[0] for r in session.query(POHistory.po_number).all())
            new_pos = []
            for _, row in df_po.iterrows():
                po_num = int(row["po_number"])
                if po_num not in existing_pos:
                    po_date = datetime.strptime(str(row["po_date"]).strip(), "%Y-%m-%d").date()
                    on_time = str(row["delivered_on_time"]).strip().lower() in ("true", "1", "t", "yes")
                    new_pos.append(POHistory(
                        po_number=po_num,
                        po_date=po_date,
                        supplier_id=str(row["supplier_id"]).strip(),
                        item_code=str(row["item_code"]).strip(),
                        quantity=float(row["quantity"]),
                        uom=str(row["uom"]).strip(),
                        unit_price=float(row["unit_price"]),
                        plant=str(row["plant"]).strip(),
                        delivered_on_time=on_time
                    ))
            if new_pos:
                session.add_all(new_pos)
                session.commit()
            print(f"Seeded {len(df_po)} PO history records.")

        # 5. Contracts (Register + Lines)
        cr_path = os.path.join(KIT_DIR, "contracts", "contract_register.csv")
        cl_path = os.path.join(KIT_DIR, "contracts", "contract_lines.csv")
        
        if os.path.exists(cr_path):
            df_cr = pd.read_csv(cr_path)
            for _, row in df_cr.iterrows():
                cid = str(row["contract_id"]).strip()
                c = session.get(ContractHeader, cid)
                s_date = datetime.strptime(str(row["start_date"]).strip(), "%Y-%m-%d").date()
                e_date = datetime.strptime(str(row["end_date"]).strip(), "%Y-%m-%d").date()
                if not c:
                    c = ContractHeader(
                        contract_id=cid,
                        supplier_id=str(row["supplier_id"]).strip(),
                        supplier_name=str(row["supplier_name"]).strip(),
                        start_date=s_date,
                        end_date=e_date,
                        value_cap=float(row["value_cap"]),
                        consumed_value=float(row["consumed_value"]),
                        source_type="REGISTER_CSV"
                    )
                    session.add(c)
                else:
                    c.value_cap = float(row["value_cap"])
                    c.consumed_value = float(row["consumed_value"])
            session.commit()
            print(f"Seeded {len(df_cr)} contracts from register.")

        if os.path.exists(cl_path):
            df_cl = pd.read_csv(cl_path)
            for _, row in df_cl.iterrows():
                cid = str(row["contract_id"]).strip()
                icode = str(row["item_code"]).strip()
                existing = session.query(ContractLine).filter_by(contract_id=cid, item_code=icode).first()
                if not existing:
                    session.add(ContractLine(
                        contract_id=cid,
                        item_code=icode,
                        description=str(row["description"]).strip(),
                        uom=str(row["uom"]).strip(),
                        rate=float(row["rate"])
                    ))
            session.commit()
            print(f"Seeded {len(df_cl)} contract lines.")

        # 6. Parse PDF-only contracts: RC-2026-031 and RC-2026-033
        pdf_dir = os.path.join(KIT_DIR, "contracts", "pdf")
        for pdf_name in ["RC-2026-031.pdf", "RC-2026-033.pdf"]:
            pdf_path = os.path.join(pdf_dir, pdf_name)
            if os.path.exists(pdf_path):
                parsed = parse_contract_pdf(pdf_path)
                cid = parsed["contract_id"]
                c = session.get(ContractHeader, cid)
                if not c:
                    c = ContractHeader(
                        contract_id=cid,
                        supplier_id=parsed["supplier_id"],
                        supplier_name=parsed["supplier_name"],
                        start_date=parsed["start_date"],
                        end_date=parsed["end_date"],
                        value_cap=parsed["value_cap"],
                        consumed_value=0.0,
                        source_type="PDF_EXTRACTED",
                        pdf_filename=pdf_name
                    )
                    session.add(c)
                    session.flush()
                for line in parsed["lines"]:
                    icode = line["item_code"]
                    existing_l = session.query(ContractLine).filter_by(contract_id=cid, item_code=icode).first()
                    if not existing_l:
                        session.add(ContractLine(
                            contract_id=cid,
                            item_code=icode,
                            description=line["description"],
                            uom=line["uom"],
                            rate=line["rate"]
                        ))
                session.commit()
                print(f"Extracted and seeded PDF contract {cid} ({len(parsed['lines'])} lines).")

        # 7. Seed Policy v5.0
        policy_path = os.path.join(os.path.dirname(BASE_DIR), "data", "seed", "policy_v5.0.json")
        if os.path.exists(policy_path):
            with open(policy_path, "r", encoding="utf-8") as f:
                policy_data = json.load(f)
            pv_id = policy_data["policy_version"]
            pv = session.get(PolicyVersion, pv_id)
            eff_date = datetime.strptime(policy_data["effective_date"], "%Y-%m-%d").date()
            if not pv:
                pv = PolicyVersion(
                    version_id=pv_id,
                    name=policy_data["name"],
                    document_ref=policy_data.get("document_ref"),
                    effective_date=eff_date,
                    status="ACTIVE",
                    rules_definition=policy_data,
                    created_by="SYSTEM"
                )
                session.add(pv)
            else:
                pv.rules_definition = policy_data
                pv.status = "ACTIVE"
            session.commit()
            print(f"Seeded active policy {pv_id}.")

    finally:
        session.close()
    print("Seed complete!")

if __name__ == "__main__":
    seed_all()

