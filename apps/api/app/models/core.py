"""Shared core domain — orchestrator §1a.

Defined once here and consumed by every module. Do not redefine per module.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk

# --- Enum-ish string domains -------------------------------------------------
# Externally visible, evolving codes stay as VARCHAR + CHECK so a new value is a
# one-line migration instead of a Postgres type rewrite (§3 Backend/data).

MERCHANT_KINDS = ("RETAIL", "BANK", "INSURER", "UTILITY_PROVIDER", "SERVICE_PROVIDER", "OTHER")
CATEGORY_DOMAINS = ("GROCERY", "BANKING", "HEALTH", "UTILITY", "VEHICLE", "OTHER")
LINK_TYPES = (
    "RECEIPT_TRANSACTION",
    "CLAIM_TRANSACTION",
    "BILL_TRANSACTION",
    "VEHICLE_EXPENSE_TRANSACTION",
    "OTHER",
)
LINK_STATUSES = ("SUGGESTED", "CONFIRMED", "DISMISSED")
REVIEW_STATUSES = ("PENDING", "CONFIRMED", "FIXED", "DISMISSED")
AUDIT_ACTIONS = ("CREATE", "UPDATE", "DELETE", "STATUS_CHANGE")
SETTING_SCOPES = ("GLOBAL", "HOUSEHOLD", "ENTITY", "MODULE")
IMPORT_SOURCES = ("CSV", "OFX", "PDF", "MANUAL")
IMPORT_STATUSES = ("PENDING", "PROCESSING", "COMPLETED", "FAILED")
JOB_STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "RETRYING")
DOCUMENT_SOURCES = ("URL", "UPLOAD")


def _check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


class Merchant(Base, TimestampMixin, SoftDeleteMixin):
    """Global reference data — not entity-scoped."""

    __tablename__ = "merchants"
    __table_args__ = (
        _check("kind", MERCHANT_KINDS, "kind"),
        Index("ix_merchants_name", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    nif: Mapped[str | None] = mapped_column(String(9), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    default_category_l1_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    default_category_l2_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    aliases: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Category(Base, SoftDeleteMixin):
    """Hierarchical taxonomy. Invariants enforced in the service layer and by CHECK."""

    __tablename__ = "categories"
    __table_args__ = (
        _check("domain", CATEGORY_DOMAINS, "domain"),
        CheckConstraint("level BETWEEN 1 AND 3", name="ck_categories_level"),
        CheckConstraint(
            "(level = 1 AND parent_id IS NULL) OR (level > 1 AND parent_id IS NOT NULL)",
            name="ck_categories_level_parent",
        ),
        UniqueConstraint("domain", "code_en", name="uq_categories_domain_code_en"),
        Index("ix_categories_parent_id", "parent_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    code_en: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name_pt: Mapped[str] = mapped_column(String(160), nullable=False)
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    brand_axis: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class Tag(Base, SoftDeleteMixin):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("household_id", "name", name="uq_tags_household_id_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    household_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("households.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Document(Base):
    """Binary attachment stored outside the web root, served only via a signed URL."""

    __tablename__ = "documents"
    __table_args__ = (
        _check("source", DOCUMENT_SOURCES, "source"),
        Index("ix_documents_sha256_hash", "sha256_hash"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="UPLOAD")
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signed_url_expires_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15, server_default="15"
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class Link(Base):
    """Polymorphic reconciliation edge. No real FKs — see the integrity audit job."""

    __tablename__ = "links"
    __table_args__ = (
        _check("link_type", LINK_TYPES, "link_type"),
        _check("status", LINK_STATUSES, "status"),
        Index("ix_links_from", "from_type", "from_id"),
        Index("ix_links_to", "to_type", "to_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    from_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    to_type: Mapped[str] = mapped_column(String(64), nullable=False)
    to_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    link_type: Mapped[str] = mapped_column(String(48), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    decision_reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="SUGGESTED")
    created_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class ReviewTask(Base):
    """Backs the shared Review Queue."""

    __tablename__ = "review_tasks"
    __table_args__ = (
        _check("status", REVIEW_STATUSES, "status"),
        Index("ix_review_tasks_entity_status", "entity_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(48), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    suggested_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    decision_reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class AuditLog(Base):
    """Sole source of truth for historical state. Every mutation writes one row."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        _check("action", AUDIT_ACTIONS, "action"),
        Index("ix_audit_logs_record", "table_name", "record_id", "created_at"),
        Index("ix_audit_logs_entity_id_created_at", "entity_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class Setting(Base):
    """Confidence thresholds, provider opt-ins and per-module knobs."""

    __tablename__ = "settings"
    __table_args__ = (
        _check("scope", SETTING_SCOPES, "scope"),
        UniqueConstraint("scope", "scope_id", "key", name="uq_settings_scope_scope_id_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="GLOBAL")
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        _check("source_type", IMPORT_SOURCES, "source_type"),
        _check("status", IMPORT_STATUSES, "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(48), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessingJob(Base):
    """One row per background task. A failure is a row here, never a silent loss."""

    __tablename__ = "processing_jobs"
    __table_args__ = (
        _check("status", JOB_STATUSES, "status"),
        UniqueConstraint("idempotency_key", name="uq_processing_jobs_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "AuditLog",
    "Category",
    "Document",
    "ImportBatch",
    "Link",
    "Merchant",
    "ProcessingJob",
    "ReviewTask",
    "Setting",
    "Tag",
]
