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
import io
import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import openpyxl
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.core import audit
from app.core.errors import AppError, Conflict, NotFound, ValidationError
from app.models.core import Category
from app.models.products import MasterProduct, ProductAlias
from app.models.supermarket import SupermarketReceiptItem
from app.services.supermarket import catalogue, classify
from app.services.supermarket.normalize import normalize_description

GROCERY = "GROCERY"
PRODUCT_TABLE = "master_products"
CATEGORY_TABLE = "categories"

#: One gram. Finer than that is noise on a till receipt, and rounding both sides
#: to the same quantum is what lets a parsed token and a curated format compare
#: as equals without a foreign key between them.
WEIGHT_QUANTUM = Decimal("0.001")


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


# --- Pack formats -------------------------------------------------------------


def round_to_the_gram(value: Any) -> Decimal | None:
    """The single normalisation every pack weight passes through, on both sides."""
    if value is None or value == "":
        return None
    try:
        weight = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None
    if not weight.is_finite() or weight <= 0:
        return None
    return weight.quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)


def pack_variant_label(weight_kg: Decimal) -> str:
    """``0,5`` reads as ``500 g`` and ``1`` as ``1 kg``.

    Derived rather than typed so a label can never contradict the weight it names.
    """
    if weight_kg < 1:
        return f"{(weight_kg * 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP):f} g"
    return f"{weight_kg.normalize():f}".replace(".", ",") + " kg"


def sanitize_pack_variants(variants: Iterable[Any] | None) -> list[dict[str, Any]]:
    """One entry per weight, rounded to the gram, ordered, weights as strings.

    Unique weights are what let a receipt line find its format **by value**: with
    no two formats sharing a weight, "which format is this line?" always has one
    answer and needs no foreign key. Strings because JSONB cannot hold a Decimal.
    """
    cleaned: dict[Decimal, dict[str, Any]] = {}
    for variant in variants or []:
        data = dict(variant)
        weight = round_to_the_gram(data.get("weight_kg"))
        if weight is None:
            raise ValidationError("Cada formato precisa de um peso maior do que zero.")
        if weight in cleaned:
            raise ValidationError(f"O formato {pack_variant_label(weight)} está repetido.")
        label = str(data.get("label") or "").strip()
        cleaned[weight] = {
            **data,
            "label": label or pack_variant_label(weight),
            "weight_kg": str(weight),
        }
    return [cleaned[weight] for weight in sorted(cleaned)]


def pack_weights(product: MasterProduct) -> set[Decimal]:
    weights = (round_to_the_gram(dict(v).get("weight_kg")) for v in product.pack_variants)
    return {weight for weight in weights if weight is not None}


def add_pack_variant(
    db: DbSession,
    product: MasterProduct,
    *,
    weight_kg: Decimal,
    label: str | None = None,
    barcode: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> MasterProduct:
    """Append one format, idempotent on the weight.

    Idempotent rather than a read-modify-write of the whole list so the review
    pane can add the format it just read off a line without knowing the others,
    and so two people reviewing at once cannot drop each other's formats.
    """
    weight = round_to_the_gram(weight_kg)
    if weight is None:
        raise ValidationError("O formato precisa de um peso maior do que zero.")
    if weight in pack_weights(product):
        return product

    variants = [dict(variant) for variant in product.pack_variants]
    variants.append(
        {
            "label": (label or "").strip() or pack_variant_label(weight),
            "weight_kg": str(weight),
            "barcode": barcode,
        }
    )
    return update_product(
        db,
        product,
        {"pack_variants": sanitize_pack_variants(variants)},
        actor_user_id=actor_user_id,
    )


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
        pack_variants=sanitize_pack_variants(pack_variants),
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
        db.query(SupermarketReceiptItem)
        .filter(SupermarketReceiptItem.master_product_id == source.id)
        .update({SupermarketReceiptItem.master_product_id: target.id}, synchronize_session="fetch")
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
    db: DbSession, item: SupermarketReceiptItem, *, merchant_id: uuid.UUID | None
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
            .select_from(SupermarketReceiptItem)
            .join(MasterProduct, MasterProduct.id == SupermarketReceiptItem.master_product_id)
            .where(SupermarketReceiptItem.is_deleted.is_(False), MasterProduct.category_id.in_(ids))
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


# --- Bulk import (curated product log) ----------------------------------------
#
# A curated log has no per-row external lookup (there is no Brickset-equivalent
# here), so unlike LEGO's bulk import there is no reason to split preview from
# commit across a slow network call — both run against the local database only.
# The split is kept anyway, for the same reason: a preview of 500 rows must be
# safe to show and re-show without writing anything, and the review table needs
# a resolved `category_id`/`existing_product_id` per row before the human ever
# presses "Importar".

_PRODUCT_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "canonical_name": ("nome", "produto", "nome canonico", "nome do produto"),
    "brand": ("marca",),
    "category_path": ("categoria", "categoria completa"),
    "sold_by_weight": ("vendido a peso", "a peso", "venda a peso"),
    "pack_weights": ("formatos", "formatos kg", "pesos", "pesos kg"),
}

_TRUTHY_TOKENS = {"sim", "true", "1", "x", "yes"}


def _norm(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return _norm(str(value)) in _TRUTHY_TOKENS


def parse_product_import_file(data: bytes) -> list[dict[str, Any]]:
    """The first worksheet, columns matched by normalized header name — not
    position — so a hand-edited spreadsheet's column order never matters."""
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationError("Não foi possível ler a folha de cálculo.") from exc

    sheet = workbook.worksheets[0]
    iterator = sheet.iter_rows(values_only=True)
    header_row = next(iterator, None)
    if header_row is None:
        return []

    columns: dict[str, int] = {}
    for index, cell in enumerate(header_row):
        if cell is None:
            continue
        normalized = _norm(str(cell))
        for field_name, alias_list in _PRODUCT_HEADER_ALIASES.items():
            if field_name not in columns and normalized in alias_list:
                columns[field_name] = index

    rows: list[dict[str, Any]] = []
    for row_number, values in enumerate(iterator, start=2):
        if all(value in (None, "") for value in values):
            continue
        row: dict[str, Any] = {"_row": row_number}
        for field_name, index in columns.items():
            row[field_name] = values[index] if index < len(values) else None
        rows.append(row)
    return rows


def find_category_by_path(db: DbSession, path: str | None) -> Category | None:
    """Walks ``L1 › L2 › L3`` (also accepts ``>``/``/``) down the tree, matching
    each level's display name case-insensitively under the parent already
    resolved — the same separator ``category_path()`` writes on the way out."""
    if not path:
        return None
    parts = [part.strip() for part in re.split(r"[›>/|]", path) if part.strip()]
    if not parts:
        return None

    parent_id: uuid.UUID | None = None
    node: Category | None = None
    for part in parts:
        stmt = select(Category).where(
            Category.domain == GROCERY,
            Category.is_deleted.is_(False),
            func.lower(Category.display_name_pt) == part.lower(),
        )
        stmt = (
            stmt.where(Category.parent_id == parent_id)
            if parent_id
            else stmt.where(Category.parent_id.is_(None))
        )
        node = db.scalar(stmt)
        if node is None:
            return None
        parent_id = node.id
    return node


def _resolve_bulk_row(db: DbSession, raw: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, str] = {}

    name = str(raw.get("canonical_name") or "").strip()
    if not name:
        errors["canonical_name"] = "Nome em falta."

    brand_raw = raw.get("brand")
    brand = str(brand_raw).strip() or None if brand_raw not in (None, "") else None

    category_path_raw = raw.get("category_path")
    path_value = (
        str(category_path_raw).strip() or None if category_path_raw not in (None, "") else None
    )
    category = find_category_by_path(db, path_value) if path_value else None
    if path_value and category is None:
        errors["category_path"] = "Categoria não encontrada."

    pack_weights: list[Decimal] = []
    weights_raw = raw.get("pack_weights")
    if weights_raw not in (None, ""):
        for token in re.split(r"[,;]", str(weights_raw)):
            token = token.strip()
            if not token:
                continue
            weight = round_to_the_gram(token.replace(",", "."))
            if weight is None:
                errors["pack_weights"] = f"Peso inválido: «{token}»."
                continue
            pack_weights.append(weight)

    existing_id: uuid.UUID | None = None
    if name:
        existing = db.scalar(
            select(MasterProduct).where(
                func.lower(MasterProduct.canonical_name) == name.lower(),
                MasterProduct.brand.is_(None) if brand is None else MasterProduct.brand == brand,
                MasterProduct.is_deleted.is_(False),
            )
        )
        if existing is not None:
            existing_id = existing.id

    return {
        "row_number": raw["_row"],
        "canonical_name": name or None,
        "brand": brand,
        "category_path": path_value,
        "category_id": category.id if category else None,
        "sold_by_weight": _parse_bool(raw.get("sold_by_weight")),
        "pack_weights_kg": pack_weights,
        "existing_product_id": existing_id,
        "errors": errors,
    }


def preview_product_import(db: DbSession, data: bytes) -> list[dict[str, Any]]:
    return [_resolve_bulk_row(db, raw) for raw in parse_product_import_file(data)]


def commit_product_import(
    db: DbSession, rows: list[dict[str, Any]], *, actor_user_id: uuid.UUID | None
) -> list[dict[str, Any]]:
    """One row at a time, each its own try/except: one bad row never sinks the
    batch. Committed (or rolled back) per row rather than once at the end, so a
    later failure cannot undo an earlier success."""
    results: list[dict[str, Any]] = []
    for row in rows:
        row_number = row["row_number"]
        try:
            existing_id = row.get("existing_product_id")
            if existing_id:
                results.append(
                    {
                        "row_number": row_number,
                        "ok": True,
                        "skipped": True,
                        "message": "Já existe um produto com este nome e marca — ignorado.",
                        "master_product_id": existing_id,
                    }
                )
                continue

            name = row.get("canonical_name")
            if not name:
                raise ValidationError("O produto precisa de um nome.")

            pack_variants = [
                {"weight_kg": str(weight)} for weight in row.get("pack_weights_kg") or []
            ]
            product = create_product(
                db,
                canonical_name=name,
                brand=row.get("brand"),
                category_id=row.get("category_id"),
                sold_by_weight=bool(row.get("sold_by_weight")),
                pack_variants=pack_variants,
                actor_user_id=actor_user_id,
            )
            db.commit()
            results.append(
                {
                    "row_number": row_number,
                    "ok": True,
                    "skipped": False,
                    "message": "Produto criado.",
                    "master_product_id": product.id,
                }
            )
        except AppError as exc:
            db.rollback()
            results.append(
                {
                    "row_number": row_number,
                    "ok": False,
                    "skipped": False,
                    "message": exc.detail,
                    "master_product_id": None,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive, mirrors lego_bulk_import
            db.rollback()
            results.append(
                {
                    "row_number": row_number,
                    "ok": False,
                    "skipped": False,
                    "message": str(exc),
                    "master_product_id": None,
                }
            )
    return results
