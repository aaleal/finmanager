"""Shared reference data — merchants, categories and tags (Foundation rubric)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentAuth, Db, Writer
from app.core import audit
from app.core.errors import Conflict, NotFound
from app.models.core import Category, Merchant, Tag
from app.schemas.common import ApiModel, Ok

router = APIRouter(tags=["reference"])


# --- Merchants ---------------------------------------------------------------
class MerchantOut(ApiModel):
    id: uuid.UUID
    name: str
    nif: str | None
    kind: str
    website: str | None
    aliases: list[str]


class MerchantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    nif: str | None = Field(default=None, min_length=9, max_length=9, pattern=r"^\d{9}$")
    kind: str = "OTHER"
    website: str | None = None
    aliases: list[str] = Field(default_factory=list)


def _nif_is_valid(nif: str) -> bool:
    """Portuguese NIF checksum (modulo 11)."""
    if not nif.isdigit() or len(nif) != 9:
        return False
    total = sum(int(digit) * (9 - index) for index, digit in enumerate(nif[:8]))
    remainder = total % 11
    check = 0 if remainder < 2 else 11 - remainder
    return check == int(nif[8])


@router.get("/merchants", response_model=list[MerchantOut])
def list_merchants(ctx: CurrentAuth, db: Db, search: str | None = None) -> list[MerchantOut]:
    stmt = select(Merchant).where(Merchant.is_deleted.is_(False))
    if search:
        stmt = stmt.where(Merchant.name.ilike(f"%{search}%"))
    return [
        MerchantOut.model_validate(row) for row in db.scalars(stmt.order_by(Merchant.name)).all()
    ]


@router.post("/merchants", response_model=MerchantOut, status_code=201)
def create_merchant(payload: MerchantIn, ctx: Writer, db: Db) -> MerchantOut:
    if payload.nif and not _nif_is_valid(payload.nif):
        raise Conflict("NIF inválido.")
    if db.scalar(
        select(Merchant).where(
            func.lower(Merchant.name) == payload.name.strip().lower(),
            Merchant.is_deleted.is_(False),
        )
    ):
        raise Conflict("Já existe um comerciante com este nome.")
    merchant = Merchant(**payload.model_dump())
    db.add(merchant)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name="merchants",
        record_id=merchant.id,
        actor_user_id=ctx.user.id,
        after=audit.snapshot(merchant),
    )
    return MerchantOut.model_validate(merchant)


@router.patch("/merchants/{merchant_id}", response_model=MerchantOut)
def update_merchant(
    merchant_id: uuid.UUID, payload: MerchantIn, ctx: Writer, db: Db
) -> MerchantOut:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.is_deleted:
        raise NotFound("Comerciante não encontrado.")
    if payload.nif and not _nif_is_valid(payload.nif):
        raise Conflict("NIF inválido.")
    before = audit.snapshot(merchant)
    for field, value in payload.model_dump().items():
        setattr(merchant, field, value)
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name="merchants",
        record_id=merchant.id,
        actor_user_id=ctx.user.id,
        before=before,
        after=audit.snapshot(merchant),
    )
    return MerchantOut.model_validate(merchant)


@router.delete("/merchants/{merchant_id}", response_model=Ok)
def delete_merchant(merchant_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.is_deleted:
        raise NotFound("Comerciante não encontrado.")
    merchant.is_deleted = True
    audit.record(
        db,
        action="DELETE",
        table_name="merchants",
        record_id=merchant.id,
        actor_user_id=ctx.user.id,
        before=audit.snapshot(merchant),
    )
    return Ok(message="Comerciante eliminado.")


# --- Categories --------------------------------------------------------------
class CategoryOut(ApiModel):
    id: uuid.UUID
    code_en: str
    display_name_pt: str
    domain: str
    level: int
    parent_id: uuid.UUID | None
    brand_axis: bool


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    ctx: CurrentAuth,
    db: Db,
    domain: str | None = None,
    level: int | None = None,
    parent_id: uuid.UUID | None = None,
) -> list[CategoryOut]:
    stmt = select(Category).where(Category.is_deleted.is_(False))
    if domain:
        stmt = stmt.where(Category.domain == domain)
    if level:
        stmt = stmt.where(Category.level == level)
    if parent_id:
        stmt = stmt.where(Category.parent_id == parent_id)
    return [
        CategoryOut.model_validate(row)
        for row in db.scalars(stmt.order_by(Category.level, Category.display_name_pt)).all()
    ]


# --- Tags --------------------------------------------------------------------
class TagOut(ApiModel):
    id: uuid.UUID
    name: str
    color: str | None


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=16)


@router.get("/tags", response_model=list[TagOut])
def list_tags(ctx: CurrentAuth, db: Db) -> list[TagOut]:
    rows = db.scalars(
        select(Tag)
        .where(Tag.household_id == ctx.household_id, Tag.is_deleted.is_(False))
        .order_by(Tag.name)
    ).all()
    return [TagOut.model_validate(row) for row in rows]


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(payload: TagIn, ctx: Writer, db: Db) -> TagOut:
    if db.scalar(
        select(Tag).where(
            Tag.household_id == ctx.household_id,
            func.lower(Tag.name) == payload.name.strip().lower(),
            Tag.is_deleted.is_(False),
        )
    ):
        raise Conflict("Já existe uma etiqueta com este nome.")
    tag = Tag(household_id=ctx.household_id, name=payload.name.strip(), color=payload.color)
    db.add(tag)
    db.flush()
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", response_model=Ok)
def delete_tag(tag_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    tag = db.get(Tag, tag_id)
    if tag is None or tag.is_deleted or tag.household_id != ctx.household_id:
        raise NotFound("Etiqueta não encontrada.")
    tag.is_deleted = True
    return Ok(message="Etiqueta eliminada.")
