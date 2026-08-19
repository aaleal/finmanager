"""The product catalogue and the taxonomy that hangs off it.

Two rules govern everything here:

1. **A category lives on the product and nowhere else** (Decision #34). A receipt
   line inherits it by resolving.
2. **The deepest assigned level is authoritative; its ancestors are maintained.**
   Snapshotting the full triple per row lets history drift into a second
   taxonomy; deriving it on every read costs a recursive join on the hottest
   query in the module. The middle path is `category_id` plus a maintained
   `l1/l2/l3` trio, refreshed on reparent (Decision #16).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.core import audit
from app.core.errors import Conflict, NotFound, ValidationError
from app.models.core import Category
from app.models.products import MasterProduct, ProductAlias
from app.models.receipts import ReceiptItem
from app.services.receipts import catalogue, classify
from app.services.receipts.normalize import normalize_description

GROCERY = "GROCERY"
PRODUCT_TABLE = "master_products"
CATEGORY_TABLE = "categories"


# --- Category ancestry --------------------------------------------------------


def ancestry(db: DbSession, category_id: uuid.UUID | None) -> dict[str, uuid.UUID | None]:
    """The maintained trio for a given deepest-assigned category."""
    trio: dict[str, uuid.UUID | None] = {
        "category_l1_id": None,
        "category_l2_id": None,
        "category_l3_id": None,
    }
    node = db.get(Category, category_id) if category_id else None
    while node is not None:
        trio[f"category_l{node.level}_id"] = node.id
        node = db.get(Category, node.parent_id) if node.parent_id else None
    return trio


def category_path(db: DbSession, category_id: uuid.UUID | None) -> str | None:
    """``L1 › L2 › L3`` — so the same leaf name under two parents is never ambiguous."""
    names: list[str] = []
    node = db.get(Category, category_id) if category_id else None
    while node is not None:
        names.append(node.display_name_pt)
        node = db.get(Category, node.parent_id) if node.parent_id else None
    return " › ".join(reversed(names)) if names else None


def _apply_category(db: DbSession, product: MasterProduct, category_id: uuid.UUID | None) -> None:
    if category_id is not None:
        category = db.get(Category, category_id)
        if category is None or category.is_deleted:
            raise NotFound("Categoria não encontrada.")
        if category.domain != GROCERY:
            raise ValidationError("A categoria tem de pertencer ao domínio alimentar.")
    product.category_id = category_id
    for field, value in ancestry(db, category_id).items():
        setattr(product, field, value)


# --- Products -----------------------------------------------------------------


def get_product(db: DbSession, product_id: uuid.UUID) -> MasterProduct:
    product = db.get(MasterProduct, product_id)
    if product is None or product.is_deleted:
        raise NotFound("Produto não encontrado.")
    return product


def create_product(
    db: DbSession,
    *,
    canonical_name: str,
    brand: str | None = None,
    category_id: uuid.UUID | None = None,
    category_status: str = "MANUAL",
    category_confidence: Decimal | None = None,
    sold_by_weight: bool = False,
    pack_variants: list[Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
    **extra: Any,
) -> MasterProduct:
    name = canonical_name.strip()
    if not name:
        raise ValidationError("O produto precisa de um nome.")

    clash = db.scalar(
        select(MasterProduct).where(
            func.lower(MasterProduct.canonical_name) == name.lower(),
            MasterProduct.brand.is_(None) if brand is None else MasterProduct.brand == brand,
            MasterProduct.is_deleted.is_(False),
        )
    )
    if clash is not None:
        raise Conflict("Já existe um produto com este nome e marca.", existing_id=str(clash.id))

    product = MasterProduct(
        canonical_name=name,
        brand=brand,
        category_status=category_status,
        category_confidence=category_confidence,
        sold_by_weight=sold_by_weight,
        pack_variants=pack_variants or [],
        **extra,
    )
    _apply_category(db, product, category_id)
    db.add(product)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name=PRODUCT_TABLE,
        record_id=product.id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(product),
    )
    return product


def update_product(
    db: DbSession,
    product: MasterProduct,
    changes: dict[str, Any],
    *,
    actor_user_id: uuid.UUID | None = None,
) -> MasterProduct:
    before = audit.snapshot(product)
    if "category_id" in changes:
        _apply_category(db, product, changes.pop("category_id"))
        # A human touched it, so it is no longer a machine's guess.
        product.category_status = changes.pop("category_status", "MANUAL")
        product.category_confidence = None
    for field, value in changes.items():
        setattr(product, field, value)
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=PRODUCT_TABLE,
        record_id=product.id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(product),
    )
    return product


def validate_category(
    db: DbSession, product: MasterProduct, *, actor_user_id: uuid.UUID | None
) -> MasterProduct:
    """Promote an ``AUTO`` suggestion to ``VALIDATED`` — once, for every past and future line."""
    if product.category_id is None:
        raise ValidationError("Não há categoria para confirmar.")
    if product.category_status == "AUTO":
        before = audit.snapshot(product)
        product.category_status = "VALIDATED"
        db.flush()
        audit.record(
            db,
            action="UPDATE",
            table_name=PRODUCT_TABLE,
            record_id=product.id,
            actor_user_id=actor_user_id,
            before=before,
            after=audit.snapshot(product),
            reason="categoria confirmada",
        )
    return product


def merge_products(
    db: DbSession,
    *,
    source: MasterProduct,
    target: MasterProduct,
    actor_user_id: uuid.UUID | None,
) -> MasterProduct:
    """Fold a duplicate into its twin: lines and aliases move, the source retires."""
    if source.id == target.id:
        raise ValidationError("Um produto não pode ser fundido consigo próprio.")

    # `fetch` keeps already-loaded lines in step with the bulk update; without it
    # the caller's in-memory rows would still point at the retired product.
    moved_lines = (
        db.query(ReceiptItem)
        .filter(ReceiptItem.master_product_id == source.id)
        .update({ReceiptItem.master_product_id: target.id}, synchronize_session="fetch")
    )
    moved_aliases = 0
    for alias in db.scalars(
        select(ProductAlias).where(ProductAlias.master_product_id == source.id)
    ).all():
        duplicate = db.scalar(
            select(ProductAlias).where(
                ProductAlias.merchant_id == alias.merchant_id,
                ProductAlias.description_norm == alias.description_norm,
                ProductAlias.master_product_id == target.id,
            )
        )
        if duplicate is not None:
            db.delete(alias)
        else:
            alias.master_product_id = target.id
            moved_aliases += 1

    source.is_deleted = True
    source.deleted_at = dt.datetime.now(dt.UTC)
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=PRODUCT_TABLE,
        record_id=target.id,
        actor_user_id=actor_user_id,
        before={"merged_from": str(source.id)},
        after={"moved_lines": moved_lines, "moved_aliases": moved_aliases},
        reason="fusão de produtos",
    )
    return target


def merge_candidates(db: DbSession, *, limit: int = 50) -> list[dict[str, Any]]:
    """Near-duplicate canonical names, so the catalogue does not silently fork."""
    products = db.execute(
        select(MasterProduct.id, MasterProduct.canonical_name, MasterProduct.brand).where(
            MasterProduct.is_deleted.is_(False)
        )
    ).all()
    by_key: dict[str, list[dict[str, Any]]] = {}
    for product_id, name, brand in products:
        key = normalize_description(name)
        by_key.setdefault(key, []).append(
            {"id": product_id, "canonical_name": name, "brand": brand}
        )
    return [{"key": key, "products": group} for key, group in by_key.items() if len(group) > 1][
        :limit
    ]


def suggest_category(
    db: DbSession, *, description: str, merchant_section: str | None
) -> classify.Classification:
    return classify.get_classifier().classify(
        db, description=description, merchant_section=merchant_section
    )


def find_or_create_for_line(
    db: DbSession, item: ReceiptItem, *, merchant_id: uuid.UUID | None
) -> MasterProduct:
    """Create the product a line implies, with an ``AUTO`` category suggestion."""
    suggestion = suggest_category(
        db, description=item.description_raw, merchant_section=item.merchant_section
    )
    product = create_product(
        db,
        canonical_name=item.description_raw.strip()[:250],
        category_id=suggestion.category_id,
        category_status="AUTO",
        category_confidence=suggestion.score if suggestion.category_id else None,
    )
    item.master_product_id = product.id
    if merchant_id is not None:
        catalogue.learn(
            db,
            master_product_id=product.id,
            merchant_id=merchant_id,
            merchant_description=item.description_raw,
        )
    return product


# --- Category governance (FR-1.17) --------------------------------------------


@dataclass(frozen=True, slots=True)
class CategoryImpact:
    """What a destructive operation would touch, **before** it runs."""

    category_id: uuid.UUID
    descendants: int
    master_products: int
    receipt_items: int

    @property
    def in_use(self) -> bool:
        return self.master_products > 0 or self.receipt_items > 0


def subtree_ids(db: DbSession, category_id: uuid.UUID) -> list[uuid.UUID]:
    ids = [category_id]
    frontier = [category_id]
    while frontier:
        children = list(
            db.scalars(select(Category.id).where(Category.parent_id.in_(frontier))).all()
        )
        if not children:
            break
        ids.extend(children)
        frontier = children
    return ids


def impact(db: DbSession, category_id: uuid.UUID) -> CategoryImpact:
    ids = subtree_ids(db, category_id)
    products = int(
        db.scalar(
            select(func.count())
            .select_from(MasterProduct)
            .where(
                MasterProduct.is_deleted.is_(False),
                or_(
                    MasterProduct.category_id.in_(ids),
                    MasterProduct.category_l1_id.in_(ids),
                    MasterProduct.category_l2_id.in_(ids),
                    MasterProduct.category_l3_id.in_(ids),
                ),
            )
        )
        or 0
    )
    lines = int(
        db.scalar(
            select(func.count())
            .select_from(ReceiptItem)
            .join(MasterProduct, MasterProduct.id == ReceiptItem.master_product_id)
            .where(ReceiptItem.is_deleted.is_(False), MasterProduct.category_id.in_(ids))
        )
        or 0
    )
    return CategoryImpact(category_id, len(ids) - 1, products, lines)


def get_category(db: DbSession, category_id: uuid.UUID) -> Category:
    category = db.get(Category, category_id)
    if category is None or category.is_deleted:
        raise NotFound("Categoria não encontrada.")
    return category


def create_category(
    db: DbSession,
    *,
    display_name_pt: str,
    parent_id: uuid.UUID | None,
    code_en: str | None = None,
    brand_axis: bool = False,
    actor_user_id: uuid.UUID | None = None,
) -> Category:
    parent = get_category(db, parent_id) if parent_id else None
    level = (parent.level + 1) if parent else 1
    if level > 3:
        raise ValidationError("A árvore alimentar tem três níveis.")

    category = Category(
        code_en=code_en or _slug(display_name_pt, parent),
        display_name_pt=display_name_pt.strip(),
        domain=GROCERY,
        level=level,
        parent_id=parent.id if parent else None,
        brand_axis=brand_axis,
    )
    db.add(category)
    db.flush()
    audit.record(
        db,
        action="CREATE",
        table_name=CATEGORY_TABLE,
        record_id=category.id,
        actor_user_id=actor_user_id,
        after=audit.snapshot(category),
    )
    return category


def _slug(name: str, parent: Category | None) -> str:
    from app.seed import slugify

    base = slugify(name)
    return f"{parent.code_en}__{base}" if parent else base


def rename_category(
    db: DbSession, category: Category, display_name_pt: str, *, actor_user_id: uuid.UUID | None
) -> Category:
    """Costs nothing: rows reference categories by id, so a rename propagates free."""
    before = audit.snapshot(category)
    category.display_name_pt = display_name_pt.strip()
    db.flush()
    audit.record(
        db,
        action="UPDATE",
        table_name=CATEGORY_TABLE,
        record_id=category.id,
        actor_user_id=actor_user_id,
        before=before,
        after=audit.snapshot(category),
        reason="renomear",
    )
    return category


def reparent_category(
    db: DbSession,
    category: Category,
    new_parent_id: uuid.UUID | None,
    *,
    actor_user_id: uuid.UUID | None,
) -> int:
    """Move a node; recompute maintained ancestors on every affected product."""
    new_parent = get_category(db, new_parent_id) if new_parent_id else None
    if new_parent is not None and new_parent.id in set(subtree_ids(db, category.id)):
        raise ValidationError("Uma categoria não pode ser movida para dentro de si própria.")

    new_level = (new_parent.level + 1) if new_parent else 1
    depth = _subtree_depth(db, category.id)
    if new_level + depth > 3:
        raise ValidationError("A mudança colocaria a árvore acima de três níveis.")

    before = audit.snapshot(category)
    category.parent_id = new_parent.id if new_parent else None
    _relevel(db, category, new_level)
    db.flush()

    affected = _refresh_ancestors(db, subtree_ids(db, category.id))
    audit.record(
        db,
        action="UPDATE",
        table_name=CATEGORY_TABLE,
        record_id=category.id,
        actor_user_id=actor_user_id,
        before=before,
        after={**audit.snapshot(category), "products_refreshed": affected},
        reason="reparentar",
    )
    return affected


def _subtree_depth(db: DbSession, category_id: uuid.UUID) -> int:
    children = list(db.scalars(select(Category.id).where(Category.parent_id == category_id)).all())
    if not children:
        return 0
    return 1 + max(_subtree_depth(db, child) for child in children)


def _relevel(db: DbSession, category: Category, level: int) -> None:
    category.level = level
    for child in db.scalars(select(Category).where(Category.parent_id == category.id)).all():
        _relevel(db, child, level + 1)


def _refresh_ancestors(db: DbSession, category_ids: list[uuid.UUID]) -> int:
    """Thousands of product rows, not the millions of receipt lines the old shape hit."""
    products = db.scalars(
        select(MasterProduct).where(
            MasterProduct.is_deleted.is_(False), MasterProduct.category_id.in_(category_ids)
        )
    ).all()
    for product in products:
        for field, value in ancestry(db, product.category_id).items():
            setattr(product, field, value)
    db.flush()
    return len(products)


def merge_categories(
    db: DbSession,
    *,
    source: Category,
    target: Category,
    actor_user_id: uuid.UUID | None,
) -> int:
    """Fold A into B: every referencing row is reassigned, then A retires."""
    if source.id == target.id:
        raise ValidationError("Uma categoria não pode ser fundida consigo própria.")
    if target.id in set(subtree_ids(db, source.id)):
        raise ValidationError("O destino está dentro da categoria de origem.")

    ids = subtree_ids(db, source.id)
    products = db.scalars(
        select(MasterProduct).where(
            MasterProduct.is_deleted.is_(False), MasterProduct.category_id.in_(ids)
        )
    ).all()
    for product in products:
        before = audit.snapshot(product)
        _apply_category(db, product, target.id)
        # Reassignment is audited row by row, so it is reversible from AuditLog.
        audit.record(
            db,
            action="UPDATE",
            table_name=PRODUCT_TABLE,
            record_id=product.id,
            actor_user_id=actor_user_id,
            before=before,
            after=audit.snapshot(product),
            reason=f"fusão de categorias {source.id} -> {target.id}",
        )

    for category_id in ids:
        node = db.get(Category, category_id)
        if node is not None:
            node.is_deleted = True
    db.flush()
    audit.record(
        db,
        action="DELETE",
        table_name=CATEGORY_TABLE,
        record_id=source.id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(source),
        after={"merged_into": str(target.id), "products_reassigned": len(products)},
    )
    return len(products)


def retire_category(db: DbSession, category: Category, *, actor_user_id: uuid.UUID | None) -> None:
    """Blocked while in use — a category is never silently orphaned."""
    usage = impact(db, category.id)
    if usage.in_use:
        raise Conflict(
            "Esta categoria está em uso. Funda-a noutra em vez de a retirar.",
            master_products=usage.master_products,
            receipt_items=usage.receipt_items,
        )
    for category_id in subtree_ids(db, category.id):
        node = db.get(Category, category_id)
        if node is not None:
            node.is_deleted = True
    db.flush()
    audit.record(
        db,
        action="DELETE",
        table_name=CATEGORY_TABLE,
        record_id=category.id,
        actor_user_id=actor_user_id,
        before=audit.snapshot(category),
    )


# --- Counts for the status board ----------------------------------------------


def uncategorized_count(db: DbSession) -> int:
    """Products never checked by a human — a list that shrinks, not one that grows."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(MasterProduct)
            .where(MasterProduct.is_deleted.is_(False), MasterProduct.category_status == "AUTO")
        )
        or 0
    )


def total_count(db: DbSession) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(MasterProduct)
            .where(MasterProduct.is_deleted.is_(False))
        )
        or 0
    )


def merge_candidate_count(db: DbSession) -> int:
    return len(merge_candidates(db, limit=1000))
