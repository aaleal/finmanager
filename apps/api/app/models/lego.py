"""Module 9 — LEGO Collection Catalog.

Three tables only: catalog identity (``LegoSetModel``), the owned physical copy
(``LegoSetInstance``) and a flat place (``StorageLocation``). No valuation
history, no galleries, no external-listing table — by explicit design.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk

ACQUISITION_SOURCES = ("RETAIL", "SECONDHAND", "GIFT", "OTHER")
BUILD_STATES = ("SEALED", "BUILT", "DISASSEMBLED")
CONDITIONS = ("NEW", "GOOD", "WORN", "DAMAGED")
OWNERSHIP_STATUSES = ("IN_COLLECTION", "SOLD", "GIFTED")


class LegoSetModel(Base, TimestampMixin, SoftDeleteMixin):
    """Catalog identity + the single, hand-maintained current market value."""

    __tablename__ = "lego_set_models"
    __table_args__ = (
        # Unique per entity only while the row is alive and has a set number.
        Index(
            "uq_lego_set_models_entity_set_number",
            "entity_id",
            "set_number",
            unique=True,
            postgresql_where=text("set_number IS NOT NULL AND is_deleted = false"),
        ),
        Index("ix_lego_set_models_entity_id_name", "entity_id", "name"),
        Index("ix_lego_set_models_theme", "theme"),
        CheckConstraint(
            "current_value_eur IS NULL OR current_value_eur >= 0",
            name="ck_lego_set_models_value_non_negative",
        ),
        CheckConstraint(
            "(is_custom = true AND set_number IS NULL) OR is_custom = false",
            name="ck_lego_set_models_custom_has_no_number",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    set_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_custom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    theme: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subtheme: Mapped[str | None] = mapped_column(String(120), nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retired_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    piece_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minifig_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rrp_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    current_value_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    value_updated_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    image_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    instances: Mapped[list[LegoSetInstance]] = relationship(
        "LegoSetInstance", back_populates="model", lazy="selectin"
    )

    @property
    def is_retired(self) -> bool:
        return self.retired_year is not None


class StorageLocation(Base, SoftDeleteMixin):
    """Flat ``area`` + ``container``. No tree — real usage never needed one."""

    __tablename__ = "lego_storage_locations"
    __table_args__ = (
        UniqueConstraint(
            "entity_id", "area", "container", name="uq_lego_storage_locations_entity_area_container"
        ),
        CheckConstraint(
            "capacity_pct IS NULL OR (capacity_pct BETWEEN 0 AND 100)",
            name="ck_lego_storage_locations_capacity_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    area: Mapped[str] = mapped_column(String(120), nullable=False)
    container: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    capacity_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)

    @property
    def label(self) -> str:
        return f"{self.area} › {self.container}" if self.container else self.area


class LegoSetInstance(Base, TimestampMixin, SoftDeleteMixin):
    """Exactly one physical copy per row — there is deliberately no ``quantity``."""

    __tablename__ = "lego_set_instances"
    __table_args__ = (
        CheckConstraint(
            "acquisition_cost_eur >= 0", name="ck_lego_set_instances_cost_non_negative"
        ),
        CheckConstraint(
            "acquisition_source IS NULL OR acquisition_source IN "
            "('RETAIL', 'SECONDHAND', 'GIFT', 'OTHER')",
            name="ck_lego_set_instances_acquisition_source",
        ),
        CheckConstraint(
            "build_state IS NULL OR build_state IN ('SEALED', 'BUILT', 'DISASSEMBLED')",
            name="ck_lego_set_instances_build_state",
        ),
        CheckConstraint(
            "condition IS NULL OR condition IN ('NEW', 'GOOD', 'WORN', 'DAMAGED')",
            name="ck_lego_set_instances_condition",
        ),
        CheckConstraint(
            "ownership_status IN ('IN_COLLECTION', 'SOLD', 'GIFTED')",
            name="ck_lego_set_instances_ownership_status",
        ),
        Index("ix_lego_set_instances_model_id", "lego_set_model_id"),
        Index("ix_lego_set_instances_entity_status", "entity_id", "ownership_status", "is_deleted"),
        Index("ix_lego_set_instances_storage_location_id", "storage_location_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False
    )
    lego_set_model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("lego_set_models.id"), nullable=False
    )
    acquisition_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    acquisition_cost_eur: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    acquisition_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # M2 is not built yet: the column is the contract, the FK lands with the ledger.
    # See docs/decisions/0005-defer-transaction-fk.md
    acquisition_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    storage_location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("lego_storage_locations.id"), nullable=True
    )
    build_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(16), nullable=True)
    has_box: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    has_instructions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    missing_parts: Mapped[str | None] = mapped_column(Text, nullable=True)
    ownership_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="IN_COLLECTION", server_default="'IN_COLLECTION'"
    )
    sale_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sale_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    photo_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    model: Mapped[LegoSetModel] = relationship("LegoSetModel", back_populates="instances")
    storage_location: Mapped[StorageLocation | None] = relationship(
        "StorageLocation", lazy="joined"
    )

    @property
    def is_complete(self) -> bool:
        return not (self.missing_parts or "").strip()

    @property
    def in_collection(self) -> bool:
        return self.ownership_status == "IN_COLLECTION" and not self.is_deleted


__all__ = [
    "ACQUISITION_SOURCES",
    "BUILD_STATES",
    "CONDITIONS",
    "OWNERSHIP_STATUSES",
    "LegoSetInstance",
    "LegoSetModel",
    "StorageLocation",
]
