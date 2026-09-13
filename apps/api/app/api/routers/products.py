"""Master products, learned aliases, the GROCERY taxonomy and the legacy import.

Category **reads** stay in the shared reference router; the administration
endpoints here extend that surface and are scoped to ``domain = GROCERY``,
because M1 is the module that lives or dies by that tree (Decision #18).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, Query, Response, UploadFile
from rapidfuzz import fuzz, process
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import CurrentAuth, Db, Owner, Writer, resolve_write_entity
from app.core.errors import ValidationError
from app.models.core import Category, Merchant
from app.models.products import MasterProduct, ProductAlias
from app.models.supermarket import SupermarketReceipt, SupermarketReceiptItem
from app.schemas.common import Ok, Page
from app.schemas.products import (
    AttributeOption,
    BulkProductImportCommitIn,
    BulkProductImportPreviewOut,
    BulkProductImportRow,
    BulkProductImportRowResult,
    CategoryCreate,
    CategoryDefaultsLoadOut,
    CategoryImpactOut,
    CategoryImportOut,
    CategoryImportRowError,
    CategoryMerge,
    CategoryOperationResult,
    CategoryRename,
    CategoryReparent,
    CategorySearchResult,
    CategoryTreeNode,
    LastKnownPrice,
    LearnAliasRequest,
    LegacyImportResult,
    MasterProductCreate,
    MasterProductOut,
    MasterProductUpdate,
    MergeCandidate,
    MergeCandidateProduct,
    MergeRequest,
    PackVariantAdd,
    ProductAliasOut,
    ProductAttributeVocabularyOut,
    ProductDefaultsLoadOut,
    ProductOccurrence,
    ProductSearchResult,
)
from app.services import documents, reference_data
from app.services.supermarket import (
    attributes,
    catalogue,
    legacy_import,
    prices_service,
    products_service,
)
from app.services.supermarket import defaults as supermarket_defaults
from app.services.supermarket import service as supermarket
from app.services.supermarket.normalize import normalize_description

products_router = APIRouter(prefix="/master-products", tags=["supermarket"])
aliases_router = APIRouter(prefix="/product-aliases", tags=["supermarket"])
categories_router = APIRouter(prefix="/categories", tags=["supermarket"])


# --- Serialization ------------------------------------------------------------


def _last_known_price(db: DbSession, product_id: uuid.UUID) -> LastKnownPrice | None:
    """Derived from the newest observation, so it can never become a second truth."""
    latest = prices_service.last_known_price(db, product_id)
    if latest is None:
        return None
    return LastKnownPrice(
        last_pvp_eur=latest.last_pvp_eur,
        last_price_per_kg_eur=latest.last_price_per_kg_eur,
        last_weight_kg=latest.last_weight_kg,
        last_observed_on=latest.last_observed_on,
    )


def product_out(db: DbSession, product: MasterProduct) -> MasterProductOut:
    payload = MasterProductOut.model_validate(product)
    payload.category_path = products_service.category_path(db, product.category_id)
    payload.alias_count = int(
        db.scalar(
            select(func.count())
            .select_from(ProductAlias)
            .where(ProductAlias.master_product_id == product.id)
        )
        or 0
    )
    payload.occurrence_count = int(
        db.scalar(
            select(func.count())
            .select_from(SupermarketReceiptItem)
            .where(
                SupermarketReceiptItem.master_product_id == product.id,
                SupermarketReceiptItem.is_deleted.is_(False),
            )
        )
        or 0
    )
    payload.last_known_price = _last_known_price(db, product.id)
    return payload


# --- Products -----------------------------------------------------------------


@products_router.get("", response_model=Page[MasterProductOut])
def list_products(
    ctx: CurrentAuth,
    db: Db,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    category_status: str | None = None,
    sold_by_weight: bool | None = None,
    is_own_brand: bool | None = None,
    brand: str | None = None,
    conservation: str | None = None,
    presentation: str | None = None,
    dietary: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[MasterProductOut]:
    stmt = select(MasterProduct).where(MasterProduct.is_deleted.is_(False))
    if search:
        stmt = stmt.where(MasterProduct.canonical_name.ilike(f"%{search}%"))
    if category_id:
        ids = products_service.subtree_ids(db, category_id)
        stmt = stmt.where(MasterProduct.category_id.in_(ids))
    if category_status:
        stmt = stmt.where(MasterProduct.category_status == category_status)
    if sold_by_weight is not None:
        stmt = stmt.where(MasterProduct.sold_by_weight.is_(sold_by_weight))
    stmt = products_service.apply_attribute_filters(
        stmt,
        is_own_brand=is_own_brand,
        brand=brand,
        conservation=conservation,
        presentation=presentation,
        dietary=dietary,
    )

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(MasterProduct.canonical_name).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return Page(
        items=[product_out(db, row) for row in rows], total=total, page=page, page_size=page_size
    )


@products_router.get("/search", response_model=list[ProductSearchResult])
def search_products(
    ctx: CurrentAuth,
    db: Db,
    q: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> list[ProductSearchResult]:
    """Autocomplete over canonical names, brands and learned aliases.

    Returns the category and the last known price so any picker can pre-fill —
    which is what stops a near-duplicate being created by hand.
    """
    needle = normalize_description(q)
    rows = db.execute(
        select(
            MasterProduct.id,
            MasterProduct.canonical_name,
            MasterProduct.brand,
            MasterProduct.category_id,
            MasterProduct.sold_by_weight,
        ).where(MasterProduct.is_deleted.is_(False))
    ).all()
    if not rows or not needle:
        return []

    scored = process.extract(
        needle,
        {row[0]: normalize_description(f"{row[1]} {row[2] or ''}") for row in rows},
        scorer=fuzz.token_set_ratio,
        limit=limit,
    )
    by_id = {row[0]: row for row in rows}
    results: list[ProductSearchResult] = []
    for _, score, product_id in scored:
        row = by_id[product_id]
        results.append(
            ProductSearchResult(
                id=row[0],
                canonical_name=row[1],
                brand=row[2],
                category_id=row[3],
                category_path=products_service.category_path(db, row[3]),
                sold_by_weight=row[4],
                score=round(score / 100, 3),
                last_known_price=_last_known_price(db, row[0]),
            )
        )
    return results


@products_router.get("/merge-candidates", response_model=list[MergeCandidate])
def list_merge_candidates(ctx: CurrentAuth, db: Db) -> list[MergeCandidate]:
    return [
        MergeCandidate(
            key=candidate["key"],
            products=[MergeCandidateProduct(**product) for product in candidate["products"]],
        )
        for candidate in products_service.merge_candidates(db)
    ]


@products_router.get("/attributes", response_model=ProductAttributeVocabularyOut)
def product_attribute_vocabulary(ctx: CurrentAuth) -> ProductAttributeVocabularyOut:
    """Registered above ``/{product_id}``: a static segment declared after a bare
    ``/{id}`` route is swallowed by it and fails as a 422 (see ADR-0055's note)."""
    return ProductAttributeVocabularyOut(
        **{
            axis: [AttributeOption(**option) for option in options]
            for axis, options in attributes.vocabulary().items()
        }
    )


@products_router.post("/defaults/load", response_model=ProductDefaultsLoadOut, status_code=201)
def load_default_products(ctx: Writer, db: Db) -> ProductDefaultsLoadOut:
    """Load the household's own catalogue file on demand (ADR-0061).

    Not run at boot, not run by ``make seed`` alone: a household presses this
    once the catalogue is empty. Safe to press again — rows already present
    (same name + brand) are skipped, never duplicated. ``available=false`` means
    there is no file to load yet, which the empty state reads as a different
    message than "loaded, but everything was already here".
    """
    created = supermarket_defaults.load_default_products(db, actor_user_id=ctx.user.id)
    return ProductDefaultsLoadOut(
        created=created, available=supermarket_defaults.PRODUCTS_FILE.exists()
    )


# --- Bulk import (curated product log) -----------------------------------------


@products_router.post("/bulk/preview", response_model=BulkProductImportPreviewOut)
def preview_bulk_import(
    ctx: Writer, db: Db, file: Annotated[UploadFile, File()]
) -> BulkProductImportPreviewOut:
    """Resolves category paths and existing-product matches only — never writes.

    Safe to call for a re-preview after fixing a row, and safe to call for the
    same file twice: nothing here creates or changes a product.
    """
    data = file.file.read()
    if not data:
        raise ValidationError("Ficheiro vazio.")
    rows = products_service.preview_product_import(db, data)
    return BulkProductImportPreviewOut(rows=[BulkProductImportRow(**row) for row in rows])


@products_router.post("/bulk/commit", response_model=list[BulkProductImportRowResult])
def commit_bulk_import(
    payload: BulkProductImportCommitIn, ctx: Writer, db: Db
) -> list[BulkProductImportRowResult]:
    """One row at a time — a row already known to exist is skipped, not
    duplicated, and one bad row never blocks the rest of the sheet."""
    results = products_service.commit_product_import(
        db,
        [row.model_dump() for row in payload.rows],
        actor_user_id=ctx.user.id,
    )
    return [BulkProductImportRowResult(**result) for result in results]


@products_router.post("", response_model=MasterProductOut, status_code=201)
def create_product(payload: MasterProductCreate, ctx: Writer, db: Db) -> MasterProductOut:
    data = payload.model_dump()
    product = products_service.create_product(
        db,
        canonical_name=data.pop("canonical_name"),
        brand=data.pop("brand"),
        category_id=data.pop("category_id"),
        sold_by_weight=data.pop("sold_by_weight"),
        pack_variants=data.pop("pack_variants"),
        actor_user_id=ctx.user.id,
        **data,
    )
    return product_out(db, product)


@products_router.get("/{product_id}", response_model=MasterProductOut)
def get_product(product_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> MasterProductOut:
    return product_out(db, products_service.get_product(db, product_id))


@products_router.patch("/{product_id}", response_model=MasterProductOut)
def update_product(
    product_id: uuid.UUID, payload: MasterProductUpdate, ctx: Writer, db: Db
) -> MasterProductOut:
    product = products_service.get_product(db, product_id)
    changes: dict[str, Any] = payload.model_dump(exclude_unset=True)
    if "pack_variants" in changes and changes["pack_variants"] is not None:
        changes["pack_variants"] = products_service.sanitize_pack_variants(changes["pack_variants"])
    products_service.update_product(db, product, changes, actor_user_id=ctx.user.id)
    return product_out(db, product)


@products_router.post("/{product_id}/pack-variants", response_model=MasterProductOut)
def add_pack_variant(
    product_id: uuid.UUID, payload: PackVariantAdd, ctx: Writer, db: Db
) -> MasterProductOut:
    """Curate the format a receipt line just showed us, without touching the rest."""
    product = products_service.get_product(db, product_id)
    products_service.add_pack_variant(
        db,
        product,
        weight_kg=payload.weight_kg,
        label=payload.label,
        barcode=payload.barcode,
        actor_user_id=ctx.user.id,
    )
    return product_out(db, product)


@products_router.post("/{product_id}/validate-category", response_model=MasterProductOut)
def validate_category(product_id: uuid.UUID, ctx: Writer, db: Db) -> MasterProductOut:
    product = products_service.get_product(db, product_id)
    products_service.validate_category(db, product, actor_user_id=ctx.user.id)
    return product_out(db, product)


@products_router.get("/{product_id}/aliases", response_model=list[ProductAliasOut])
def product_aliases(product_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> list[ProductAliasOut]:
    rows = db.scalars(
        select(ProductAlias).where(ProductAlias.master_product_id == product_id)
    ).all()
    names = {
        row[0]: row[1]
        for row in db.execute(
            select(Merchant.id, Merchant.name).where(
                Merchant.id.in_({alias.merchant_id for alias in rows})
            )
        ).all()
    }
    payloads = []
    for alias in rows:
        payload = ProductAliasOut.model_validate(alias)
        payload.merchant_name = names.get(alias.merchant_id)
        payloads.append(payload)
    return payloads


@products_router.get("/{product_id}/occurrences", response_model=list[ProductOccurrence])
def product_occurrences(
    product_id: uuid.UUID,
    ctx: CurrentAuth,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ProductOccurrence]:
    """Every receipt line this product has appeared on, with a link to each invoice."""
    rows = db.execute(
        select(SupermarketReceiptItem, SupermarketReceipt, Merchant.name)
        .join(SupermarketReceipt, SupermarketReceipt.id == SupermarketReceiptItem.receipt_id)
        .outerjoin(Merchant, Merchant.id == SupermarketReceipt.merchant_id)
        .where(
            SupermarketReceiptItem.master_product_id == product_id,
            SupermarketReceiptItem.is_deleted.is_(False),
            SupermarketReceipt.is_deleted.is_(False),
        )
        .order_by(SupermarketReceipt.purchase_date.desc().nullslast())
        .limit(limit)
    ).all()

    occurrences: list[ProductOccurrence] = []
    for item, receipt, merchant_name in rows:
        derived = supermarket.item_derived(item)
        occurrences.append(
            ProductOccurrence(
                receipt_item_id=item.id,
                receipt_id=receipt.id,
                purchase_date=receipt.purchase_date,
                merchant_name=merchant_name,
                description_raw=item.description_raw,
                quantity=item.quantity,
                unit=item.unit,
                unit_price_pvp_eur=item.unit_price_pvp_eur,
                paid_price_eur=item.paid_price_eur,
                price_per_kg_final_eur=derived["price_per_kg_final_eur"],
                is_fs=item.is_fs,
            )
        )
    return occurrences


@products_router.post("/{product_id}/merge", response_model=MasterProductOut)
def merge_products(
    product_id: uuid.UUID, payload: MergeRequest, ctx: Writer, db: Db
) -> MasterProductOut:
    target = products_service.get_product(db, product_id)
    source = products_service.get_product(db, payload.source_id)
    products_service.merge_products(db, source=source, target=target, actor_user_id=ctx.user.id)
    return product_out(db, target)


@products_router.delete("/purge", response_model=Ok)
def purge_products(ctx: Owner, db: Db) -> Ok:
    """Hard-deletes the whole catalogue ahead of a fresh import — no per-row
    in-use guard, unlike `delete_product`. Registered ahead of the `/{product_id}`
    route below so "purge" is never parsed as a product id (see supermarket-rename
    routing gotcha in repo notes)."""
    count = products_service.purge_products(db, actor_user_id=ctx.user.id)
    return Ok(message=f"{count} produto(s) eliminado(s) definitivamente.")


@products_router.delete("/{product_id}", response_model=Ok)
def delete_product(product_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    product = products_service.get_product(db, product_id)
    in_use = int(
        db.scalar(
            select(func.count())
            .select_from(SupermarketReceiptItem)
            .where(
                SupermarketReceiptItem.master_product_id == product.id,
                SupermarketReceiptItem.is_deleted.is_(False),
            )
        )
        or 0
    )
    if in_use:
        raise ValidationError(
            f"Este produto está em {in_use} linha(s). Funda-o noutro em vez de o apagar."
        )
    products_service.update_product(db, product, {"is_deleted": True}, actor_user_id=ctx.user.id)
    return Ok(message="Produto eliminado.")


# --- Aliases ------------------------------------------------------------------


@aliases_router.post("/learn", response_model=ProductAliasOut)
def learn_alias(payload: LearnAliasRequest, ctx: Writer, db: Db) -> ProductAliasOut:
    products_service.get_product(db, payload.master_product_id)
    alias = catalogue.learn(
        db,
        master_product_id=payload.master_product_id,
        merchant_id=payload.merchant_id,
        merchant_description=payload.merchant_description,
    )
    return ProductAliasOut.model_validate(alias)


# --- Category administration (FR-1.17) ----------------------------------------


@categories_router.get("/search", response_model=list[CategorySearchResult])
def search_categories(
    ctx: CurrentAuth,
    db: Db,
    q: str = "",
    domain: str = "GROCERY",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[CategorySearchResult]:
    rows = db.scalars(
        select(Category).where(Category.domain == domain, Category.is_deleted.is_(False))
    ).all()
    needle = normalize_description(q)
    results: list[tuple[float, CategorySearchResult]] = []
    for node in rows:
        path = products_service.category_path(db, node.id) or node.display_name_pt
        score = fuzz.token_set_ratio(needle, normalize_description(path)) if needle else 100.0
        results.append(
            (
                score,
                CategorySearchResult(
                    id=node.id, display_name_pt=node.display_name_pt, level=node.level, path=path
                ),
            )
        )
    results.sort(key=lambda pair: (-pair[0], pair[1].path))
    return [result for _, result in results[:limit]]


@categories_router.get("/tree", response_model=list[CategoryTreeNode])
def category_tree(ctx: CurrentAuth, db: Db, domain: str = "GROCERY") -> list[CategoryTreeNode]:
    """Every node, flat, with its path and how many products reference it.

    The taxonomy editor needs the whole tree; a search limit would silently
    truncate it and make a node look retired when it is merely off the end.
    """
    nodes = db.scalars(
        select(Category)
        .where(Category.domain == domain, Category.is_deleted.is_(False))
        .order_by(Category.level, Category.display_name_pt)
    ).all()
    counts = {
        row[0]: row[1]
        for row in db.execute(
            select(MasterProduct.category_id, func.count())
            .where(MasterProduct.is_deleted.is_(False))
            .group_by(MasterProduct.category_id)
        ).all()
    }
    by_id = {node.id: node for node in nodes}

    def path_of(node: Category) -> str:
        names: list[str] = []
        current: Category | None = node
        while current is not None:
            names.append(current.display_name_pt)
            current = by_id.get(current.parent_id) if current.parent_id else None
        return " › ".join(reversed(names))

    return [
        CategoryTreeNode(
            id=node.id,
            display_name_pt=node.display_name_pt,
            level=node.level,
            parent_id=node.parent_id,
            brand_axis=node.brand_axis,
            path=path_of(node),
            product_count=counts.get(node.id, 0),
        )
        for node in nodes
    ]


@categories_router.get("/{category_id}/impact", response_model=CategoryImpactOut)
def category_impact(category_id: uuid.UUID, ctx: CurrentAuth, db: Db) -> CategoryImpactOut:
    """What a destructive operation would touch, **before** it runs."""
    usage = products_service.impact(db, category_id)
    return CategoryImpactOut(
        category_id=usage.category_id,
        descendants=usage.descendants,
        master_products=usage.master_products,
        receipt_items=usage.receipt_items,
        in_use=usage.in_use,
    )


@categories_router.post("", response_model=CategorySearchResult, status_code=201)
def create_category(payload: CategoryCreate, ctx: Writer, db: Db) -> CategorySearchResult:
    category = products_service.create_category(
        db,
        display_name_pt=payload.display_name_pt,
        parent_id=payload.parent_id,
        brand_axis=payload.brand_axis,
        actor_user_id=ctx.user.id,
    )
    return CategorySearchResult(
        id=category.id,
        display_name_pt=category.display_name_pt,
        level=category.level,
        path=products_service.category_path(db, category.id) or category.display_name_pt,
    )


@categories_router.post("/defaults/load", response_model=CategoryDefaultsLoadOut, status_code=201)
def load_default_categories(ctx: Writer, db: Db) -> CategoryDefaultsLoadOut:
    """Load the shipped GROCERY taxonomy on demand (ADR-0057).

    Not run at boot: a household presses this once the table is empty. Safe to
    press again later — additive only, same idempotent contract as
    ``ensure_categories`` had at boot before this release.
    """
    created = reference_data.ensure_categories(db)
    return CategoryDefaultsLoadOut(created=created)


@categories_router.patch("/{category_id}", response_model=CategorySearchResult)
def rename_category(
    category_id: uuid.UUID, payload: CategoryRename, ctx: Writer, db: Db
) -> CategorySearchResult:
    """A rename costs nothing: rows reference categories by id."""
    category = products_service.get_category(db, category_id)
    products_service.rename_category(
        db, category, payload.display_name_pt, actor_user_id=ctx.user.id
    )
    return CategorySearchResult(
        id=category.id,
        display_name_pt=category.display_name_pt,
        level=category.level,
        path=products_service.category_path(db, category.id) or category.display_name_pt,
    )


@categories_router.post("/{category_id}/reparent", response_model=CategoryOperationResult)
def reparent_category(
    category_id: uuid.UUID, payload: CategoryReparent, ctx: Writer, db: Db
) -> CategoryOperationResult:
    category = products_service.get_category(db, category_id)
    affected = products_service.reparent_category(
        db, category, payload.parent_id, actor_user_id=ctx.user.id
    )
    return CategoryOperationResult(
        affected_products=affected,
        message=f"{affected} produto(s) com ascendentes recalculados.",
    )


@categories_router.post("/{category_id}/merge", response_model=CategoryOperationResult)
def merge_categories(
    category_id: uuid.UUID, payload: CategoryMerge, ctx: Writer, db: Db
) -> CategoryOperationResult:
    source = products_service.get_category(db, category_id)
    target = products_service.get_category(db, payload.target_id)
    affected = products_service.merge_categories(
        db, source=source, target=target, actor_user_id=ctx.user.id
    )
    return CategoryOperationResult(
        affected_products=affected, message=f"{affected} produto(s) reatribuídos."
    )


@categories_router.delete("/purge", response_model=Ok)
def purge_categories(ctx: Owner, db: Db) -> Ok:
    """Hard-deletes the whole GROCERY taxonomy — no in-use guard, unlike
    `retire_category`. Registered ahead of the `/{category_id}` route below so
    "purge" is never parsed as a category id."""
    count = products_service.purge_categories(db, actor_user_id=ctx.user.id)
    return Ok(message=f"{count} categoria(s) eliminada(s) definitivamente.")


@categories_router.delete("/{category_id}", response_model=Ok)
def retire_category(category_id: uuid.UUID, ctx: Writer, db: Db) -> Ok:
    """Refused while in use, with the usage count returned."""
    category = products_service.get_category(db, category_id)
    products_service.retire_category(db, category, actor_user_id=ctx.user.id)
    return Ok(message="Categoria retirada.")


# --- Whole-tree export / import (Decision #56) ---------------------------------


@categories_router.get("/export.xlsx", response_class=Response)
def export_categories(ctx: CurrentAuth, db: Db) -> Response:
    """Every node, one row per category — a valid input for «Importar» below."""
    payload = products_service.export_categories_workbook(db)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="categorias-{dt.date.today():%Y%m%d}.xlsx"'
            )
        },
    )


@categories_router.post("/import", response_model=CategoryImportOut)
def import_categories(
    ctx: Writer, db: Db, file: Annotated[UploadFile, File()]
) -> CategoryImportOut:
    """Additive only: ensures every L1›L2›L3 path in the sheet exists, same as
    the export it round-trips (Decision #56)."""
    data = file.file.read()
    if not data:
        raise ValidationError("Ficheiro vazio.")
    report = products_service.import_categories_workbook(db, data=data, actor_user_id=ctx.user.id)
    return CategoryImportOut(
        created=report.created,
        existing=report.existing,
        errors=[
            CategoryImportRowError(row_number=issue.row_number, message=issue.message)
            for issue in report.errors
        ],
    )


# --- Legacy import (FR-1.19) ---------------------------------------------------


import_router = APIRouter(prefix="/supermarket/import", tags=["supermarket"])


@import_router.post("/legacy", response_model=LegacyImportResult)
def import_legacy(
    ctx: Writer,
    db: Db,
    file: Annotated[UploadFile, File()],
    entity_id: uuid.UUID | None = None,
    include_non_grocery: bool = False,
) -> LegacyImportResult:
    """The ``SUPERMARKET_YYYY`` migration, wrapped in an ``ImportBatch``.

    Re-runnable without duplication: a group already imported for this entity is
    updated in place rather than doubled.
    """
    target_entity = resolve_write_entity(db, ctx, entity_id)
    data = file.file.read()
    if not data:
        raise ValidationError("Ficheiro vazio.")

    document = None
    try:
        document = documents.store_bytes(db, data, source="UPLOAD", original_filename=file.filename)
    except ValidationError:
        # A spreadsheet is not in the attachment allow-list; the import does not
        # need the file kept, so provenance is simply absent.
        document = None

    report = legacy_import.import_workbook(
        db,
        data=data,
        entity_id=target_entity,
        actor_user_id=ctx.user.id,
        document_id=document.id if document else None,
        include_non_grocery=include_non_grocery,
    )
    return LegacyImportResult(**report.as_dict())


routers = (products_router, aliases_router, categories_router, import_router)
