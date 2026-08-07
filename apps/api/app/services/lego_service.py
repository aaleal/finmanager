"""Module 9 service layer — all LEGO business rules live here.

Derived values (``appreciation_eur``, ``roi_pct``, ``owned_copies_count``,
``remaining_capacity_pct``) are computed on read; nothing is persisted.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from app.core import audit
from app.core.errors import Conflict, NotFound, ValidationError
from app.core.money import ZERO, appreciation_eur, roi_pct
from app.core.security import signed_document_url
from app.models.lego import LegoSetInstance, LegoSetModel, StorageLocation
from app.schemas.lego import (
    LegoSetInstanceCreate,
    LegoSetInstanceOut,
    LegoSetInstanceUpdate,
    LegoSetModelCreate,
    LegoSetModelOut,
    LegoSetModelUpdate,
    OverviewOut,
    StorageLocationCreate,
    StorageLocationOut,
    StorageLocationUpdate,
    ThemeBreakdown,
)
from app.services import documents, settings_service

MODEL_TABLE = "lego_set_models"
INSTANCE_TABLE = "lego_set_instances"
STORAGE_TABLE = "lego_storage_locations"


# --- Serialization -----------------------------------------------------------
def _model_out(
    model: LegoSetModel, *, stale_days: int, owned_copies_count: int = 0
) -> LegoSetModelOut:
    age_days: int | None = None
    if model.value_updated_at is not None:
        age_days = (dt.date.today() - model.value_updated_at).days
    stale = model.current_value_eur is None or age_days is None or age_days > stale_days

    return LegoSetModelOut(
        **{c.name: getattr(model, c.name) for c in model.__table__.columns},
        image_url=signed_document_url(model.image_document_id) if model.image_document_id else None,
        is_retired=model.retired_year is not None,
        value_is_stale=stale,
        value_age_days=age_days,
        owned_copies_count=owned_copies_count,
    )


def _instance_out(
    instance: LegoSetInstance,
    *,
    stale_days: int,
    copies_count: int = 0,
    include_model: bool = True,
) -> LegoSetInstanceOut:
    model = instance.model
    current_value = model.current_value_eur if model else None
    cost = instance.acquisition_cost_eur

    return LegoSetInstanceOut(
        **{c.name: getattr(instance, c.name) for c in instance.__table__.columns},
        photo_url=(
            signed_document_url(instance.photo_document_id) if instance.photo_document_id else None
        ),
        is_complete=instance.is_complete,
        current_value_eur=current_value,
        appreciation_eur=appreciation_eur(cost, current_value),
        roi_pct=roi_pct(cost, current_value),
        storage_label=instance.storage_location.label if instance.storage_location else None,
        set_model=(
            _model_out(model, stale_days=stale_days, owned_copies_count=copies_count)
            if (include_model and model)
            else None
        ),
    )


def _instances_out(
    db: DbSession, instances: list[LegoSetInstance], *, stale_days: int
) -> list[LegoSetInstanceOut]:
    counts = _copy_counts(db, [i.lego_set_model_id for i in instances])
    return [
        _instance_out(
            instance, stale_days=stale_days, copies_count=counts.get(instance.lego_set_model_id, 0)
        )
        for instance in instances
    ]


def _storage_out(
    location: StorageLocation, *, stored_count: int = 0, stored_value_eur: Decimal = ZERO
) -> StorageLocationOut:
    remaining = None if location.capacity_pct is None else 100 - location.capacity_pct
    return StorageLocationOut(
        id=location.id,
        entity_id=location.entity_id,
        area=location.area,
        container=location.container,
        description=location.description,
        capacity_pct=location.capacity_pct,
        label=location.label,
        stored_count=stored_count,
        stored_value_eur=stored_value_eur,
        remaining_capacity_pct=remaining,
        is_full=location.capacity_pct is not None and location.capacity_pct >= 100,
    )


# --- Scoping -----------------------------------------------------------------
def _scope(
    stmt: Select[Any], column: Any, entity_ids: list[uuid.UUID], active_entity_id: uuid.UUID | None
) -> Select[Any]:
    """Entity is a filter, not a boundary: default to the whole household."""
    if active_entity_id is not None:
        return stmt.where(column == active_entity_id)
    return stmt.where(column.in_(entity_ids))


# --- Set models --------------------------------------------------------------
def _copy_counts(db: DbSession, model_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not model_ids:
        return {}
    rows = db.execute(
        select(LegoSetInstance.lego_set_model_id, func.count())
        .where(
            LegoSetInstance.lego_set_model_id.in_(model_ids),
            LegoSetInstance.is_deleted.is_(False),
            LegoSetInstance.ownership_status == "IN_COLLECTION",
        )
        .group_by(LegoSetInstance.lego_set_model_id)
    ).all()
    return {row[0]: row[1] for row in rows}


def list_models(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    active_entity_id: uuid.UUID | None,
    search: str | None = None,
    theme: str | None = None,
    stale_only: bool = False,
    no_value_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[LegoSetModelOut], int]:
    stale_days = settings_service.stale_value_days(db)
    stmt = select(LegoSetModel).where(LegoSetModel.is_deleted.is_(False))
    stmt = _scope(stmt, LegoSetModel.entity_id, entity_ids, active_entity_id)

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                LegoSetModel.name.ilike(pattern),
                LegoSetModel.set_number.ilike(pattern),
                LegoSetModel.theme.ilike(pattern),
                LegoSetModel.short_description.ilike(pattern),
                LegoSetModel.notes.ilike(pattern),
            )
        )
    if theme:
        stmt = stmt.where(LegoSetModel.theme == theme)
    if no_value_only:
        stmt = stmt.where(LegoSetModel.current_value_eur.is_(None))
    if stale_only:
        cutoff = dt.date.today() - dt.timedelta(days=stale_days)
        stmt = stmt.where(
            or_(LegoSetModel.value_updated_at.is_(None), LegoSetModel.value_updated_at < cutoff)
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(stmt.order_by(LegoSetModel.name).limit(limit).offset(offset)).unique().all()
    )
    counts = _copy_counts(db, [r.id for r in rows])
    return (
        [
            _model_out(r, stale_days=stale_days, owned_copies_count=counts.get(r.id, 0))
            for r in rows
        ],
        total,
    )


def get_model(db: DbSession, model_id: uuid.UUID) -> LegoSetModel:
    model = db.get(LegoSetModel, model_id)
    if model is None or model.is_deleted:
        raise NotFound("Conjunto não encontrado.")
    return model


def model_out(db: DbSession, model: LegoSetModel) -> LegoSetModelOut:
    stale_days = settings_service.stale_value_days(db)
    counts = _copy_counts(db, [model.id])
    return _model_out(model, stale_days=stale_days, owned_copies_count=counts.get(model.id, 0))


def find_model_by_set_number(
    db: DbSession, entity_id: uuid.UUID, set_number: str
) -> LegoSetModel | None:
    return db.scalar(
        select(LegoSetModel).where(
            LegoSetModel.entity_id == entity_id,
            func.upper(LegoSetModel.set_number) == set_number.strip().upper(),
            LegoSetModel.is_deleted.is_(False),
        )
    )


def create_model(
    db: DbSession,
    payload: LegoSetModelCreate,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> LegoSetModel:
    if payload.set_number:
        existing = find_model_by_set_number(db, entity_id, payload.set_number)
        if existing is not None:
            raise Conflict(
                f"O conjunto {payload.set_number} já existe nesta entidade. "
                "Adicione outra cópia em vez de o duplicar.",
                model_id=str(existing.id),
            )

    data = payload.model_dump(exclude={"entity_id", "image_url"})
    if data.get("set_number"):
        data["set_number"] = str(data["set_number"]).strip().upper()
    model = LegoSetModel(entity_id=entity_id, **data)
    if model.current_value_eur is not None:
        model.value_updated_at = dt.date.today()

    if payload.image_url:
        model.image_document_id = documents.store_from_url(db, payload.image_url).id

    db.add(model)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name=MODEL_TABLE,
        record_id=model.id,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(model),
    )
    return model


def update_model(
    db: DbSession,
    model: LegoSetModel,
    payload: LegoSetModelUpdate,
    *,
    actor_user_id: uuid.UUID,
) -> LegoSetModel:
    before = audit.snapshot(model)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("set_number"):
        candidate = str(changes["set_number"]).strip().upper()
        clash = find_model_by_set_number(db, model.entity_id, candidate)
        if clash is not None and clash.id != model.id:
            raise Conflict(f"Já existe um conjunto {candidate} nesta entidade.")
        changes["set_number"] = candidate

    # FR-9.6: any hand-set value re-stamps its freshness date.
    if "current_value_eur" in changes and changes["current_value_eur"] != model.current_value_eur:
        model.value_updated_at = (
            dt.date.today() if changes["current_value_eur"] is not None else None
        )

    for field, value in changes.items():
        setattr(model, field, value)

    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=MODEL_TABLE,
        record_id=model.id,
        entity_id=model.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(model),
    )
    return model


def delete_model(
    db: DbSession, model: LegoSetModel, *, hard: bool, actor_user_id: uuid.UUID
) -> None:
    live_copies = db.scalar(
        select(func.count())
        .select_from(LegoSetInstance)
        .where(
            LegoSetInstance.lego_set_model_id == model.id,
            LegoSetInstance.is_deleted.is_(False),
        )
    )
    if live_copies:
        raise Conflict(
            f"Este conjunto tem {live_copies} cópia(s) registada(s). " "Elimine-as primeiro."
        )

    before = audit.snapshot(model)
    audit.record(
        db,
        action="DELETE",
        table_name=MODEL_TABLE,
        record_id=model.id,
        entity_id=model.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        reason="hard delete" if hard else "soft delete",
    )
    if hard:
        db.query(LegoSetInstance).filter(LegoSetInstance.lego_set_model_id == model.id).delete(
            synchronize_session=False
        )
        db.delete(model)
    else:
        model.is_deleted = True
        model.deleted_at = dt.datetime.now(dt.UTC)
    db.flush()


def set_model_image(
    db: DbSession,
    model: LegoSetModel,
    *,
    url: str | None = None,
    data: bytes | None = None,
    filename: str | None = None,
    actor_user_id: uuid.UUID,
) -> LegoSetModel:
    before = audit.snapshot(model)
    if url:
        document = documents.store_from_url(db, url)
    elif data is not None:
        document = documents.store_bytes(db, data, original_filename=filename)
    else:
        raise ValidationError("Indique um endereço de imagem ou carregue um ficheiro.")

    model.image_document_id = document.id
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=MODEL_TABLE,
        record_id=model.id,
        entity_id=model.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(model),
        reason="cover image set",
    )
    return model


# --- Instances ---------------------------------------------------------------
def _instance_query() -> Select[Any]:
    return select(LegoSetInstance).options(
        selectinload(LegoSetInstance.model), selectinload(LegoSetInstance.storage_location)
    )


def list_instances(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    active_entity_id: uuid.UUID | None,
    search: str | None = None,
    theme: str | None = None,
    storage_location_id: uuid.UUID | None = None,
    build_state: str | None = None,
    condition: str | None = None,
    ownership_status: str | None = "IN_COLLECTION",
    incomplete_only: bool = False,
    retired_only: bool = False,
    model_id: uuid.UUID | None = None,
    sort: str = "created_desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[LegoSetInstanceOut], int]:
    stale_days = settings_service.stale_value_days(db)
    stmt = (
        _instance_query()
        .join(LegoSetModel)
        .where(LegoSetInstance.is_deleted.is_(False), LegoSetModel.is_deleted.is_(False))
    )
    stmt = _scope(stmt, LegoSetInstance.entity_id, entity_ids, active_entity_id)

    if ownership_status:
        stmt = stmt.where(LegoSetInstance.ownership_status == ownership_status)
    if model_id:
        stmt = stmt.where(LegoSetInstance.lego_set_model_id == model_id)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                LegoSetModel.name.ilike(pattern),
                LegoSetModel.set_number.ilike(pattern),
                LegoSetModel.theme.ilike(pattern),
                LegoSetModel.short_description.ilike(pattern),
                LegoSetModel.notes.ilike(pattern),
                LegoSetInstance.notes.ilike(pattern),
            )
        )
    if theme:
        stmt = stmt.where(LegoSetModel.theme == theme)
    if storage_location_id:
        stmt = stmt.where(LegoSetInstance.storage_location_id == storage_location_id)
    if build_state:
        stmt = stmt.where(LegoSetInstance.build_state == build_state)
    if condition:
        stmt = stmt.where(LegoSetInstance.condition == condition)
    if incomplete_only:
        stmt = stmt.where(
            and_(
                LegoSetInstance.missing_parts.is_not(None),
                func.trim(LegoSetInstance.missing_parts) != "",
            )
        )
    if retired_only:
        stmt = stmt.where(LegoSetModel.retired_year.is_not(None))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order_options: dict[str, Any] = {
        "created_desc": LegoSetInstance.created_at.desc(),
        "created_asc": LegoSetInstance.created_at.asc(),
        "name_asc": LegoSetModel.name.asc(),
        "name_desc": LegoSetModel.name.desc(),
        "cost_desc": LegoSetInstance.acquisition_cost_eur.desc(),
        "cost_asc": LegoSetInstance.acquisition_cost_eur.asc(),
        "value_desc": LegoSetModel.current_value_eur.desc().nullslast(),
        "value_asc": LegoSetModel.current_value_eur.asc().nullsfirst(),
        "pieces_desc": LegoSetModel.piece_count.desc().nullslast(),
        "year_desc": LegoSetModel.release_year.desc().nullslast(),
    }
    order = order_options.get(sort, LegoSetInstance.created_at.desc())

    rows = list(db.scalars(stmt.order_by(order).limit(limit).offset(offset)).unique().all())
    return _instances_out(db, rows, stale_days=stale_days), total


def get_instance(db: DbSession, instance_id: uuid.UUID) -> LegoSetInstance:
    instance = db.scalar(_instance_query().where(LegoSetInstance.id == instance_id))
    if instance is None or instance.is_deleted:
        raise NotFound("Cópia não encontrada.")
    return instance


def instance_out(db: DbSession, instance: LegoSetInstance) -> LegoSetInstanceOut:
    return _instances_out(db, [instance], stale_days=settings_service.stale_value_days(db))[0]


def create_instance(
    db: DbSession,
    payload: LegoSetInstanceCreate,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> LegoSetInstance:
    if payload.lego_set_model_id is not None:
        model = get_model(db, payload.lego_set_model_id)
    else:
        assert payload.new_set is not None  # guaranteed by the schema validator
        draft = payload.new_set
        existing = (
            find_model_by_set_number(db, entity_id, draft.set_number) if draft.set_number else None
        )
        model = existing or create_model(
            db, draft, entity_id=entity_id, actor_user_id=actor_user_id
        )

    _validate_storage(db, payload.storage_location_id, entity_id)

    data = payload.model_dump(exclude={"entity_id", "lego_set_model_id", "new_set"})
    instance = LegoSetInstance(entity_id=entity_id, lego_set_model_id=model.id, **data)
    db.add(instance)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name=INSTANCE_TABLE,
        record_id=instance.id,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(instance),
    )
    db.flush()
    db.refresh(instance)
    return instance


def update_instance(
    db: DbSession,
    instance: LegoSetInstance,
    payload: LegoSetInstanceUpdate,
    *,
    actor_user_id: uuid.UUID,
) -> LegoSetInstance:
    before = audit.snapshot(instance)
    changes = payload.model_dump(
        exclude_unset=True, exclude={"clear_storage_location", "clear_transaction_link"}
    )
    status_changed = (
        "ownership_status" in changes and changes["ownership_status"] != instance.ownership_status
    )

    if changes.get("storage_location_id"):
        _validate_storage(db, changes["storage_location_id"], instance.entity_id)

    for field, value in changes.items():
        setattr(instance, field, value)

    if payload.clear_storage_location:
        instance.storage_location_id = None
    if payload.clear_transaction_link:
        instance.acquisition_transaction_id = None

    # FR-9.9: coming back into the collection wipes the sale record.
    if instance.ownership_status == "IN_COLLECTION":
        instance.sale_price_eur = None
        instance.sale_date = None

    db.flush()
    audit.record(
        db,
        action="STATUS_CHANGE" if status_changed else "UPDATE",
        table_name=INSTANCE_TABLE,
        record_id=instance.id,
        entity_id=instance.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(instance),
    )
    db.flush()
    db.refresh(instance)
    return instance


def delete_instance(
    db: DbSession, instance: LegoSetInstance, *, hard: bool, actor_user_id: uuid.UUID
) -> None:
    audit.record(
        db,
        action="DELETE",
        table_name=INSTANCE_TABLE,
        record_id=instance.id,
        entity_id=instance.entity_id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(instance),
        reason="hard delete" if hard else "soft delete",
    )
    if hard:
        db.delete(instance)
    else:
        instance.is_deleted = True
        instance.deleted_at = dt.datetime.now(dt.UTC)
    db.flush()


def set_instance_photo(
    db: DbSession,
    instance: LegoSetInstance,
    *,
    url: str | None = None,
    data: bytes | None = None,
    filename: str | None = None,
    actor_user_id: uuid.UUID,
) -> LegoSetInstance:
    before = audit.snapshot(instance)
    if url:
        document = documents.store_from_url(db, url)
    elif data is not None:
        document = documents.store_bytes(db, data, original_filename=filename)
    else:
        raise ValidationError("Indique um endereço de imagem ou carregue um ficheiro.")

    instance.photo_document_id = document.id
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=INSTANCE_TABLE,
        record_id=instance.id,
        entity_id=instance.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(instance),
        reason="photo set",
    )
    return instance


# --- Storage locations -------------------------------------------------------
def _validate_storage(db: DbSession, location_id: uuid.UUID | None, entity_id: uuid.UUID) -> None:
    if location_id is None:
        return
    location = db.get(StorageLocation, location_id)
    if location is None or location.is_deleted:
        raise NotFound("Local de arrumação não encontrado.")


def _location_stats(
    db: DbSession, location_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, Decimal]]:
    if not location_ids:
        return {}
    rows = db.execute(
        select(
            LegoSetInstance.storage_location_id,
            func.count(),
            func.coalesce(func.sum(LegoSetModel.current_value_eur), 0),
        )
        .join(LegoSetModel, LegoSetModel.id == LegoSetInstance.lego_set_model_id)
        .where(
            LegoSetInstance.storage_location_id.in_(location_ids),
            LegoSetInstance.is_deleted.is_(False),
            LegoSetInstance.ownership_status == "IN_COLLECTION",
        )
        .group_by(LegoSetInstance.storage_location_id)
    ).all()
    return {row[0]: (row[1], Decimal(row[2])) for row in rows}


def list_storage_locations(
    db: DbSession, *, entity_ids: list[uuid.UUID], active_entity_id: uuid.UUID | None
) -> list[StorageLocationOut]:
    stmt = select(StorageLocation).where(StorageLocation.is_deleted.is_(False))
    stmt = _scope(stmt, StorageLocation.entity_id, entity_ids, active_entity_id)
    rows = list(db.scalars(stmt.order_by(StorageLocation.area, StorageLocation.container)).all())
    stats = _location_stats(db, [r.id for r in rows])
    return [
        _storage_out(
            r,
            stored_count=stats.get(r.id, (0, ZERO))[0],
            stored_value_eur=stats.get(r.id, (0, ZERO))[1],
        )
        for r in rows
    ]


def get_storage_location(db: DbSession, location_id: uuid.UUID) -> StorageLocation:
    location = db.get(StorageLocation, location_id)
    if location is None or location.is_deleted:
        raise NotFound("Local de arrumação não encontrado.")
    return location


def storage_out(db: DbSession, location: StorageLocation) -> StorageLocationOut:
    stats = _location_stats(db, [location.id]).get(location.id, (0, ZERO))
    return _storage_out(location, stored_count=stats[0], stored_value_eur=stats[1])


def create_storage_location(
    db: DbSession,
    payload: StorageLocationCreate,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> StorageLocation:
    duplicate = db.scalar(
        select(StorageLocation).where(
            StorageLocation.entity_id == entity_id,
            StorageLocation.area == payload.area,
            StorageLocation.container.is_not_distinct_from(payload.container),
            StorageLocation.is_deleted.is_(False),
        )
    )
    if duplicate is not None:
        raise Conflict("Já existe um local de arrumação com esta área e contentor.")

    location = StorageLocation(entity_id=entity_id, **payload.model_dump(exclude={"entity_id"}))
    db.add(location)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name=STORAGE_TABLE,
        record_id=location.id,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(location),
    )
    return location


def update_storage_location(
    db: DbSession,
    location: StorageLocation,
    payload: StorageLocationUpdate,
    *,
    actor_user_id: uuid.UUID,
) -> StorageLocation:
    before = audit.snapshot(location)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=STORAGE_TABLE,
        record_id=location.id,
        entity_id=location.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(location),
    )
    return location


def delete_storage_location(
    db: DbSession, location: StorageLocation, *, actor_user_id: uuid.UUID
) -> None:
    assigned = db.scalar(
        select(func.count())
        .select_from(LegoSetInstance)
        .where(
            LegoSetInstance.storage_location_id == location.id,
            LegoSetInstance.is_deleted.is_(False),
            LegoSetInstance.ownership_status == "IN_COLLECTION",
        )
    )
    if assigned:
        raise Conflict(f"Este local tem {assigned} cópia(s) guardada(s). Mova-as primeiro.")
    audit.record(
        db,
        action="DELETE",
        table_name=STORAGE_TABLE,
        record_id=location.id,
        entity_id=location.entity_id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(location),
    )
    location.is_deleted = True
    location.deleted_at = dt.datetime.now(dt.UTC)
    db.flush()


# --- Overview ----------------------------------------------------------------
def overview(
    db: DbSession, *, entity_ids: list[uuid.UUID], active_entity_id: uuid.UUID | None
) -> OverviewOut:
    stale_days = settings_service.stale_value_days(db)
    scope_ids = [active_entity_id] if active_entity_id else entity_ids

    in_collection = (
        _instance_query()
        .join(LegoSetModel)
        .where(
            LegoSetInstance.entity_id.in_(scope_ids),
            LegoSetInstance.is_deleted.is_(False),
            LegoSetInstance.ownership_status == "IN_COLLECTION",
            LegoSetModel.is_deleted.is_(False),
        )
    )
    copies = list(db.scalars(in_collection).unique().all())

    total_cost = ZERO
    total_value = ZERO
    valued_cost = ZERO
    total_pieces = 0
    total_minifigs = 0
    themes: dict[str, dict[str, Any]] = {}
    seen_models: set[uuid.UUID] = set()
    retired_models: set[uuid.UUID] = set()
    models_without_value: set[uuid.UUID] = set()

    for copy in copies:
        model = copy.model
        total_cost += copy.acquisition_cost_eur
        if model.current_value_eur is not None:
            total_value += model.current_value_eur
            valued_cost += copy.acquisition_cost_eur
        else:
            models_without_value.add(model.id)
        total_pieces += model.piece_count or 0
        total_minifigs += model.minifig_count or 0
        seen_models.add(model.id)
        if model.retired_year is not None:
            retired_models.add(model.id)

        theme = model.theme or "Sem tema"
        bucket = themes.setdefault(
            theme, {"copies": 0, "models": set(), "cost": ZERO, "value": ZERO}
        )
        bucket["copies"] += 1
        bucket["models"].add(model.id)
        bucket["cost"] += copy.acquisition_cost_eur
        bucket["value"] += model.current_value_eur or ZERO

    gain = total_value - valued_cost
    overall_roi = roi_pct(valued_cost, total_value) if valued_cost > ZERO else None

    ranked = sorted(
        (c for c in copies if c.model.current_value_eur is not None),
        key=lambda c: (c.model.current_value_eur or ZERO) - c.acquisition_cost_eur,
        reverse=True,
    )
    top_gainers = _instances_out(db, ranked[:5], stale_days=stale_days)
    top_losers = _instances_out(db, list(reversed(ranked[-5:])), stale_days=stale_days)

    oldest_value = db.scalar(
        select(func.min(LegoSetModel.value_updated_at)).where(
            LegoSetModel.entity_id.in_(scope_ids),
            LegoSetModel.is_deleted.is_(False),
            LegoSetModel.current_value_eur.is_not(None),
        )
    )
    cutoff = dt.date.today() - dt.timedelta(days=stale_days)
    stale_models = (
        db.scalar(
            select(func.count())
            .select_from(LegoSetModel)
            .where(
                LegoSetModel.entity_id.in_(scope_ids),
                LegoSetModel.is_deleted.is_(False),
                LegoSetModel.current_value_eur.is_not(None),
                LegoSetModel.value_updated_at < cutoff,
            )
        )
        or 0
    )

    departed = db.execute(
        select(func.count(), func.coalesce(func.sum(LegoSetInstance.sale_price_eur), 0)).where(
            LegoSetInstance.entity_id.in_(scope_ids),
            LegoSetInstance.is_deleted.is_(False),
            LegoSetInstance.ownership_status.in_(("SOLD", "GIFTED")),
        )
    ).one()

    locations = list_storage_locations(db, entity_ids=entity_ids, active_entity_id=active_entity_id)

    return OverviewOut(
        total_cost_eur=total_cost,
        total_value_eur=total_value,
        unrealized_gain_eur=gain,
        roi_pct=overall_roi,
        unique_sets=len(seen_models),
        copies_owned=len(copies),
        total_pieces=total_pieces,
        total_minifigs=total_minifigs,
        retired_sets=len(retired_models),
        models_without_value=len(models_without_value),
        stale_value_models=stale_models,
        oldest_value_updated_at=oldest_value,
        stale_threshold_days=stale_days,
        departed_copies=departed[0],
        departed_sale_total_eur=Decimal(departed[1]),
        themes=sorted(
            (
                ThemeBreakdown(
                    theme=name,
                    copies=data["copies"],
                    unique_sets=len(data["models"]),
                    cost_eur=data["cost"],
                    value_eur=data["value"],
                )
                for name, data in themes.items()
            ),
            key=lambda t: t.value_eur,
            reverse=True,
        ),
        top_gainers=top_gainers,
        top_losers=top_losers,
        locations_full=sum(1 for loc in locations if loc.is_full),
        locations_total=len(locations),
    )
