from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ApiModel, Page

AcquisitionSource = Literal["CONTINENTE", "AMAZON", "OTHER_STORE", "SECONDHAND", "GIFT", "OTHER"]
BuildState = Literal["BUILT", "DISASSEMBLED"]
Condition = Literal["SEALED", "NEW", "GOOD", "WORN", "DAMAGED"]
OwnershipStatus = Literal["IN_COLLECTION", "SOLD", "GIFTED"]
# Tri-state discovery filters (M9.1): «todos» is always the default.
CompletenessFilter = Literal["all", "complete", "incomplete"]
RetirementFilter = Literal["all", "retired", "available"]
# How many copies of the same set are owned — «todos» is always the default.
CopiesFilter = Literal["all", "single", "multiple"]
FsFilter = Literal["all", "fs", "not_fs"]
GiftFilter = Literal["all", "gift", "not_gift"]


# --- Storage -----------------------------------------------------------------
class StorageLocationBase(BaseModel):
    area: str = Field(min_length=1, max_length=120)
    container: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    capacity_pct: int | None = Field(default=None, ge=0, le=100)


class StorageLocationCreate(StorageLocationBase):
    pass


class StorageLocationUpdate(BaseModel):
    area: str | None = Field(default=None, min_length=1, max_length=120)
    container: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    capacity_pct: int | None = Field(default=None, ge=0, le=100)


class StorageLocationOut(ApiModel):
    id: uuid.UUID
    area: str
    container: str | None
    description: str | None
    capacity_pct: int | None
    label: str
    stored_count: int = 0
    stored_value_eur: Decimal = Decimal("0.00")
    remaining_capacity_pct: int | None = None
    is_full: bool = False


# --- Set model ---------------------------------------------------------------
class LegoSetImageOut(ApiModel):
    id: uuid.UUID
    document_id: uuid.UUID
    url: str | None = None
    caption: str | None = None
    position: int = 0


class LegoSetImageUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=200)
    position: int | None = Field(default=None, ge=0)


class LegoSetInstructionOut(ApiModel):
    id: uuid.UUID
    document_id: uuid.UUID
    url: str | None = None
    description: str
    #: ``None`` for the language-neutral building instructions.
    language: str | None = None
    position: int = 0


class LegoSetModelBase(BaseModel):
    set_number: str | None = Field(default=None, max_length=32)
    is_custom: bool = False
    name: str = Field(min_length=1, max_length=250)
    theme: str | None = Field(default=None, max_length=120)
    subtheme: str | None = Field(default=None, max_length=120)
    release_date: dt.date | None = None
    retirement_date: dt.date | None = None
    piece_count: int | None = Field(default=None, ge=0)
    minifig_count: int | None = Field(default=None, ge=0)
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max: int | None = Field(default=None, ge=0, le=120)
    box_height_cm: Decimal | None = Field(default=None, ge=0, decimal_places=1)
    box_width_cm: Decimal | None = Field(default=None, ge=0, decimal_places=1)
    box_depth_cm: Decimal | None = Field(default=None, ge=0, decimal_places=1)
    box_weight_kg: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    rrp_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    current_value_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    short_description: str | None = Field(default=None, max_length=500)
    notes: str | None = None

    @model_validator(mode="after")
    def _custom_has_no_number(self) -> LegoSetModelBase:
        if self.is_custom and self.set_number:
            raise ValueError("uma construção personalizada (MOC) não pode ter número de conjunto")
        if not self.is_custom and not self.set_number:
            raise ValueError("indique o número do conjunto ou marque-o como MOC")
        if (
            self.release_date is not None
            and self.retirement_date is not None
            and self.retirement_date < self.release_date
        ):
            raise ValueError("a data de retirada não pode ser anterior à data de lançamento")
        if self.age_min is not None and self.age_max is not None and self.age_max < self.age_min:
            raise ValueError("a idade máxima não pode ser inferior à idade mínima")
        return self


class LegoSetModelCreate(LegoSetModelBase):
    entity_id: uuid.UUID | None = None
    image_url: str | None = Field(default=None, max_length=1000)


class LegoSetModelUpdate(BaseModel):
    set_number: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=250)
    theme: str | None = Field(default=None, max_length=120)
    subtheme: str | None = Field(default=None, max_length=120)
    release_date: dt.date | None = None
    retirement_date: dt.date | None = None
    piece_count: int | None = Field(default=None, ge=0)
    minifig_count: int | None = Field(default=None, ge=0)
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max: int | None = Field(default=None, ge=0, le=120)
    box_height_cm: Decimal | None = Field(default=None, ge=0, decimal_places=1)
    box_width_cm: Decimal | None = Field(default=None, ge=0, decimal_places=1)
    box_depth_cm: Decimal | None = Field(default=None, ge=0, decimal_places=1)
    box_weight_kg: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    rrp_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    current_value_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    short_description: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    entity_id: uuid.UUID | None = None


class LegoSetModelOut(ApiModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    set_number: str | None
    is_custom: bool
    name: str
    theme: str | None
    subtheme: str | None
    release_date: dt.date | None
    retirement_date: dt.date | None
    piece_count: int | None
    minifig_count: int | None
    age_min: int | None
    age_max: int | None
    box_height_cm: Decimal | None
    box_width_cm: Decimal | None
    box_depth_cm: Decimal | None
    box_weight_kg: Decimal | None
    rrp_eur: Decimal | None
    current_value_eur: Decimal | None
    value_updated_at: dt.date | None
    image_document_id: uuid.UUID | None
    image_url: str | None = None
    # The box shot above is always the first frame; these are the extra views.
    images: list[LegoSetImageOut] = []
    # Manuals and info booklets, downloaded once and served from disk.
    instructions: list[LegoSetInstructionOut] = []
    short_description: str | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    is_retired: bool = False
    # Year views of the two dates, so the grid can stay a compact "2022 / 2024".
    release_year: int | None = None
    retired_year: int | None = None
    value_is_stale: bool = False
    value_age_days: int | None = None
    owned_copies_count: int = 0
    # Second, cost-independent read on the same set: today's value against the
    # original RRP. Never mixed into the acquisition-cost ROI (M9.1).
    rrp_appreciation_eur: Decimal | None = None
    rrp_roi_pct: Decimal | None = None


# --- Instance ----------------------------------------------------------------
class LegoSetInstanceBase(BaseModel):
    acquisition_date: dt.date | None = None
    acquisition_cost_eur: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    acquisition_source: AcquisitionSource | None = None
    acquisition_transaction_id: uuid.UUID | None = None
    storage_location_id: uuid.UUID | None = None
    build_state: BuildState | None = None
    condition: Condition | None = None
    has_box: bool = True
    has_instructions: bool = True
    is_fs: bool = False
    is_potential_gift: bool = False
    missing_parts: str | None = None
    notes: str | None = None


class LegoSetInstanceCreate(LegoSetInstanceBase):
    entity_id: uuid.UUID | None = None
    lego_set_model_id: uuid.UUID | None = None
    # Find-or-create shortcut (FR-9.3): register a copy straight from a set number.
    new_set: LegoSetModelCreate | None = None

    @model_validator(mode="after")
    def _needs_a_model(self) -> LegoSetInstanceCreate:
        if self.lego_set_model_id is None and self.new_set is None:
            raise ValueError("indique um conjunto existente ou os dados de um novo conjunto")
        return self


class LegoSetInstanceUpdate(BaseModel):
    acquisition_date: dt.date | None = None
    acquisition_cost_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    acquisition_source: AcquisitionSource | None = None
    acquisition_transaction_id: uuid.UUID | None = None
    storage_location_id: uuid.UUID | None = None
    build_state: BuildState | None = None
    condition: Condition | None = None
    has_box: bool | None = None
    has_instructions: bool | None = None
    is_fs: bool | None = None
    is_potential_gift: bool | None = None
    missing_parts: str | None = None
    notes: str | None = None
    ownership_status: OwnershipStatus | None = None
    sale_price_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sale_date: dt.date | None = None
    entity_id: uuid.UUID | None = None
    # Explicit nulling of optional FKs, since `None` also means "not supplied".
    clear_storage_location: bool = False
    clear_transaction_link: bool = False


class LegoSetInstanceOut(ApiModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    lego_set_model_id: uuid.UUID
    acquisition_date: dt.date | None
    acquisition_cost_eur: Decimal
    acquisition_source: AcquisitionSource | None
    acquisition_transaction_id: uuid.UUID | None
    storage_location_id: uuid.UUID | None
    build_state: BuildState | None
    condition: Condition | None
    has_box: bool
    has_instructions: bool
    is_fs: bool
    is_potential_gift: bool
    missing_parts: str | None
    ownership_status: OwnershipStatus
    sale_price_eur: Decimal | None
    sale_date: dt.date | None
    photo_document_id: uuid.UUID | None
    photo_url: str | None = None
    display_image_document_id: uuid.UUID | None = None
    display_image_url: str | None = None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    is_complete: bool = True
    current_value_eur: Decimal | None = None
    appreciation_eur: Decimal | None = None
    roi_pct: Decimal | None = None
    storage_label: str | None = None
    set_model: LegoSetModelOut | None = None


class CollectionSummary(BaseModel):
    """Totals for the *currently filtered* set of copies, not the whole collection."""

    copies: int
    unique_sets: int
    unique_themes: int
    total_cost_eur: Decimal
    total_rrp_eur: Decimal
    total_value_eur: Decimal
    total_pieces: int


class LegoSetInstancePage(Page[LegoSetInstanceOut]):
    summary: CollectionSummary


class OwnershipChange(BaseModel):
    ownership_status: OwnershipStatus
    sale_price_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sale_date: dt.date | None = None


class ValueUpdate(BaseModel):
    current_value_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)


class ImageSource(BaseModel):
    url: str | None = Field(default=None, max_length=1000)

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("o endereço da imagem tem de começar por http:// ou https://")
        return v


class InstanceDisplayImageUpdate(BaseModel):
    #: `None` clears the pick — the copy falls back to the collection's own cover.
    document_id: uuid.UUID | None = None


# --- Lookup ------------------------------------------------------------------
class LookupRequest(BaseModel):
    set_number: str = Field(min_length=1, max_length=32)


class LookupResult(BaseModel):
    found: bool
    provider: str = "brickset"
    message: str | None = None
    set_number: str | None = None
    name: str | None = None
    theme: str | None = None
    subtheme: str | None = None
    release_date: dt.date | None = None
    retirement_date: dt.date | None = None
    piece_count: int | None = None
    minifig_count: int | None = None
    age_min: int | None = None
    age_max: int | None = None
    box_height_cm: Decimal | None = None
    box_width_cm: Decimal | None = None
    box_depth_cm: Decimal | None = None
    box_weight_kg: Decimal | None = None
    rrp_eur: Decimal | None = None
    image_url: str | None = None
    short_description: str | None = None
    # How much more the provider holds, so the UI can offer the import before
    # anything is downloaded.
    additional_image_count: int = 0
    instruction_count: int = 0


# --- Bulk import (M9.5) -------------------------------------------------------
# The same shape travels both ways: the preview response fills in whatever the
# sheet let it resolve and reports the rest in `errors`; the commit request sends
# the identical shape back once the table shows every row green. See
# docs/decisions/0048-bulk-import-mirrors-the-export.md.
class BulkImportRow(BaseModel):
    row_number: int
    set_number: str | None = Field(default=None, max_length=32)
    entity_id: uuid.UUID | None = None
    entity_name: str | None = None
    storage_location_id: uuid.UUID | None = None
    storage_area: str | None = None
    storage_container: str | None = None
    acquisition_cost_eur: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    acquisition_date: dt.date | None = None
    acquisition_source: AcquisitionSource | None = None
    build_state: BuildState | None = None
    condition: Condition | None = None
    has_box: bool = True
    has_instructions: bool = True
    is_fs: bool = False
    is_potential_gift: bool = False
    missing_parts: str | None = None
    notes: str | None = None
    #: The set's "preço atual" as typed in the sheet — not the physical copy's own
    #: cost. When several rows share a set_number with different values, the
    #: commit keeps the largest one (see lego_bulk_import.py).
    current_value_eur: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    #: Keyed by field name, so the review table can highlight just that cell.
    errors: dict[str, str] = Field(default_factory=dict)


class BulkImportPreviewOut(BaseModel):
    rows: list[BulkImportRow]


class BulkImportCommitIn(BaseModel):
    rows: list[BulkImportRow]


class BulkImportRowResult(BaseModel):
    row_number: int
    ok: bool
    message: str
    lego_set_instance_id: uuid.UUID | None = None


class StorageBulkImportError(BaseModel):
    row_number: int
    message: str


class StorageBulkImportOut(BaseModel):
    created: int
    updated: int
    errors: list[StorageBulkImportError]


class BricksetImportOut(ApiModel):
    """What one press of «Importar do Brickset» actually brought down."""

    model: LegoSetModelOut
    images_added: int = 0
    instructions_added: int = 0
    message: str | None = None


class BricksetJobOut(ApiModel):
    """One row of visibility into a backgrounded images/manuals fetch (ADR-0049)."""

    id: uuid.UUID
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    lego_set_model_id: uuid.UUID
    set_number: str | None
    set_name: str
    created_at: dt.datetime
    started_at: dt.datetime | None
    completed_at: dt.datetime | None


# --- Overview ----------------------------------------------------------------
class ThemeBreakdown(BaseModel):
    theme: str
    copies: int
    unique_sets: int
    cost_eur: Decimal
    value_eur: Decimal
    rrp_eur: Decimal
    piece_count: int = 0


class SubthemeBreakdown(BaseModel):
    """One (theme, subtema) leaf, for a treemap weighted by cost or peças."""

    theme: str
    subtheme: str
    copies: int
    unique_sets: int
    cost_eur: Decimal
    rrp_eur: Decimal
    piece_count: int


class AreaBreakdown(BaseModel):
    """Number of sets/copies and PVP sitting in each storage area — "onde está
    o dinheiro", not just "onde estão as caixas"."""

    area: str
    copies: int
    unique_sets: int
    rrp_eur: Decimal
    sealed_copies: int = 0


class ChannelBreakdown(BaseModel):
    """Real cost paid vs. original PVP, per acquisition source — highlights
    channels where cards/promotions widen the PVP-vs-custo gap."""

    source: str
    copies: int
    cost_eur: Decimal
    rrp_eur: Decimal


class ReleaseYearCount(BaseModel):
    year: int | None
    unique_sets: int


class BuildStateCount(BaseModel):
    build_state: str | None
    copies: int


class PiecePricePoint(BaseModel):
    """One physical copy's cost-per-piece, for the PPP scatter plot."""

    name: str
    set_number: str | None = None
    piece_count: int
    cost_per_piece_eur: Decimal
    rrp_per_piece_eur: Decimal | None = None
    theme: str


class ReleaseYearPiecePoint(BaseModel):
    """One unique model's release year vs. piece count, for the size-over-time
    scatter. Deduped by model — a set owned in triplicate only plots once."""

    name: str
    set_number: str | None = None
    year: int
    piece_count: int
    theme: str


class PieceBracketCount(BaseModel):
    """Unique models bucketed by volumetric size (Micro/Pequeno/Médio/Grande/
    Gigante), in fixed bracket order regardless of which brackets are empty."""

    bracket: str
    unique_sets: int


class TimelinePoint(BaseModel):
    """One month of the acquisition curve.

    ``value_eur`` is **today's** market value of everything acquired up to that
    month — not a historical quote. There is no valuation snapshot table by design
    (ADR-0008), so a true market-value history cannot be drawn.
    """

    month: str
    copies: int
    cost_eur: Decimal
    value_eur: Decimal


class LegoBackupReport(BaseModel):
    """What the restore actually did. A skip is a row that was already there —
    an archive is a snapshot, so it never overwrites what is live today."""

    storage_locations: int = 0
    models: int = 0
    images: int = 0
    instructions: int = 0
    instances: int = 0
    documents: int = 0
    skipped_storage_locations: int = 0
    skipped_models: int = 0
    skipped_images: int = 0
    skipped_instructions: int = 0
    skipped_instances: int = 0


class OverviewOut(BaseModel):
    total_cost_eur: Decimal
    total_value_eur: Decimal
    total_rrp_eur: Decimal
    unrealized_gain_eur: Decimal
    roi_pct: Decimal | None
    unique_sets: int
    copies_owned: int
    total_pieces: int
    total_minifigs: int
    retired_sets: int
    models_without_value: int
    stale_value_models: int
    oldest_value_updated_at: dt.date | None
    stale_threshold_days: int
    departed_copies: int
    departed_sale_total_eur: Decimal
    themes: list[ThemeBreakdown]
    subthemes: list[SubthemeBreakdown]
    areas: list[AreaBreakdown]
    channels: list[ChannelBreakdown]
    release_years: list[ReleaseYearCount]
    build_states: list[BuildStateCount]
    piece_price_points: list[PiecePricePoint]
    release_year_points: list[ReleaseYearPiecePoint]
    piece_brackets: list[PieceBracketCount]
    fs_copies: int
    fs_rrp_eur: Decimal
    timeline: list[TimelinePoint]
    copies_without_date: int
    top_gainers: list[LegoSetInstanceOut]
    top_losers: list[LegoSetInstanceOut]
    locations_full: int
    locations_total: int
