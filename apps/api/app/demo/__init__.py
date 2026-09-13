"""Deterministic Portuguese demo dataset.

Everything fictional lives in ``app/demo/data`` as JSON, one file per module:
the LEGO sets that exist to exercise a sale, a gift, a MOC, a missing part and a
future retirement date; the one receipt whose arithmetic is worth reading; the
household's tags. Nothing here is anybody's real data — the household's own
files are mounted, not packaged, and this only loads them if they happen to be
there (``app.core.defaults``, ADR-0062).

It creates **no users**: the household and its owner come from the first-run setup
(ADR-0011), and this only fills the collection alongside them. Reference data —
merchants, parser profiles — is not demo data and lives in
``app.services.reference_data``, ensured at every boot (ADR-0029); the seed only
re-asserts it so it can run against a database the API has never started against.
The grocery taxonomy is loaded here too, explicitly (ADR-0057): a demo
installation ships with categorised products, but a real installation only gets
the taxonomy when the household asks for it.
Run it after the first login, with ``make seed``. Idempotent — re-running only
fills what is missing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core import defaults as household_defaults
from app.core.db import session_scope
from app.core.errors import ValidationError
from app.demo.images import cover_for
from app.models.core import Merchant, Tag
from app.models.household import Entity, Household
from app.models.lego import LegoSetImage, LegoSetInstance, LegoSetModel, StorageLocation
from app.services import documents, reference_data, settings_service
from app.services.reference_data import slugify
from app.services.supermarket.defaults import PRODUCTS_FILE
from app.services.supermarket.defaults import load_default_categories as _load_default_categories
from app.services.supermarket.defaults import load_default_invoices as _load_default_invoices
from app.services.supermarket.defaults import load_default_products as _load_default_products

#: The fictional data, committed and shipped. Distinct on purpose from
#: ``app.core.defaults``, which points at the household's own mounted files.
DEMO_DIR = Path(__file__).parent / "data"

__all__ = ["main"]


def _demo(name: str) -> Any:
    return json.loads((DEMO_DIR / name).read_text(encoding="utf-8"))


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value else None


def _date(value: str | None) -> dt.date | None:
    """ISO, or the one sentinel a static file cannot express.

    ``76240`` retires at the end of *next* year so the demo always proves that a
    future retirement date does not flag a set as retired today — a fixed date
    would quietly stop testing that the year it passes.
    """
    if not value:
        return None
    if value == "END_OF_NEXT_YEAR":
        return dt.date(dt.date.today().year + 1, 12, 31)
    return dt.date.fromisoformat(value)


# --- Household ---------------------------------------------------------------
def resolve_target(db: DbSession) -> tuple[Household, Entity]:
    """The household and entity the demo data attaches to.

    Both already exist: first-run setup creates the household, the first owner and
    that owner's entity. The seed never invents a user, so an unconfigured
    installation is an error rather than an invitation to create one.
    """
    household = db.scalar(select(Household).order_by(Household.created_at).limit(1))
    if household is None:
        raise ValidationError(
            "Esta instalação ainda não foi configurada. Abra a aplicação e crie o "
            "titular do agregado antes de carregar os dados de demonstração."
        )

    entity = db.scalar(
        select(Entity)
        .where(Entity.household_id == household.id, Entity.is_deleted.is_(False))
        .order_by(Entity.created_at)
        .limit(1)
    )
    if entity is None:
        raise ValidationError("O agregado não tem nenhuma entidade para atribuir os dados.")
    return household, entity


def seed_tags(db: DbSession, household: Household) -> None:
    for tag in _demo("household.json")["tags"]:
        if db.scalar(select(Tag).where(Tag.household_id == household.id, Tag.name == tag["name"])):
            continue
        db.add(Tag(household_id=household.id, name=tag["name"], color=tag["color"]))
    db.flush()


def seed_settings(db: DbSession) -> None:
    for key, value in settings_service.DEFAULTS.items():
        existing = db.scalar(
            select(settings_service.Setting).where(
                settings_service.Setting.key == key,
                settings_service.Setting.scope == "GLOBAL",
            )
        )
        if existing is None:
            settings_service.set_value(db, key, value)


# --- LEGO --------------------------------------------------------------------
_SET_DATES = ("release_date", "retirement_date")
_SET_MONEY = ("rrp_eur", "current_value_eur")
_COPY_DATES = ("acquisition_date", "sale_date")
_COPY_MONEY = ("acquisition_cost_eur", "sale_price_eur")


def _lego_spec(row: dict[str, Any]) -> dict[str, Any]:
    """JSON carries strings; the models want dates, Decimals and a storage key."""
    spec: dict[str, Any] = dict(row)
    for field in _SET_DATES:
        spec[field] = _date(spec.get(field))
    for field in _SET_MONEY:
        spec[field] = _decimal(spec.get(field))
    spec["copies"] = [
        {
            **copy,
            **{field: _date(copy[field]) for field in _COPY_DATES if field in copy},
            **{field: _decimal(copy[field]) for field in _COPY_MONEY if field in copy},
            **({"storage": tuple(copy["storage"])} if copy.get("storage") else {}),
        }
        for copy in row["copies"]
    ]
    return spec


def demo_sets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The invented sets, which exist to exercise what a real collection rarely
    holds all at once: a sale, a gift with no cost basis, a MOC with no set
    number, a copy with missing parts and a retirement date still in the future.
    """
    payload = _demo("lego.json")
    return payload["storage"], [_lego_spec(row) for row in payload["sets"]]


def inventory_sets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The household's own collection, if one is mounted (ADR-0062).

    Converted from their spreadsheet, which records no release or retirement
    information and writes ``0`` where the price paid was never noted — so those
    copies keep a zero cost basis (cost ROI stays ``NULL`` and the PVP reading
    takes over) rather than an invented number. Absent is the normal case: a
    clone that is not this household's has no collection to load.
    """
    if not household_defaults.LEGO_INVENTORY.exists():
        return [], []

    payload = json.loads(household_defaults.LEGO_INVENTORY.read_text(encoding="utf-8"))
    storage = [{"area": row["area"], "container": row["container"]} for row in payload["storage"]]

    specs: list[dict[str, Any]] = []
    for row in payload["sets"]:
        specs.append(
            {
                "set_number": row["set_number"],
                "name": row["name"],
                "theme": row["theme"],
                "short_description": row["short_description"],
                "piece_count": row["piece_count"],
                "minifig_count": row["minifig_count"],
                "rrp_eur": Decimal(row["rrp_eur"]) if row["rrp_eur"] else None,
                "current_value_eur": (
                    Decimal(row["current_value_eur"]) if row["current_value_eur"] else None
                ),
                # Hand-maintained values are only as fresh as the spreadsheet was.
                "value_age_days": 90 if row["current_value_eur"] else None,
                "copies": [
                    {
                        "acquisition_cost_eur": Decimal(copy["acquisition_cost_eur"]),
                        "acquisition_source": copy["acquisition_source"],
                        "storage": tuple(copy["storage"]) if copy["storage"] else None,
                        "build_state": copy["build_state"],
                        "condition": copy["condition"],
                        "has_box": copy.get("has_box", True),
                        "has_instructions": copy.get("has_instructions", True),
                        "missing_parts": copy.get("missing_parts"),
                        "notes": copy.get("notes"),
                    }
                    for copy in row["copies"]
                ],
            }
        )
    return storage, specs


def seed_lego(db: DbSession, entity: Entity, *, alts: int = 3) -> None:
    demo_storage, demo_specs = demo_sets()
    inventory_storage, inventory_specs = inventory_sets()

    locations: dict[tuple[str, str | None], StorageLocation] = {}
    for row in [*demo_storage, *inventory_storage]:
        key = (row["area"], row["container"])
        if key in locations:
            continue
        locations[key] = _storage_location(
            db, row["area"], row["container"], row.get("description"), row.get("capacity_pct")
        )

    today = dt.date.today()
    all_specs = demo_specs + inventory_specs
    total = len(all_specs)
    for index, spec in enumerate(all_specs, start=1):
        # A set number is unique per entity; a MOC has none, so it falls back to
        # its name. Either way, re-running the seed adds nothing twice.
        criterion = (
            LegoSetModel.set_number == spec["set_number"]
            if spec.get("set_number")
            else LegoSetModel.name == spec["name"]
        )
        existing = db.scalar(
            select(LegoSetModel).where(LegoSetModel.entity_id == entity.id, criterion)
        )
        if existing is not None:
            continue

        # Downloading box/gallery images is the slow part (one HTTP round-trip per
        # set, up to a 20s timeout each on a miss), so this is the one loop worth
        # a progress line.
        print(f"  [{index}/{total}] {spec.get('set_number') or '—'} {spec['name']}", flush=True)

        value_age = spec.get("value_age_days")
        model = LegoSetModel(
            entity_id=entity.id,
            set_number=spec.get("set_number"),
            is_custom=bool(spec.get("is_custom")),
            name=spec["name"],
            theme=spec.get("theme"),
            subtheme=spec.get("subtheme"),
            release_date=spec.get("release_date"),
            retirement_date=spec.get("retirement_date"),
            piece_count=spec.get("piece_count"),
            minifig_count=spec.get("minifig_count"),
            rrp_eur=spec.get("rrp_eur"),
            current_value_eur=spec.get("current_value_eur"),
            value_updated_at=(
                today - dt.timedelta(days=value_age) if value_age is not None else None
            ),
            short_description=spec.get("short_description"),
        )
        db.add(model)
        db.flush()
        _seed_images(db, model, alts=alts)

        for copy_spec in spec["copies"]:
            storage_key = copy_spec.get("storage")
            db.add(
                LegoSetInstance(
                    entity_id=entity.id,
                    lego_set_model_id=model.id,
                    acquisition_date=copy_spec.get("acquisition_date"),
                    acquisition_cost_eur=copy_spec["acquisition_cost_eur"],
                    acquisition_source=copy_spec.get("acquisition_source"),
                    storage_location_id=(locations[storage_key].id if storage_key else None),
                    build_state=copy_spec.get("build_state"),
                    condition=copy_spec.get("condition"),
                    has_box=copy_spec.get("has_box", True),
                    has_instructions=copy_spec.get("has_instructions", True),
                    missing_parts=copy_spec.get("missing_parts"),
                    ownership_status=copy_spec.get("ownership_status", "IN_COLLECTION"),
                    sale_price_eur=copy_spec.get("sale_price_eur"),
                    sale_date=copy_spec.get("sale_date"),
                    notes=copy_spec.get("notes"),
                )
            )
    db.flush()


#: Box shot + gallery, fetched once by ``dev/download-lego-images.py`` into the
#: household's mounted defaults. The seed itself never touches the network — a NAS
#: with no internet, a set Brickset never photographed and a MOC all just end up
#: on the placeholder instead.
IMAGES_DIR = household_defaults.LEGO_IMAGES


def _seed_images(db: DbSession, model: LegoSetModel, *, alts: int) -> None:
    """Box shot as the cover, then whatever extra views were downloaded, as the gallery."""
    number = model.set_number
    folder = IMAGES_DIR / number if number else None
    box_path = folder / "box.jpg" if folder else None
    if box_path is not None and box_path.exists():
        model.image_document_id = documents.store_bytes(
            db, box_path.read_bytes(), original_filename=box_path.name
        ).id
        for index in range(1, alts + 1):
            alt_path = folder / f"alt{index}.jpg"  # type: ignore[operator]
            if not alt_path.exists():
                break  # the set simply has no further views
            document = documents.store_bytes(
                db, alt_path.read_bytes(), original_filename=alt_path.name
            )
            db.add(
                LegoSetImage(
                    lego_set_model_id=model.id,
                    document_id=document.id,
                    position=index - 1,
                )
            )

    if model.image_document_id is None:
        placeholder = documents.store_bytes(
            db,
            cover_for(model.theme),
            original_filename=f"{number or slugify(model.name)}.png",
        )
        model.image_document_id = placeholder.id
    db.flush()


def _storage_location(
    db: DbSession,
    area: str,
    container: str | None,
    description: str | None = None,
    capacity_pct: int | None = None,
) -> StorageLocation:
    location = db.scalar(
        select(StorageLocation).where(
            StorageLocation.area == area,
            StorageLocation.container.is_(None)
            if container is None
            else StorageLocation.container == container,
        )
    )
    if location is None:
        location = StorageLocation(
            area=area,
            container=container,
            description=description,
            capacity_pct=capacity_pct,
        )
        db.add(location)
        db.flush()
    return location


# --- Supermarket (M1) --------------------------------------------------------
#: One hand-written receipt that exercises the cases the real *talões* do not all
#: carry at once: an appended Fs article, a loyalty discount prorated across the
#: lines, a refund with a negative quantity, and a deposit return.
DEMO_RECEIPT: dict[str, Any] = _demo("supermarket.json")["receipt"]
DEMO_RECEIPT_LINES: list[dict[str, Any]] = DEMO_RECEIPT["lines"]
DEMO_FS_ARTICLE: dict[str, Any] = DEMO_RECEIPT["fs_article"]


def _find_or_create_demo_product(db: DbSession, line: dict[str, Any]):  # type: ignore[no-untyped-def]
    """Reuse whatever the legacy import already created — the seed never forks it."""
    from app.models.products import MasterProduct
    from app.services.supermarket import products_service

    name = str(line["description"]).title()
    existing = db.scalar(
        select(MasterProduct).where(
            func.lower(MasterProduct.canonical_name) == name.lower(),
            MasterProduct.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing
    return products_service.create_product(
        db,
        canonical_name=name,
        category_status="AUTO",
        sold_by_weight=bool(line.get("bulk")),
    )


def seed_supermarket(db: DbSession, entity: Entity) -> None:
    """A demo receipt whose arithmetic is worth reading, plus its price history."""
    from app.models.supermarket import SupermarketReceipt, SupermarketReceiptItem
    from app.services.supermarket import arithmetic, prices_service
    from app.services.supermarket import service as receipts_service
    from app.services.supermarket.normalize import normalize_description

    merchant = db.scalar(select(Merchant).where(Merchant.name == DEMO_RECEIPT["merchant"]))
    if merchant is None:
        return
    purchased_at = dt.datetime.fromisoformat(DEMO_RECEIPT["purchased_at"])
    if db.scalar(
        select(SupermarketReceipt).where(
            SupermarketReceipt.entity_id == entity.id,
            SupermarketReceipt.purchased_at == purchased_at,
        )
    ):
        return

    gross = sum(Decimal(line["pvp"]) for line in DEMO_RECEIPT_LINES)
    promos = sum(Decimal(line["promo"]) for line in DEMO_RECEIPT_LINES)
    loyalty_discount = Decimal(DEMO_RECEIPT["loyalty_discount_eur"])
    total = gross - promos - loyalty_discount

    receipt = SupermarketReceipt(
        entity_id=entity.id,
        merchant_id=merchant.id,
        purchased_at=purchased_at,
        purchase_date=purchased_at.date(),
        total_eur=total,
        total_discount_eur=loyalty_discount,
        item_count=len(DEMO_RECEIPT_LINES),
        status="NEEDS_REVIEW",
        confidence=Decimal("0.720"),
        decision_reasons=[{"rule": "seed", "detail": "Fatura de demonstração.", "score": "0.720"}],
        loyalty_scheme=DEMO_RECEIPT["loyalty_scheme"],
        loyalty_card_masked=DEMO_RECEIPT["loyalty_card_masked"],
        loyalty_discount_eur=loyalty_discount,
        loyalty_accrued_eur=Decimal(DEMO_RECEIPT["loyalty_accrued_eur"]),
        parsed_payment_methods=[{"method": "Multibanco", "amount_eur": str(total)}],
    )
    db.add(receipt)
    db.flush()

    allocations = arithmetic.prorate_invoice_discount(
        [
            arithmetic.ProrationInput(Decimal(line["pvp"]), Decimal(line["promo"]))
            for line in DEMO_RECEIPT_LINES
        ],
        loyalty_discount,
    )
    for index, (line, allocated) in enumerate(
        zip(DEMO_RECEIPT_LINES, allocations, strict=True), start=1
    ):
        product = _find_or_create_demo_product(db, line)
        quantity = Decimal(line["quantity"])
        unit = line.get("unit", "UN")
        canonical, canonical_unit = arithmetic.canonical_quantity(quantity, unit)
        db.add(
            SupermarketReceiptItem(
                receipt_id=receipt.id,
                entity_id=entity.id,
                line_no=index,
                merchant_section=line["section"],
                description_raw=line["description"],
                description_norm=normalize_description(line["description"]),
                master_product_id=product.id,
                quantity=quantity,
                unit=unit,
                quantity_canonical=canonical,
                unit_canonical=canonical_unit,
                weight_observed_kg=Decimal(line["weight"]) if line.get("weight") else None,
                is_bulk_weighed=bool(line.get("bulk")),
                unit_price_pvp_eur=Decimal(line["pvp"]),
                promo_discount_eur=Decimal(line["promo"]),
                invoice_allocated_discount_eur=allocated,
                paid_price_eur=arithmetic.paid_from_components(
                    unit_price_pvp_eur=Decimal(line["pvp"]),
                    promo_discount_eur=Decimal(line["promo"]),
                    invoice_allocated_discount_eur=allocated,
                ),
                iva_class_raw=line["iva"],
                product_flag=line.get("flag"),
                confidence=Decimal("0.800"),
                decision_reasons=[
                    {"rule": "seed", "detail": "Linha de demonstração.", "score": "0.800"}
                ],
            )
        )
    db.flush()
    db.refresh(receipt)

    # Appended by hand afterwards: it changes no printed figure at all.
    receipts_service.append_fs_item(
        db,
        receipt,
        description_raw=str(DEMO_FS_ARTICLE["description"]),
        unit_price_pvp_eur=Decimal(str(DEMO_FS_ARTICLE["value"])),
    )
    prices_service.record_observations(db, receipt)


def seed_categories(db: DbSession) -> int:
    """Thin wrapper so `main()` reports this step like every other one."""
    return _load_default_categories(db, actor_user_id=None)


def seed_products(db: DbSession) -> int:
    """Thin wrapper so `main()` reports this step like every other one."""
    return _load_default_products(db, actor_user_id=None)


def seed_supermarket_invoices(db: DbSession, entity: Entity) -> int:
    """Thin wrapper so `main()` reports this step like every other one."""
    return _load_default_invoices(db, entity_id=entity.id, actor_user_id=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Carrega os dados de demonstração.")
    parser.add_argument(
        "--alts",
        type=int,
        default=3,
        help="Máximo de imagens adicionais por conjunto (0 desliga a galeria).",
    )
    args = parser.parse_args()

    def step(label, fn, /, **fn_kwargs):
        started = time.monotonic()
        print(f"-> {label}...", flush=True)
        result = fn(**fn_kwargs)
        print(f"   done in {time.monotonic() - started:.1f}s", flush=True)
        return result

    try:
        with session_scope() as db:
            household, entity = resolve_target(db)
            step("settings", seed_settings, db=db)
            step("reference data", reference_data.ensure_all, db=db)
            step("grocery taxonomy", seed_categories, db=db)
            products = step("product catalogue", seed_products, db=db)
            step("tags", seed_tags, db=db, household=household)
            step("supermarket demo receipt", seed_supermarket, db=db, entity=entity)
            invoices = step("supermarket invoices", seed_supermarket_invoices, db=db, entity=entity)
            step("LEGO collection", seed_lego, db=db, entity=entity, alts=max(0, args.alts))
    except ValidationError as exc:
        sys.exit(exc.detail)

    print(f"Seed concluído em «{household.name}», atribuído a «{entity.name}».")
    print(f"Ficheiros do agregado lidos de {household_defaults.DEFAULTS_DIR}.")
    print(f"Faturas reais carregadas: {invoices}.")
    print(
        f"Produtos do catálogo: {products}."
        if products
        else f"Catálogo de produtos ignorado (sem {PRODUCTS_FILE.name})."
    )


if __name__ == "__main__":
    main()
