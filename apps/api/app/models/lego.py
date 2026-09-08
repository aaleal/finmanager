"""Module 9 — LEGO Collection Catalog.

The spine is three tables: catalog identity (``LegoSetModel``), the owned
physical copy (``LegoSetInstance``) and a flat place (``StorageLocation``). Two
attachment tables were added since, each with its own ADR: ``LegoSetImage``
(0013) and ``LegoSetInstruction`` (0040). There is still no valuation history
and no external-listing table — by explicit design.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, uuid_pk

ACQUISITION_SOURCES = ("CONTINENTE", "AMAZON", "OTHER_STORE", "SECONDHAND", "GIFT", "OTHER")
BUILD_STATES = ("BUILT", "DISASSEMBLED")
CONDITIONS = ("SEALED", "NEW", "GOOD", "WORN", "DAMAGED")
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
        CheckConstraint(
            "age_min IS NULL OR age_max IS NULL OR age_max >= age_min",
            name="ck_lego_set_models_age_range",
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
    # Dates, not years: a set retiring in December is on sale for the whole year.
    # See docs/decisions/0012-lego-retirement-is-a-date.md
    release_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    retirement_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    piece_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minifig_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Brickset publishes an open-ended range: `18+` is a min with no max.
    age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    box_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    box_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    box_depth_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    box_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
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
    images: Mapped[list[LegoSetImage]] = relationship(
        "LegoSetImage",
        back_populates="model",
        lazy="selectin",
        order_by="LegoSetImage.position",
        cascade="all, delete-orphan",
    )
    instructions: Mapped[list[LegoSetInstruction]] = relationship(
        "LegoSetInstruction",
        back_populates="model",
        lazy="selectin",
        order_by="LegoSetInstruction.position",
        cascade="all, delete-orphan",
    )

    @property
    def is_retired(self) -> bool:
        """Retired only once the date has actually passed, never in advance."""
        return self.retirement_date is not None and self.retirement_date <= dt.date.today()


class LegoSetImage(Base):
    """An extra view of the set beyond the box shot kept in ``image_document_id``.

    See docs/decisions/0013-lego-set-gallery.md for why this is the fourth table.
    """

    __tablename__ = "lego_set_images"
    __table_args__ = (
        UniqueConstraint(
            "lego_set_model_id", "document_id", name="uq_lego_set_images_model_document"
        ),
        Index("ix_lego_set_images_model_position", "lego_set_model_id", "position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lego_set_model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("lego_set_models.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    model: Mapped[LegoSetModel] = relationship("LegoSetModel", back_populates="images")


class LegoSetInstruction(Base):
    """A building manual or info booklet, downloaded once and kept on disk.

    See docs/decisions/0040-a-manual-is-downloaded-not-linked.md.
    """

    __tablename__ = "lego_set_instructions"
    __table_args__ = (
        UniqueConstraint(
            "lego_set_model_id", "document_id", name="uq_lego_set_instructions_model_document"
        ),
        Index("ix_lego_set_instructions_model_position", "lego_set_model_id", "position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lego_set_model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("lego_set_models.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    #: ``None`` means the manual carries no language at all — a picture-only
    #: building instruction, which is every LEGO manual since 2000.
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    model: Mapped[LegoSetModel] = relationship("LegoSetModel", back_populates="instructions")


class StorageLocation(Base, SoftDeleteMixin):
    """Flat ``area`` + ``container``. No tree — real usage never needed one.

    Household-level reference data, not entity-scoped — a shelf does not
    belong to whoever created it, it holds anyone's sets (ADR-0046, the same
    trade as ADR-0019 for the product catalogue).
    """

    __tablename__ = "lego_storage_locations"
    __table_args__ = (
        UniqueConstraint("area", "container", name="uq_lego_storage_locations_area_container"),
        CheckConstraint(
            "capacity_pct IS NULL OR (capacity_pct BETWEEN 0 AND 100)",
            name="ck_lego_storage_locations_capacity_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
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
            "('CONTINENTE', 'AMAZON', 'OTHER_STORE', 'SECONDHAND', 'GIFT', 'OTHER')",
            name="ck_lego_set_instances_acquisition_source",
        ),
        CheckConstraint(
            "build_state IS NULL OR build_state IN ('BUILT', 'DISASSEMBLED')",
            name="ck_lego_set_instances_build_state",
        ),
        CheckConstraint(
            "condition IS NULL OR condition IN ('SEALED', 'NEW', 'GOOD', 'WORN', 'DAMAGED')",
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
    # Manually toggled (FR-9.8 amendment) — never derived from cost/source, only
    # flagged with a toast when it's set alongside a GIFT origin (odd combination).
    is_fs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Forward-looking ("earmarked to give away") — independent of
    # `acquisition_source == 'GIFT'`, which is about how the copy was acquired.
    is_potential_gift: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
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
    # Which of the set's own images (cover or gallery) stands for this exact copy in
    # the collection table — distinct from `photo_document_id`, a photo of this box.
    display_image_document_id: Mapped[uuid.UUID | None] = mapped_column(
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
    "LegoSetImage",
    "LegoSetInstance",
    "LegoSetInstruction",
    "LegoSetModel",
    "StorageLocation",
]
