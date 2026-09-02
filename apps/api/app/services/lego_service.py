"""Module 9 service layer — all LEGO business rules live here.

Derived values (``appreciation_eur``, ``roi_pct``, ``owned_copies_count``,
``remaining_capacity_pct``) are computed on read; nothing is persisted.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import aliased, selectinload

from app.core import audit
from app.core.config import settings as app_settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.core.money import ZERO, appreciation_eur, roi_pct
from app.core.security import signed_document_url
from app.models.lego import (
    BUILD_STATES,
    CONDITIONS,
    LegoSetImage,
    LegoSetInstance,
    LegoSetInstruction,
    LegoSetModel,
    StorageLocation,
)
from app.schemas.lego import (
    CollectionSummary,
    CompletenessFilter,
    CopiesFilter,
    LegoSetImageOut,
    LegoSetImageUpdate,
    LegoSetInstanceCreate,
    LegoSetInstanceOut,
    LegoSetInstanceUpdate,
    LegoSetInstructionOut,
    LegoSetModelCreate,
    LegoSetModelOut,
    LegoSetModelUpdate,
    OverviewOut,
    RetirementFilter,
    StorageLocationCreate,
    StorageLocationOut,
    StorageLocationUpdate,
    ThemeBreakdown,
    TimelinePoint,
)
from app.services import documents, lego_provider, settings_service

MODEL_TABLE = "lego_set_models"
INSTANCE_TABLE = "lego_set_instances"
STORAGE_TABLE = "lego_storage_locations"
IMAGE_TABLE = "lego_set_images"
INSTRUCTION_TABLE = "lego_set_instructions"


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
        images=[
            LegoSetImageOut(
                id=image.id,
                document_id=image.document_id,
                url=signed_document_url(image.document_id),
                caption=image.caption,
                position=image.position,
            )
            for image in model.images
        ],
        instructions=[
            LegoSetInstructionOut(
                id=manual.id,
                document_id=manual.document_id,
                url=signed_document_url(manual.document_id),
                description=manual.description,
                language=manual.language,
                position=manual.position,
            )
            for manual in model.instructions
        ],
        is_retired=model.is_retired,
        release_year=model.release_date.year if model.release_date else None,
        retired_year=model.retirement_date.year if model.retirement_date else None,
        value_is_stale=stale,
        value_age_days=age_days,
        owned_copies_count=owned_copies_count,
        rrp_appreciation_eur=appreciation_eur(model.rrp_eur, model.current_value_eur),
        rrp_roi_pct=roi_pct(model.rrp_eur, model.current_value_eur),
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
        display_image_url=(
            signed_document_url(instance.display_image_document_id)
            if instance.display_image_document_id
            else None
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
    counts = copy_counts(db, [i.lego_set_model_id for i in instances])
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
def copy_counts(db: DbSession, model_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
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
    counts = copy_counts(db, [r.id for r in rows])
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
    counts = copy_counts(db, [model.id])
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

    # A partial update may supply only one of the two dates, so the pair is checked
    # against the row as it will end up, not against the payload alone.
    release = changes.get("release_date", model.release_date)
    retirement = changes.get("retirement_date", model.retirement_date)
    if release is not None and retirement is not None and retirement < release:
        raise ValidationError("A data de retirada não pode ser anterior à data de lançamento.")

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


# --- Set gallery -------------------------------------------------------------
def _next_image_position(db: DbSession, model_id: uuid.UUID) -> int:
    highest = db.scalar(
        select(func.max(LegoSetImage.position)).where(LegoSetImage.lego_set_model_id == model_id)
    )
    return 0 if highest is None else highest + 1


def add_model_image(
    db: DbSession,
    model: LegoSetModel,
    *,
    url: str | None = None,
    data: bytes | None = None,
    filename: str | None = None,
    caption: str | None = None,
    actor_user_id: uuid.UUID,
) -> LegoSetImage:
    if url:
        document = documents.store_from_url(db, url)
    elif data is not None:
        document = documents.store_bytes(db, data, original_filename=filename)
    else:
        raise ValidationError("Indique um endereço de imagem ou carregue um ficheiro.")

    # Documents are content-addressed, so the same file uploaded twice is one row.
    existing = db.scalar(
        select(LegoSetImage).where(
            LegoSetImage.lego_set_model_id == model.id,
            LegoSetImage.document_id == document.id,
        )
    )
    if existing is not None:
        raise Conflict("Esta imagem já faz parte da galeria deste conjunto.")
    if model.image_document_id == document.id:
        raise Conflict("Esta imagem já é a imagem principal deste conjunto.")

    image = LegoSetImage(
        lego_set_model_id=model.id,
        document_id=document.id,
        position=_next_image_position(db, model.id),
        caption=caption,
    )
    db.add(image)
    db.flush()
    db.refresh(model)
    audit.record(
        db,
        action="CREATE",
        table_name=IMAGE_TABLE,
        record_id=image.id,
        entity_id=model.entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(image),
    )
    return image


def get_model_image(db: DbSession, image_id: uuid.UUID) -> LegoSetImage:
    image = db.get(LegoSetImage, image_id)
    if image is None:
        raise NotFound("Imagem não encontrada.")
    return image


def update_model_image(
    db: DbSession,
    image: LegoSetImage,
    payload: LegoSetImageUpdate,
    *,
    actor_user_id: uuid.UUID,
) -> LegoSetImage:
    before = audit.snapshot(image)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(image, field, value)
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=IMAGE_TABLE,
        record_id=image.id,
        entity_id=image.model.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(image),
    )
    return image


def promote_model_image(
    db: DbSession, image: LegoSetImage, *, actor_user_id: uuid.UUID
) -> LegoSetModel:
    """Mark a gallery image as the box shot.

    Nothing moves: `image` keeps its row and its position — only the model's
    cover pointer changes. The previous cover, if it was not already in the
    gallery itself, is appended there so it is never lost (ADR-0013's promise);
    if it already was, it simply stays exactly where it already sat.
    """
    model = image.model
    before = audit.snapshot(model)
    previous_cover = model.image_document_id

    model.image_document_id = image.document_id
    db.flush()

    if previous_cover is not None and previous_cover != image.document_id:
        already_in_gallery = db.scalar(
            select(LegoSetImage).where(
                LegoSetImage.lego_set_model_id == model.id,
                LegoSetImage.document_id == previous_cover,
            )
        )
        if already_in_gallery is None:
            db.add(
                LegoSetImage(
                    lego_set_model_id=model.id,
                    document_id=previous_cover,
                    position=_next_image_position(db, model.id),
                )
            )
    db.flush()
    db.refresh(model)
    audit.record(
        db,
        action="UPDATE",
        table_name=MODEL_TABLE,
        record_id=model.id,
        entity_id=model.entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(model),
        reason="cover changed",
    )
    return model


def delete_model_image(db: DbSession, image: LegoSetImage, *, actor_user_id: uuid.UUID) -> None:
    audit.record(
        db,
        action="DELETE",
        table_name=IMAGE_TABLE,
        record_id=image.id,
        entity_id=image.model.entity_id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(image),
    )
    # The Document row itself stays: it is content-addressed and may be shared.
    db.delete(image)
    db.flush()


# --- Instruction manuals -----------------------------------------------------
def _next_instruction_position(db: DbSession, model_id: uuid.UUID) -> int:
    highest = db.scalar(
        select(func.max(LegoSetInstruction.position)).where(
            LegoSetInstruction.lego_set_model_id == model_id
        )
    )
    return 0 if highest is None else highest + 1


def add_model_instruction(
    db: DbSession,
    model: LegoSetModel,
    *,
    url: str | None = None,
    data: bytes | None = None,
    filename: str | None = None,
    description: str,
    language: str | None = None,
    actor_user_id: uuid.UUID,
) -> LegoSetInstruction:
    """Add one manual by hand — a household scan, or a link Brickset doesn't carry.

    Same identity rule as the Brickset import (ADR-0043): the description is what
    makes a manual unique for this set, not the file.
    """
    if any(manual.description == description for manual in model.instructions):
        raise Conflict("Já existe um manual com esta descrição para este conjunto.")

    if url:
        document = documents.store_from_url(
            db,
            url,
            max_bytes=app_settings.max_instruction_bytes,
            original_filename=f"{description}.pdf",
        )
    elif data is not None:
        document = documents.store_bytes(
            db,
            data,
            max_bytes=app_settings.max_instruction_bytes,
            original_filename=filename or f"{description}.pdf",
        )
    else:
        raise ValidationError("Indique um endereço do manual ou carregue um ficheiro.")

    manual = LegoSetInstruction(
        lego_set_model_id=model.id,
        document_id=document.id,
        description=description,
        language=language,
        position=_next_instruction_position(db, model.id),
    )
    db.add(manual)
    db.flush()
    db.refresh(model)
    audit.record(
        db,
        action="CREATE",
        table_name=INSTRUCTION_TABLE,
        record_id=manual.id,
        entity_id=model.entity_id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(manual),
    )
    return manual


def get_model_instruction(db: DbSession, instruction_id: uuid.UUID) -> LegoSetInstruction:
    manual = db.get(LegoSetInstruction, instruction_id)
    if manual is None:
        raise NotFound("Manual não encontrado.")
    return manual


def delete_model_instruction(
    db: DbSession, manual: LegoSetInstruction, *, actor_user_id: uuid.UUID
) -> None:
    audit.record(
        db,
        action="DELETE",
        table_name=INSTRUCTION_TABLE,
        record_id=manual.id,
        entity_id=manual.model.entity_id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(manual),
    )
    db.delete(manual)
    db.flush()


def import_from_brickset(
    db: DbSession, model: LegoSetModel, *, actor_user_id: uuid.UUID
) -> tuple[int, int, str | None]:
    """Pull the set's extra photographs and its manuals down onto this disk.

    Contacts Brickset only from here, on an explicit press. Whatever is already
    stored is left alone, so pressing twice costs nothing (ADR-0040).
    """
    provider = lego_provider.get_provider(db)
    if not getattr(provider, "enabled", False):
        raise ValidationError(lego_provider.DISABLED_MESSAGE)
    if not model.set_number:
        raise ValidationError("Um MOC não existe no Brickset.")

    try:
        remote_images = provider.additional_images(model.set_number)
        remote_manuals = provider.instructions(model.set_number)
    except (httpx.HTTPError, ValueError) as exc:
        raise ValidationError(
            f"Brickset indisponível ({exc.__class__.__name__}). Tente novamente mais tarde."
        ) from exc

    images_added = _import_images(db, model, remote_images, actor_user_id=actor_user_id)
    manuals_added = _import_instructions(db, model, remote_manuals, actor_user_id=actor_user_id)
    db.refresh(model)

    message = None
    if not images_added and not manuals_added:
        message = "Nada de novo no Brickset para este conjunto."
    return images_added, manuals_added, message


def _import_images(
    db: DbSession,
    model: LegoSetModel,
    remote: list[lego_provider.RemoteImage],
    *,
    actor_user_id: uuid.UUID,
) -> int:
    added = 0
    for image in remote:
        try:
            document = documents.store_from_url(db, image.url)
        except ValidationError:
            # One unreachable photograph must not abandon the whole import.
            continue
        if document.id == model.image_document_id:
            continue
        clash = db.scalar(
            select(LegoSetImage).where(
                LegoSetImage.lego_set_model_id == model.id,
                LegoSetImage.document_id == document.id,
            )
        )
        if clash is not None:
            continue
        row = LegoSetImage(
            lego_set_model_id=model.id,
            document_id=document.id,
            position=_next_image_position(db, model.id),
        )
        db.add(row)
        db.flush()
        audit.record(
            db,
            action="CREATE",
            table_name=IMAGE_TABLE,
            record_id=row.id,
            entity_id=model.entity_id,
            actor_user_id=actor_user_id,
            after=audit.snapshot(row),
            reason="brickset import",
        )
        added += 1
    return added


def _import_instructions(
    db: DbSession,
    model: LegoSetModel,
    remote: list[lego_provider.RemoteInstruction],
    *,
    actor_user_id: uuid.UUID,
) -> int:
    position = db.scalar(
        select(func.max(LegoSetInstruction.position)).where(
            LegoSetInstruction.lego_set_model_id == model.id
        )
    )
    position = 0 if position is None else position + 1
    seen_descriptions = {manual.description for manual in model.instructions}

    added = 0
    for manual in remote:
        # The description is the manual's real identity: Brickset re-serves the
        # same booklet with different bytes on every download, so a content hash
        # alone lets the same manual back in under a fresh document (ADR-0042).
        if manual.description in seen_descriptions:
            continue
        try:
            document = documents.store_from_url(
                db,
                manual.url,
                max_bytes=app_settings.max_instruction_bytes,
                original_filename=f"{manual.description}.pdf",
            )
        except ValidationError:
            continue
        clash = db.scalar(
            select(LegoSetInstruction).where(
                LegoSetInstruction.lego_set_model_id == model.id,
                LegoSetInstruction.document_id == document.id,
            )
        )
        if clash is not None:
            continue
        row = LegoSetInstruction(
            lego_set_model_id=model.id,
            document_id=document.id,
            description=manual.description,
            language=manual.language,
            position=position,
        )
        db.add(row)
        db.flush()
        audit.record(
            db,
            action="CREATE",
            table_name=INSTRUCTION_TABLE,
            record_id=row.id,
            entity_id=model.entity_id,
            actor_user_id=actor_user_id,
            after=audit.snapshot(row),
            reason="brickset import",
        )
        seen_descriptions.add(manual.description)
        position += 1
        added += 1
    return added


# --- Instances ---------------------------------------------------------------
def _instance_query() -> Select[Any]:
    return select(LegoSetInstance).options(
        selectinload(LegoSetInstance.model), selectinload(LegoSetInstance.storage_location)
    )


def _owned_copies_expr() -> Any:
    """Copies of the same set still in the collection, as a scalar subquery."""
    sibling = aliased(LegoSetInstance)
    return (
        select(func.count())
        .select_from(sibling)
        .where(
            sibling.lego_set_model_id == LegoSetInstance.lego_set_model_id,
            sibling.is_deleted.is_(False),
            sibling.ownership_status == "IN_COLLECTION",
        )
        .scalar_subquery()
    )


def _roi_expr() -> Any:
    """The same rule as ``roi_pct``: no cost basis and no value both mean NULL."""
    return case(
        (
            and_(
                LegoSetInstance.acquisition_cost_eur > 0,
                LegoSetModel.current_value_eur.is_not(None),
            ),
            (LegoSetModel.current_value_eur - LegoSetInstance.acquisition_cost_eur)
            / LegoSetInstance.acquisition_cost_eur,
        ),
        else_=None,
    )


def _ordinal_expr(column: Any, order: tuple[str, ...]) -> Any:
    """Rank a quality/lifecycle scale by meaning rather than alphabetically."""
    return case({value: rank for rank, value in enumerate(order)}, value=column, else_=None)


# Every column the grid renders is sortable, plus the two things it does not show
# (when the copy was added, and how many minifigures the set has). Direction is
# chosen separately, so the UI needs one entry per field and an asc/desc toggle.
SORT_FIELDS: dict[str, Any] = {
    "created": LegoSetInstance.created_at,
    "number": LegoSetModel.set_number,
    "name": LegoSetModel.name,
    "theme": LegoSetModel.theme,
    "pieces": LegoSetModel.piece_count,
    "minifigs": LegoSetModel.minifig_count,
    "year": LegoSetModel.release_date,
    "retired": LegoSetModel.retirement_date,
    "copies": _owned_copies_expr(),
    "storage": StorageLocation.area,
    "state": _ordinal_expr(LegoSetInstance.build_state, BUILD_STATES),
    "condition": _ordinal_expr(LegoSetInstance.condition, CONDITIONS),
    "acquired": LegoSetInstance.acquisition_date,
    "cost": LegoSetInstance.acquisition_cost_eur,
    "rrp": LegoSetModel.rrp_eur,
    "value": LegoSetModel.current_value_eur,
    "roi": _roi_expr(),
    "ownership": LegoSetInstance.ownership_status,
}

# The second key breaks ties so that paging is stable: without it Postgres is free
# to return a different row order for equal values on every page.
_TIEBREAK = LegoSetInstance.created_at.desc()


def _retired_clause() -> Any:
    """A set is retired only once its retirement date has arrived."""
    return and_(
        LegoSetModel.retirement_date.is_not(None),
        LegoSetModel.retirement_date <= dt.date.today(),
    )


def _order_by(sort: str, direction: str) -> list[Any]:
    """Resolve ``sort``/``direction`` into an ORDER BY clause.

    Legacy combined values (``value_desc``) are still understood so bookmarked
    URLs keep working.
    """
    field, _, suffix = sort.partition("_")
    if suffix in ("asc", "desc"):
        direction = suffix
    column = SORT_FIELDS.get(field, LegoSetInstance.created_at)
    # NULLs are absent data, never "the smallest" — they belong at the bottom.
    primary = column.desc().nullslast() if direction == "desc" else column.asc().nullslast()
    return [primary, _TIEBREAK]


def list_instances(
    db: DbSession,
    *,
    entity_ids: list[uuid.UUID],
    active_entity_id: uuid.UUID | None,
    search: str | None = None,
    theme: str | None = None,
    storage_location_id: uuid.UUID | None = None,
    storage_area: str | None = None,
    build_state: str | None = None,
    condition: str | None = None,
    ownership_status: str | None = "IN_COLLECTION",
    completeness: CompletenessFilter = "all",
    retirement: RetirementFilter = "all",
    copies: CopiesFilter = "all",
    model_id: uuid.UUID | None = None,
    sort: str = "created",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[LegoSetInstanceOut], int, CollectionSummary]:
    stale_days = settings_service.stale_value_days(db)
    stmt = (
        _instance_query()
        .join(LegoSetModel)
        # Outer, and with an explicit ON clause, so copies with no place still show
        # and «sort by arrumação» has a column to order on.
        .outerjoin(StorageLocation, LegoSetInstance.storage_location_id == StorageLocation.id)
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
    if storage_area:
        # "Everything in the garage" — the table stays flat; only the filter is
        # hierarchical (M9.1).
        stmt = stmt.where(
            LegoSetInstance.storage_location_id.in_(
                select(StorageLocation.id).where(
                    StorageLocation.area == storage_area,
                    StorageLocation.is_deleted.is_(False),
                )
            )
        )
    if build_state:
        stmt = stmt.where(LegoSetInstance.build_state == build_state)
    if condition:
        stmt = stmt.where(LegoSetInstance.condition == condition)

    has_missing_parts = and_(
        LegoSetInstance.missing_parts.is_not(None),
        func.trim(LegoSetInstance.missing_parts) != "",
    )
    if completeness == "incomplete":
        stmt = stmt.where(has_missing_parts)
    elif completeness == "complete":
        stmt = stmt.where(~has_missing_parts)

    if retirement == "retired":
        stmt = stmt.where(_retired_clause())
    elif retirement == "available":
        stmt = stmt.where(~_retired_clause())

    if copies == "multiple":
        stmt = stmt.where(_owned_copies_expr() > 1)
    elif copies == "single":
        stmt = stmt.where(_owned_copies_expr() <= 1)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    summary = _collection_summary(db, stmt, total)

    rows = list(
        db.scalars(stmt.order_by(*_order_by(sort, direction)).limit(limit).offset(offset))
        .unique()
        .all()
    )
    return _instances_out(db, rows, stale_days=stale_days), total, summary


def _collection_summary(db: DbSession, stmt: Select[Any], total: int) -> CollectionSummary:
    """Totals across every copy matching the filters, not just the current page."""
    matched = stmt.subquery()
    row = db.execute(
        select(
            func.count(func.distinct(matched.c.lego_set_model_id)),
            func.coalesce(func.sum(matched.c.acquisition_cost_eur), 0),
            func.coalesce(func.sum(LegoSetModel.current_value_eur), 0),
            func.coalesce(func.sum(LegoSetModel.piece_count), 0),
        )
        .select_from(matched)
        .join(LegoSetModel, LegoSetModel.id == matched.c.lego_set_model_id)
    ).one()
    return CollectionSummary(
        copies=total,
        unique_sets=row[0],
        total_cost_eur=Decimal(row[1]),
        total_value_eur=Decimal(row[2]),
        total_pieces=int(row[3]),
    )


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


def set_instance_display_image(
    db: DbSession,
    instance: LegoSetInstance,
    document_id: uuid.UUID | None,
    *,
    actor_user_id: uuid.UUID,
) -> LegoSetInstance:
    """Pick which of the *set's* own images (cover or gallery) stands for this copy
    in the table — `None` clears the pick, falling back to the collection's cover."""
    if document_id is not None:
        model = instance.model
        available = {model.image_document_id, *(image.document_id for image in model.images)}
        if document_id not in available:
            raise ValidationError("Escolha uma imagem já associada a este conjunto.")

    before = audit.snapshot(instance)
    instance.display_image_document_id = document_id
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
        reason="display image set",
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
def _timeline(copies: list[LegoSetInstance]) -> tuple[list[TimelinePoint], int]:
    """Cumulative acquisition curve, by month of ``acquisition_date``.

    Copies and cost are genuine history. ``value_eur`` is **today's** market value
    of everything owned up to that month — the module keeps a single hand-set value
    per set and no snapshot table (ADR-0008), so a real price history cannot exist.
    Copies without an acquisition date are counted apart and never guessed into a
    bucket.
    """
    buckets: dict[str, dict[str, Any]] = {}
    undated = 0

    for copy in copies:
        if copy.acquisition_date is None:
            undated += 1
            continue
        month = copy.acquisition_date.strftime("%Y-%m")
        bucket = buckets.setdefault(month, {"copies": 0, "cost": ZERO, "value": ZERO})
        bucket["copies"] += 1
        bucket["cost"] += copy.acquisition_cost_eur
        bucket["value"] += copy.model.current_value_eur or ZERO

    points: list[TimelinePoint] = []
    running_copies = 0
    running_cost = ZERO
    running_value = ZERO
    for month in sorted(buckets):
        bucket = buckets[month]
        running_copies += bucket["copies"]
        running_cost += bucket["cost"]
        running_value += bucket["value"]
        points.append(
            TimelinePoint(
                month=month,
                copies=running_copies,
                cost_eur=running_cost,
                value_eur=running_value,
            )
        )
    return points, undated


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
        if model.is_retired:
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
    timeline, copies_without_date = _timeline(copies)

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
        timeline=timeline,
        copies_without_date=copies_without_date,
        top_gainers=top_gainers,
        top_losers=top_losers,
        locations_full=sum(1 for loc in locations if loc.is_full),
        locations_total=len(locations),
    )
