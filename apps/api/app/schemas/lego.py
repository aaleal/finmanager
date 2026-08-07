from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ApiModel

AcquisitionSource = Literal["RETAIL", "SECONDHAND", "GIFT", "OTHER"]
BuildState = Literal["SEALED", "BUILT", "DISASSEMBLED"]
Condition = Literal["NEW", "GOOD", "WORN", "DAMAGED"]
OwnershipStatus = Literal["IN_COLLECTION", "SOLD", "GIFTED"]


# --- Storage -----------------------------------------------------------------
class StorageLocationBase(BaseModel):
    area: str = Field(min_length=1, max_length=120)
    container: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    capacity_pct: int | None = Field(default=None, ge=0, le=100)


class StorageLocationCreate(StorageLocationBase):
    entity_id: uuid.UUID | None = None


class StorageLocationUpdate(BaseModel):
    area: str | None = Field(default=None, min_length=1, max_length=120)
    container: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    capacity_pct: int | None = Field(default=None, ge=0, le=100)


class StorageLocationOut(ApiModel):
    id: uuid.UUID
    entity_id: uuid.UUID
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
class LegoSetModelBase(BaseModel):
    set_number: str | None = Field(default=None, max_length=32)
    is_custom: bool = False
    name: str = Field(min_length=1, max_length=250)
    theme: str | None = Field(default=None, max_length=120)
    subtheme: str | None = Field(default=None, max_length=120)
    release_year: int | None = Field(default=None, ge=1932, le=2100)
    retired_year: int | None = Field(default=None, ge=1932, le=2100)
    piece_count: int | None = Field(default=None, ge=0)
    minifig_count: int | None = Field(default=None, ge=0)
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
        return self


class LegoSetModelCreate(LegoSetModelBase):
    entity_id: uuid.UUID | None = None
    image_url: str | None = Field(default=None, max_length=1000)


class LegoSetModelUpdate(BaseModel):
    set_number: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=250)
    theme: str | None = Field(default=None, max_length=120)
    subtheme: str | None = Field(default=None, max_length=120)
    release_year: int | None = Field(default=None, ge=1932, le=2100)
    retired_year: int | None = Field(default=None, ge=1932, le=2100)
    piece_count: int | None = Field(default=None, ge=0)
    minifig_count: int | None = Field(default=None, ge=0)
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
    release_year: int | None
    retired_year: int | None
    piece_count: int | None
    minifig_count: int | None
    rrp_eur: Decimal | None
    current_value_eur: Decimal | None
    value_updated_at: dt.date | None
    image_document_id: uuid.UUID | None
    image_url: str | None = None
    short_description: str | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    is_retired: bool = False
    value_is_stale: bool = False
    value_age_days: int | None = None
    owned_copies_count: int = 0


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
    missing_parts: str | None
    ownership_status: OwnershipStatus
    sale_price_eur: Decimal | None
    sale_date: dt.date | None
    photo_document_id: uuid.UUID | None
    photo_url: str | None = None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    is_complete: bool = True
    current_value_eur: Decimal | None = None
    appreciation_eur: Decimal | None = None
    roi_pct: Decimal | None = None
    storage_label: str | None = None
    set_model: LegoSetModelOut | None = None


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
    release_year: int | None = None
    retired_year: int | None = None
    piece_count: int | None = None
    minifig_count: int | None = None
    rrp_eur: Decimal | None = None
    image_url: str | None = None
    short_description: str | None = None


# --- Overview ----------------------------------------------------------------
class ThemeBreakdown(BaseModel):
    theme: str
    copies: int
    unique_sets: int
    cost_eur: Decimal
    value_eur: Decimal


class OverviewOut(BaseModel):
    total_cost_eur: Decimal
    total_value_eur: Decimal
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
    top_gainers: list[LegoSetInstanceOut]
    top_losers: list[LegoSetInstanceOut]
    locations_full: int
    locations_total: int
