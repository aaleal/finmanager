from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import CurrentAuth, Db, Writer, household_entity_ids, resolve_write_entity
from app.core.errors import ValidationError
from app.schemas.common import Ok, Page
from app.schemas.lego import (
    ImageSource,
    LegoSetInstanceCreate,
    LegoSetInstanceOut,
    LegoSetInstanceUpdate,
    LegoSetModelCreate,
    LegoSetModelOut,
    LegoSetModelUpdate,
    LookupRequest,
    LookupResult,
    OverviewOut,
    StorageLocationCreate,
    StorageLocationOut,
    StorageLocationUpdate,
)
from app.services import lego_provider, lego_service

router = APIRouter(prefix="/lego", tags=["lego"])


# --- Overview ----------------------------------------------------------------
@router.get("/overview", response_model=OverviewOut)
def overview(ctx: CurrentAuth, db: Db) -> OverviewOut:
    return lego_service.overview(
        db,
        entity_ids=household_entity_ids(db, ctx),
        active_entity_id=ctx.active_entity_id,
    )


# --- Set models --------------------------------------------------------------
@router.get("/models", response_model=Page[LegoSetModelOut])
def list_models(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    theme: str | None = None,
    stale_only: bool = False,
    no_value_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[LegoSetModelOut]:
    items, total = lego_service.list_models(
        db,
        entity_ids=household_entity_ids(db, ctx),
        active_entity_id=ctx.active_entity_id,
        search=search,
        theme=theme,
        stale_only=stale_only,
        no_value_only=no_value_only,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/models", response_model=LegoSetModelOut, status_code=201)
def create_model(payload: LegoSetModelCreate, ctx: Writer, db: Db) -> LegoSetModelOut:
    entity_id = resolve_write_entity(db, ctx, payload.entity_id)
    model = lego_service.create_model(db, payload, entity_id=entity_id, actor_user_id=ctx.user.id)
    return lego_service.model_out(db, model)


@router.post("/models/lookup", response_model=LookupResult)
def lookup(payload: LookupRequest, ctx: CurrentAuth, db: Db) -> LookupResult:
    """Contacts Brickset only here — on an explicit user action (M9 guarantee)."""
    return lego_provider.get_provider(db).lookup(payload.set_number)


@router.get("/models/{model_id}", response_model=LegoSetModelOut)
def get_model(model_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> LegoSetModelOut:
    return lego_service.model_out(db, lego_service.get_model(db, model_id))


@router.get("/models/{model_id}/instances", response_model=list[LegoSetInstanceOut])
def model_instances(
    model_id: uuid.UUID,
    ctx: CurrentAuth,
    db: Db,
    ownership_status: str | None = None,
) -> list[LegoSetInstanceOut]:
    items, _ = lego_service.list_instances(
        db,
        entity_ids=household_entity_ids(db, ctx),
        active_entity_id=ctx.active_entity_id,
        model_id=model_id,
        ownership_status=ownership_status,
        limit=200,
    )
    return items


@router.patch("/models/{model_id}", response_model=LegoSetModelOut)
def update_model(
    model_id: uuid.UUID, payload: LegoSetModelUpdate, ctx: Writer, db: Db
) -> LegoSetModelOut:
    model = lego_service.get_model(db, model_id)
    lego_service.update_model(db, model, payload, actor_user_id=ctx.user.id)
    return lego_service.model_out(db, model)


@router.delete("/models/{model_id}", response_model=Ok)
def delete_model(model_id: uuid.UUID, ctx: Writer, db: Db, hard: bool = False) -> Ok:
    model = lego_service.get_model(db, model_id)
    lego_service.delete_model(db, model, hard=hard, actor_user_id=ctx.user.id)
    return Ok(message="Conjunto eliminado.")


@router.put("/models/{model_id}/image", response_model=LegoSetModelOut)
async def set_model_image(
    model_id: uuid.UUID,
    ctx: Writer,
    db: Db,
    url: str | None = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> LegoSetModelOut:
    model = lego_service.get_model(db, model_id)
    data = await file.read() if file is not None else None
    lego_service.set_model_image(
        db,
        model,
        url=ImageSource(url=url).url if url else None,
        data=data,
        filename=file.filename if file else None,
        actor_user_id=ctx.user.id,
    )
    return lego_service.model_out(db, model)


# --- Copies ------------------------------------------------------------------
@router.get("/instances", response_model=Page[LegoSetInstanceOut])
def list_instances(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    theme: str | None = None,
    storage_location_id: uuid.UUID | None = None,
    build_state: str | None = None,
    condition: str | None = None,
    ownership_status: str | None = "IN_COLLECTION",
    incomplete_only: bool = False,
    retired_only: bool = False,
    sort: str = "created_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[LegoSetInstanceOut]:
    items, total = lego_service.list_instances(
        db,
        entity_ids=household_entity_ids(db, ctx),
        active_entity_id=ctx.active_entity_id,
        search=search,
        theme=theme,
        storage_location_id=storage_location_id,
        build_state=build_state,
        condition=condition,
        ownership_status=ownership_status or None,
        incomplete_only=incomplete_only,
        retired_only=retired_only,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/instances", response_model=LegoSetInstanceOut, status_code=201)
def create_instance(payload: LegoSetInstanceCreate, ctx: Writer, db: Db) -> LegoSetInstanceOut:
    entity_id = resolve_write_entity(db, ctx, payload.entity_id)
    instance = lego_service.create_instance(
        db, payload, entity_id=entity_id, actor_user_id=ctx.user.id
    )
    return lego_service.instance_out(db, instance)


@router.get("/instances/{instance_id}", response_model=LegoSetInstanceOut)
def get_instance(instance_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> LegoSetInstanceOut:
    return lego_service.instance_out(db, lego_service.get_instance(db, instance_id))


@router.patch("/instances/{instance_id}", response_model=LegoSetInstanceOut)
def update_instance(
    instance_id: uuid.UUID, payload: LegoSetInstanceUpdate, ctx: Writer, db: Db
) -> LegoSetInstanceOut:
    instance = lego_service.get_instance(db, instance_id)
    lego_service.update_instance(db, instance, payload, actor_user_id=ctx.user.id)
    return lego_service.instance_out(db, instance)


@router.delete("/instances/{instance_id}", response_model=Ok)
def delete_instance(instance_id: uuid.UUID, ctx: Writer, db: Db, hard: bool = False) -> Ok:
    instance = lego_service.get_instance(db, instance_id)
    lego_service.delete_instance(db, instance, hard=hard, actor_user_id=ctx.user.id)
    return Ok(message="Cópia eliminada.")


@router.put("/instances/{instance_id}/photo", response_model=LegoSetInstanceOut)
async def set_instance_photo(
    instance_id: uuid.UUID,
    ctx: Writer,
    db: Db,
    url: str | None = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> LegoSetInstanceOut:
    instance = lego_service.get_instance(db, instance_id)
    data = await file.read() if file is not None else None
    if url is None and data is None:
        raise ValidationError("Indique um endereço de imagem ou carregue um ficheiro.")
    lego_service.set_instance_photo(
        db,
        instance,
        url=ImageSource(url=url).url if url else None,
        data=data,
        filename=file.filename if file else None,
        actor_user_id=ctx.user.id,
    )
    return lego_service.instance_out(db, instance)


# --- Storage -----------------------------------------------------------------
@router.get("/storage-locations", response_model=list[StorageLocationOut])
def list_storage(ctx: CurrentAuth, db: Db) -> list[StorageLocationOut]:
    return lego_service.list_storage_locations(
        db, entity_ids=household_entity_ids(db, ctx), active_entity_id=ctx.active_entity_id
    )


@router.post("/storage-locations", response_model=StorageLocationOut, status_code=201)
def create_storage(payload: StorageLocationCreate, ctx: Writer, db: Db) -> StorageLocationOut:
    entity_id = resolve_write_entity(db, ctx, payload.entity_id)
    location = lego_service.create_storage_location(
        db, payload, entity_id=entity_id, actor_user_id=ctx.user.id
    )
    return lego_service.storage_out(db, location)


@router.get("/storage-locations/{location_id}", response_model=StorageLocationOut)
def get_storage(location_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> StorageLocationOut:
    return lego_service.storage_out(db, lego_service.get_storage_location(db, location_id))


@router.patch("/storage-locations/{location_id}", response_model=StorageLocationOut)
def update_storage(
    location_id: uuid.UUID, payload: StorageLocationUpdate, ctx: Writer, db: Db
) -> StorageLocationOut:
    location = lego_service.get_storage_location(db, location_id)
    lego_service.update_storage_location(db, location, payload, actor_user_id=ctx.user.id)
    return lego_service.storage_out(db, location)


@router.delete("/storage-locations/{location_id}", response_model=Ok)
def delete_storage(location_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    location = lego_service.get_storage_location(db, location_id)
    lego_service.delete_storage_location(db, location, actor_user_id=ctx.user.id)
    return Ok(message="Local eliminado.")
