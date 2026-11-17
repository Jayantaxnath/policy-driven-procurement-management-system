"""
SQLAlchemy ORM models for Corvo Procurement Management System.
Compatible with PostgreSQL and SQLite.
"""
import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime, 
    Text, ForeignKey, UniqueConstraint, BigInteger, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

# ─── MASTER DATA ──────────────────────────────────────────────────────────────

class Plant(Base):
    __tablename__ = "plants"
    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class ItemMaster(Base):
    __tablename__ = "item_master"
    item_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    uom: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)  # Material | Service | Capex
    standard_price: Mapped[float] = mapped_column(Float, nullable=False)


class SupplierMaster(Base):
    __tablename__ = "supplier_master"
    supplier_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    categories: Mapped[list] = mapped_column(JSON, nullable=False)  # list of strings
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # Active | Blocked | Inactive
    on_time_pct: Mapped[float] = mapped_column(Float, nullable=False)
    quality_rating: Mapped[float] = mapped_column(Float, nullable=False)


class POHistory(Base):
    __tablename__ = "po_history"
    po_number: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(20), ForeignKey("supplier_master.supplier_id"), nullable=False)
    item_code: Mapped[str] = mapped_column(String(20), ForeignKey("item_master.item_code"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    uom: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    plant: Mapped[str] = mapped_column(String(10), ForeignKey("plants.plant_code"), nullable=False)
    delivered_on_time: Mapped[bool] = mapped_column(Boolean, nullable=False)


# ─── CONTRACT TABLES ──────────────────────────────────────────────────────────

class ContractHeader(Base):
    __tablename__ = "contract_headers"
    contract_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(String(20), ForeignKey("supplier_master.supplier_id"), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_cap: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # REGISTER_CSV | PDF_EXTRACTED | MANUAL
    pdf_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    lines: Mapped[List["ContractLine"]] = relationship("ContractLine", back_populates="contract", cascade="all, delete-orphan")


class ContractLine(Base):
    __tablename__ = "contract_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[str] = mapped_column(String(50), ForeignKey("contract_headers.contract_id", ondelete="CASCADE"), nullable=False)
    item_code: Mapped[str] = mapped_column(String(20), ForeignKey("item_master.item_code"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    uom: Mapped[str] = mapped_column(String(20), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    
    contract: Mapped["ContractHeader"] = relationship("ContractHeader", back_populates="lines")
    __table_args__ = (UniqueConstraint("contract_id", "item_code"),)


# ─── POLICY VERSIONING ────────────────────────────────────────────────────────

class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    version_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")  # DRAFT | ACTIVE | SUPERSEDED
    rules_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    parent_version_id: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("policy_versions.version_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class PolicyApproval(Base):
    __tablename__ = "policy_approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String(20), ForeignKey("policy_versions.version_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # SUBMITTED | APPROVED | REJECTED | ACTIVATED | SUPERSEDED
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ─── OPERATIONAL TABLES ───────────────────────────────────────────────────────

class PRBatch(Base):
    __tablename__ = "pr_batches"
    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    batch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CSV_UPLOAD | CHAT | API
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    lines: Mapped[List["PRLine"]] = relationship("PRLine", back_populates="batch", cascade="all, delete-orphan")


class PRLine(Base):
    __tablename__ = "pr_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("pr_batches.batch_id"), nullable=False)
    pr_no: Mapped[str] = mapped_column(String(50), nullable=False)
    pr_line: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    requester: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    plant: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    item_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uom: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    need_by_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String(20), default="Normal")
    ingestion_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    not_processed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    batch: Mapped["PRBatch"] = relationship("PRBatch", back_populates="lines")
    __table_args__ = (UniqueConstraint("batch_id", "pr_no", "pr_line"),)


class BatchExecutionRun(Base):
    __tablename__ = "batch_execution_runs"
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("pr_batches.batch_id"), nullable=False)
    policy_version_id: Mapped[str] = mapped_column(String(20), ForeignKey("policy_versions.version_id"), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    executed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    total_pr_lines: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_requirements: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_pos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_sourcing_requests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_not_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Requirement(Base):
    __tablename__ = "requirements"
    requirement_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("batch_execution_runs.run_id", ondelete="CASCADE"), nullable=False)
    resolved_item_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_new_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    plant: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    requirement_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    uom: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, default="Normal")
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    group_value_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    winning_contract_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    supplier_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    po_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    suggested_supplier_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    policy_clause: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    pr_lines: Mapped[List["RequirementLine"]] = relationship("RequirementLine", back_populates="requirement", cascade="all, delete-orphan")


class RequirementLine(Base):
    __tablename__ = "requirement_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requirement_id: Mapped[str] = mapped_column(String(100), ForeignKey("requirements.requirement_id", ondelete="CASCADE"), nullable=False)
    pr_line_id: Mapped[str] = mapped_column(String(36), ForeignKey("pr_lines.id"), nullable=False)
    
    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="pr_lines")
    __table_args__ = (UniqueConstraint("requirement_id", "pr_line_id"),)


class POHeader(Base):
    __tablename__ = "po_headers"
    po_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("batch_execution_runs.run_id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(20), ForeignKey("supplier_master.supplier_id"), nullable=False)
    plant: Mapped[str] = mapped_column(String(10), ForeignKey("plants.plant_code"), nullable=False)
    route: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    po_lines: Mapped[List["POLine"]] = relationship("POLine", back_populates="po_header", cascade="all, delete-orphan")


class POLine(Base):
    __tablename__ = "po_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[str] = mapped_column(String(50), ForeignKey("po_headers.po_id", ondelete="CASCADE"), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(100), ForeignKey("requirements.requirement_id"), nullable=False)
    item_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uom: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    line_value_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    po_header: Mapped["POHeader"] = relationship("POHeader", back_populates="po_lines")


class ContractConsumptionLog(Base):
    __tablename__ = "contract_consumption_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("batch_execution_runs.run_id", ondelete="CASCADE"), nullable=False)
    contract_id: Mapped[str] = mapped_column(String(50), ForeignKey("contract_headers.contract_id"), nullable=False)
    requirement_group_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_consumed: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BuyerAction(Base):
    __tablename__ = "buyer_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("batch_execution_runs.run_id"), nullable=False)
    requirement_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("requirements.requirement_id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)  # APPROVED | OVERRIDDEN | REJECTED | HELD
    buyer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    previous_route: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_route: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    previous_supplier_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_supplier_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

