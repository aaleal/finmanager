from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAuth, Db, Writer, household_entity_ids, resolve_write_entity
from app.core.errors import ValidationError
from app.schemas.common import Ok, Page
from app.schemas.lego import (
    BricksetImportOut,
    BricksetJobOut,
    BulkImportCommitIn,
    BulkImportPreviewOut,
    BulkImportRowResult,
    CompletenessFilter,
    CopiesFilter,
    FsFilter,
    ImageSource,
    InstanceDisplayImageUpdate,
    LegoSetImageUpdate,
    LegoSetInstanceCreate,
    LegoSetInstanceOut,
    LegoSetInstancePage,
    LegoSetInstanceUpdate,
    LegoSetModelCreate,
    LegoSetModelOut,
    LegoSetModelUpdate,
    LookupRequest,
    LookupResult,
    OverviewOut,
    RetirementFilter,
    StorageBulkImportOut,
    StorageLocationCreate,
    StorageLocationOut,
    StorageLocationUpdate,
)
from app.services import lego_brickset_jobs, lego_bulk_import, lego_provider, lego_service

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
    items, _, _ = lego_service.list_instances(
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


@router.post("/models/{model_id}/images", response_model=LegoSetModelOut, status_code=201)
async def add_model_image(
    model_id: uuid.UUID,
    ctx: Writer,
    db: Db,
    url: str | None = None,
    caption: str | None = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> LegoSetModelOut:
    """Add one more view of the set. The box shot stays the cover until promoted."""
    model = lego_service.get_model(db, model_id)
    data = await file.read() if file is not None else None
    if url is None and data is None:
        raise ValidationError("Indique um endereço de imagem ou carregue um ficheiro.")
    lego_service.add_model_image(
        db,
        model,
        url=ImageSource(url=url).url if url else None,
        data=data,
        filename=file.filename if file else None,
        caption=caption,
        actor_user_id=ctx.user.id,
    )
    return lego_service.model_out(db, model)


@router.post("/models/{model_id}/instructions", response_model=LegoSetModelOut, status_code=201)
async def add_model_instruction(
    model_id: uuid.UUID,
    ctx: Writer,
    db: Db,
    description: str,
    url: str | None = None,
    language: str | None = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> LegoSetModelOut:
    """Add one manual by hand — a household scan, or a link Brickset doesn't carry."""
    model = lego_service.get_model(db, model_id)
    data = await file.read() if file is not None else None
    if url is None and data is None:
        raise ValidationError("Indique um endereço do manual ou carregue um ficheiro.")
    lego_service.add_model_instruction(
        db,
        model,
        url=ImageSource(url=url).url if url else None,
        data=data,
        filename=file.filename if file else None,
        description=description,
        language=language,
        actor_user_id=ctx.user.id,
    )
    return lego_service.model_out(db, model)


@router.patch("/models/{model_id}/images/{image_id}", response_model=LegoSetModelOut)
def update_model_image(
    model_id: uuid.UUID,
    image_id: uuid.UUID,
    payload: LegoSetImageUpdate,
    ctx: Writer,
    db: Db,
) -> LegoSetModelOut:
    model = lego_service.get_model(db, model_id)
    lego_service.update_model_image(
        db, lego_service.get_model_image(db, image_id), payload, actor_user_id=ctx.user.id
    )
    return lego_service.model_out(db, model)


@router.post("/models/{model_id}/images/{image_id}/cover", response_model=LegoSetModelOut)
def promote_model_image(
    model_id: uuid.UUID, image_id: uuid.UUID, ctx: Writer, db: Db
) -> LegoSetModelOut:
    lego_service.get_model(db, model_id)
    model = lego_service.promote_model_image(
        db, lego_service.get_model_image(db, image_id), actor_user_id=ctx.user.id
    )
    return lego_service.model_out(db, model)


@router.delete("/models/{model_id}/images/{image_id}", response_model=LegoSetModelOut)
def delete_model_image(
    model_id: uuid.UUID, image_id: uuid.UUID, ctx: Writer, db: Db
) -> LegoSetModelOut:
    model = lego_service.get_model(db, model_id)
    lego_service.delete_model_image(
        db, lego_service.get_model_image(db, image_id), actor_user_id=ctx.user.id
    )
    db.refresh(model)
    return lego_service.model_out(db, model)


@router.post("/models/{model_id}/brickset", response_model=BricksetImportOut)
def import_from_brickset(model_id: uuid.UUID, ctx: Writer, db: Db) -> BricksetImportOut:
    """Download the set's extra photographs and manuals — on this press only."""
    model = lego_service.get_model(db, model_id)
    images, instructions, message = lego_service.import_from_brickset(
        db, model, actor_user_id=ctx.user.id
    )
    return BricksetImportOut(
        model=lego_service.model_out(db, model),
        images_added=images,
        instructions_added=instructions,
        message=message,
    )


@router.post("/models/{model_id}/brickset/queue", response_model=list[BricksetJobOut])
def queue_model_brickset_assets(model_id: uuid.UUID, ctx: Writer, db: Db) -> list[BricksetJobOut]:
    """Queues the images + manuals fetch as two background jobs instead of
    downloading them inline (ADR-0049) — this is what the automatic import
    fired once from set creation calls now, both from the manual add-set form
    and from bulk import."""
    model = lego_service.get_model(db, model_id)
    jobs = lego_brickset_jobs.queue_brickset_assets(db, model, actor_user_id=ctx.user.id)
    return [lego_brickset_jobs.job_out(job) for job in jobs]


@router.get("/brickset-jobs", response_model=list[BricksetJobOut])
def list_brickset_jobs(ctx: CurrentAuth, db: Db) -> list[BricksetJobOut]:
    """Visibility into every background images/manuals fetch for this household."""
    jobs = lego_brickset_jobs.list_jobs(db, entity_ids=household_entity_ids(db, ctx))
    return [lego_brickset_jobs.job_out(job) for job in jobs]


@router.post("/brickset-jobs/{job_id}/cancel", response_model=BricksetJobOut)
def cancel_brickset_job(job_id: uuid.UUID, ctx: Writer, db: Db) -> BricksetJobOut:
    job = lego_brickset_jobs.get_job(db, job_id, entity_ids=household_entity_ids(db, ctx))
    lego_brickset_jobs.cancel_job(db, job)
    return lego_brickset_jobs.job_out(job)


@router.post("/brickset-jobs/{job_id}/retry", response_model=BricksetJobOut)
def retry_brickset_job(job_id: uuid.UUID, ctx: Writer, db: Db) -> BricksetJobOut:
    job = lego_brickset_jobs.get_job(db, job_id, entity_ids=household_entity_ids(db, ctx))
    lego_brickset_jobs.retry_job(db, job)
    return lego_brickset_jobs.job_out(job)


@router.delete("/models/{model_id}/instructions/{instruction_id}", response_model=LegoSetModelOut)
def delete_model_instruction(
    model_id: uuid.UUID, instruction_id: uuid.UUID, ctx: Writer, db: Db
) -> LegoSetModelOut:
    model = lego_service.get_model(db, model_id)
    lego_service.delete_model_instruction(
        db, lego_service.get_model_instruction(db, instruction_id), actor_user_id=ctx.user.id
    )
    db.refresh(model)
    return lego_service.model_out(db, model)


# --- Copies ------------------------------------------------------------------
@router.get("/instances", response_model=LegoSetInstancePage)
def list_instances(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    theme: str | None = None,
    storage_location_id: uuid.UUID | None = None,
    storage_area: str | None = None,
    build_state: str | None = None,
    condition: str | None = None,
    acquisition_source: str | None = None,
    ownership_status: str | None = "IN_COLLECTION",
    completeness: CompletenessFilter = "all",
    retirement: RetirementFilter = "all",
    copies: CopiesFilter = "all",
    fs: FsFilter = "all",
    paid_min: Decimal | None = None,
    paid_max: Decimal | None = None,
    rrp_min: Decimal | None = None,
    rrp_max: Decimal | None = None,
    roi_min: Decimal | None = None,
    roi_max: Decimal | None = None,
    sort: str = "created",
    direction: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> LegoSetInstancePage:
    items, total, summary = lego_service.list_instances(
        db,
        entity_ids=household_entity_ids(db, ctx),
        active_entity_id=ctx.active_entity_id,
        search=search,
        theme=theme,
        storage_location_id=storage_location_id,
        storage_area=storage_area,
        build_state=build_state,
        condition=condition,
        acquisition_source=acquisition_source,
        ownership_status=ownership_status or None,
        completeness=completeness,
        retirement=retirement,
        copies=copies,
        fs=fs,
        paid_min=paid_min,
        paid_max=paid_max,
        rrp_min=rrp_min,
        rrp_max=rrp_max,
        roi_min=roi_min,
        roi_max=roi_max,
        sort=sort,
        direction=direction,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return LegoSetInstancePage(
        items=items, total=total, page=page, page_size=page_size, summary=summary
    )


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


@router.put("/instances/{instance_id}/display-image", response_model=LegoSetInstanceOut)
def set_instance_display_image(
    instance_id: uuid.UUID, payload: InstanceDisplayImageUpdate, ctx: Writer, db: Db
) -> LegoSetInstanceOut:
    """Which of the set's own images stands for this copy in the collection table."""
    instance = lego_service.get_instance(db, instance_id)
    lego_service.set_instance_display_image(
        db, instance, payload.document_id, actor_user_id=ctx.user.id
    )
    return lego_service.instance_out(db, instance)


# --- Bulk import (M9.5) -------------------------------------------------------
@router.post("/instances/bulk/preview", response_model=BulkImportPreviewOut)
def bulk_preview_instances(
    ctx: CurrentAuth, db: Db, file: Annotated[UploadFile, File()]
) -> BulkImportPreviewOut:
    """Resolves each row against the household's own entities/locations only —
    Brickset is never contacted here (M9 guarantee: only on an explicit action)."""
    data = file.file.read()
    if not data:
        raise ValidationError("Ficheiro vazio.")
    rows = lego_bulk_import.preview_instances(
        db, data=data, household_id=ctx.household_id, active_entity_id=ctx.active_entity_id
    )
    return BulkImportPreviewOut(rows=rows)


@router.post(
    "/instances/bulk/commit",
    # Real response is a StreamingResponse (NDJSON, one BulkImportRowResult per
    # line), which FastAPI can't describe from a return type alone. Declaring it
    # here only registers the schema for OpenAPI/types-gen - it has no effect on
    # the actual streamed response (FastAPI skips response_model handling when a
    # Response instance is returned directly).
    responses={
        200: {
            "model": BulkImportRowResult,
            "description": "NDJSON stream, one BulkImportRowResult per line.",
        }
    },
)
def bulk_commit_instances(payload: BulkImportCommitIn, ctx: Writer, db: Db) -> StreamingResponse:
    """One Brickset lookup + registration per row, exactly like the manual form.
    A row that fails (unknown to Brickset, network error, ...) does not stop the rest.
    Streamed as NDJSON (one `BulkImportRowResult` per line) so the client can show
    progress as each row lands instead of waiting for the whole batch."""

    def generate() -> Iterator[str]:
        for result in lego_bulk_import.iter_commit_instances(
            db, payload.rows, household_id=ctx.household_id, actor_user_id=ctx.user.id
        ):
            yield result.model_dump_json() + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# --- Storage -----------------------------------------------------------------
@router.get("/storage-locations", response_model=list[StorageLocationOut])
def list_storage(ctx: CurrentAuth, db: Db) -> list[StorageLocationOut]:
    return lego_service.list_storage_locations(db)


@router.post("/storage-locations", response_model=StorageLocationOut, status_code=201)
def create_storage(payload: StorageLocationCreate, ctx: Writer, db: Db) -> StorageLocationOut:
    location = lego_service.create_storage_location(db, payload, actor_user_id=ctx.user.id)
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


@router.post("/storage-locations/bulk", response_model=StorageBulkImportOut)
def bulk_import_storage(
    ctx: Writer, db: Db, file: Annotated[UploadFile, File()]
) -> StorageBulkImportOut:
    """Upserted on (área, contentor) — unlike copies, re-running this is safe."""
    data = file.file.read()
    if not data:
        raise ValidationError("Ficheiro vazio.")
    return lego_bulk_import.import_storage_locations(db, data=data, actor_user_id=ctx.user.id)


# --- Export ------------------------------------------------------------------
@router.get("/export.xlsx", response_class=Response)
def export_workbook(ctx: CurrentAuth, db: Db) -> Response:
    """The whole collection as one workbook: copies, sets and storage locations."""
    # Imported here so the spreadsheet writer is only loaded when someone exports.
    from app.services import lego_export

    payload = lego_export.build_workbook(
        db,
        entity_ids=household_entity_ids(db, ctx),
        active_entity_id=ctx.active_entity_id,
    )
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{lego_export.filename(ctx.active_entity_id)}"'
            )
        },
    )
