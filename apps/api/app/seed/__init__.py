"""Deterministic Portuguese demo dataset.

Idempotent: re-running only fills what is missing. Run with ``make seed``.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.core.db import session_scope
from app.core.security import hash_password
from app.models.core import Category, Merchant, Tag
from app.models.household import Entity, Household, HouseholdMember, User
from app.models.lego import LegoSetInstance, LegoSetModel, StorageLocation
from app.seed.images import cover_for
from app.services import documents, settings_service

DATA_DIR = Path(__file__).parent / "data"
TAXONOMY_FILE = DATA_DIR / "supermarket-categories.pt-PT.json"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")


# --- Household ---------------------------------------------------------------
def seed_household(db: DbSession) -> tuple[Household, dict[str, User], dict[str, Entity]]:
    household = db.scalar(select(Household).limit(1))
    if household is None:
        household = Household(name=settings.bootstrap_household_name)
        db.add(household)
        db.flush()

    people = [
        ("owner", settings.bootstrap_owner_email, "Ana", "OWNER", False),
        ("partner", "bruno@finmanager.local", "Bruno", "MEMBER", False),
        ("child", None, "Clara", "VIEWER", True),
    ]
    users: dict[str, User] = {}
    for key, email, display_name, role, is_dependent in people:
        user = db.scalar(
            select(User).where(
                (User.email == email) if email else (User.display_name == display_name)
            )
        )
        if user is None:
            user = User(
                email=email,
                display_name=display_name,
                password_hash=(
                    None if is_dependent else hash_password(settings.bootstrap_owner_password)
                ),
                role=role,
                is_dependent=is_dependent,
                must_change_password=False,
            )
            db.add(user)
            db.flush()
        users[key] = user

        membership = db.scalar(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household.id,
                HouseholdMember.user_id == user.id,
            )
        )
        if membership is None:
            db.add(HouseholdMember(household_id=household.id, user_id=user.id, role=role))

    db.flush()
    household.created_by = users["owner"].id

    entity_specs = [
        ("Ana", [users["owner"].id], "#2563eb"),
        ("Bruno", [users["partner"].id], "#0d9488"),
        ("Clara", [users["child"].id], "#c026d3"),
        ("Ana & Bruno", [users["owner"].id, users["partner"].id], "#ea580c"),
    ]
    entities: dict[str, Entity] = {}
    for name, member_ids, color in entity_specs:
        entity = db.scalar(
            select(Entity).where(Entity.household_id == household.id, Entity.name == name)
        )
        if entity is None:
            entity = Entity(
                household_id=household.id, name=name, member_ids=member_ids, color=color
            )
            db.add(entity)
            db.flush()
        entities[name] = entity

    return household, users, entities


# --- Reference data ----------------------------------------------------------
def seed_categories(db: DbSession) -> None:
    if db.scalar(select(func.count()).select_from(Category).where(Category.domain == "GROCERY")):
        return
    if not TAXONOMY_FILE.exists():  # pragma: no cover
        return

    payload = json.loads(TAXONOMY_FILE.read_text(encoding="utf-8"))
    brand_axis_l2 = {"Gelados", "Pastilhas"}

    for l1_name, l2_map in payload["categories"].items():
        l1 = Category(
            code_en=slugify(l1_name),
            display_name_pt=l1_name,
            domain="GROCERY",
            level=1,
        )
        db.add(l1)
        db.flush()
        for l2_name, l3_names in l2_map.items():
            l2 = Category(
                code_en=f"{slugify(l1_name)}__{slugify(l2_name)}",
                display_name_pt=l2_name,
                domain="GROCERY",
                level=2,
                parent_id=l1.id,
                brand_axis=l2_name in brand_axis_l2,
            )
            db.add(l2)
            db.flush()
            for l3_name in l3_names:
                db.add(
                    Category(
                        code_en=f"{slugify(l1_name)}__{slugify(l2_name)}__{slugify(l3_name)}",
                        display_name_pt=l3_name,
                        domain="GROCERY",
                        level=3,
                        parent_id=l2.id,
                    )
                )
    db.flush()


PORTUGUESE_MERCHANTS = [
    ("Continente", "RETAIL", "https://www.continente.pt"),
    ("Pingo Doce", "RETAIL", "https://www.pingodoce.pt"),
    ("Auchan", "RETAIL", "https://www.auchan.pt"),
    ("Lidl", "RETAIL", "https://www.lidl.pt"),
    ("Aldi", "RETAIL", "https://www.aldi.pt"),
    ("El Corte Inglés", "RETAIL", None),
    ("Galp", "SERVICE_PROVIDER", "https://www.galp.pt"),
    ("BP", "SERVICE_PROVIDER", None),
    ("EDP Comercial", "UTILITY_PROVIDER", "https://www.edp.pt"),
    ("Águas de Gaia", "UTILITY_PROVIDER", None),
    ("Millennium bcp", "BANK", None),
    ("Caixa Geral de Depósitos", "BANK", None),
    ("Médis", "INSURER", None),
    ("Farmácia Central", "RETAIL", None),
]


def seed_merchants(db: DbSession) -> None:
    for name, kind, website in PORTUGUESE_MERCHANTS:
        if db.scalar(select(Merchant).where(Merchant.name == name)):
            continue
        db.add(Merchant(name=name, kind=kind, website=website, aliases=[]))
    db.flush()


def seed_tags(db: DbSession, household: Household) -> None:
    for name, color in [
        ("férias", "#0ea5e9"),
        ("culinária", "#f59e0b"),
        ("social", "#8b5cf6"),
        ("Clara", "#ec4899"),
    ]:
        if db.scalar(select(Tag).where(Tag.household_id == household.id, Tag.name == name)):
            continue
        db.add(Tag(household_id=household.id, name=name, color=color))
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
    if settings.brickset_api_key:
        settings_service.set_value(db, settings_service.BRICKSET_API_KEY, settings.brickset_api_key)


# --- LEGO --------------------------------------------------------------------
STORAGE: list[tuple[str, str, str, int | None]] = [
    ("Garagem", "Caixa TV", "Caixa grande junto à televisão antiga", 75),
    ("Garagem", "Caixa A", "Caixa de arrumação empilhável", 40),
    ("Casa", "Armário", "Armário do escritório", 90),
    ("Casa", "Montado", "Sets expostos, já construídos", None),
    ("Casa", "A uso", "Peças em utilização pela Clara", 100),
]

SETS: list[dict[str, Any]] = [
    {
        "set_number": "10307",
        "name": "Torre Eiffel",
        "theme": "Icons",
        "subtheme": "Landmarks",
        "release_year": 2022,
        "retired_year": None,
        "piece_count": 10001,
        "minifig_count": 0,
        "rrp_eur": Decimal("629.99"),
        "current_value_eur": Decimal("689.00"),
        "value_age_days": 20,
        "short_description": (
            "Réplica de 149 cm da Torre Eiffel, o maior conjunto LEGO alguma vez lançado."
        ),
        "copies": [
            {
                "acquisition_date": dt.date(2023, 3, 18),
                "acquisition_cost_eur": Decimal("599.99"),
                "acquisition_source": "RETAIL",
                "storage": ("Garagem", "Caixa TV"),
                "build_state": "SEALED",
                "condition": "NEW",
            },
            {
                "acquisition_date": dt.date(2024, 11, 29),
                "acquisition_cost_eur": Decimal("529.00"),
                "acquisition_source": "SECONDHAND",
                "storage": ("Casa", "Montado"),
                "build_state": "BUILT",
                "condition": "GOOD",
                "has_box": False,
                "notes": "Comprado na Black Friday, montado na sala.",
            },
        ],
    },
    {
        "set_number": "75192",
        "name": "Millennium Falcon",
        "theme": "Star Wars",
        "subtheme": "Ultimate Collector Series",
        "release_year": 2017,
        "retired_year": None,
        "piece_count": 7541,
        "minifig_count": 10,
        "rrp_eur": Decimal("849.99"),
        "current_value_eur": Decimal("920.00"),
        "value_age_days": 250,
        "short_description": "A versão UCS da nave mais famosa da galáxia.",
        "copies": [
            {
                "acquisition_date": dt.date(2019, 12, 20),
                "acquisition_cost_eur": Decimal("739.90"),
                "acquisition_source": "RETAIL",
                "storage": ("Casa", "Armário"),
                "build_state": "DISASSEMBLED",
                "condition": "GOOD",
                "missing_parts": "2x 3001 vermelho, 1x canopy transparente",
            }
        ],
    },
    {
        "set_number": "21318",
        "name": "Casa da Árvore",
        "theme": "Ideas",
        "release_year": 2019,
        "retired_year": 2023,
        "piece_count": 3036,
        "minifig_count": 4,
        "rrp_eur": Decimal("219.99"),
        "current_value_eur": Decimal("349.00"),
        "value_age_days": 45,
        "short_description": "Conjunto Ideas com folhagem em plástico de origem vegetal.",
        "copies": [
            {
                "acquisition_date": dt.date(2021, 6, 5),
                "acquisition_cost_eur": Decimal("199.99"),
                "acquisition_source": "RETAIL",
                "storage": ("Garagem", "Caixa A"),
                "build_state": "SEALED",
                "condition": "NEW",
            }
        ],
    },
    {
        "set_number": "42115",
        "name": "Lamborghini Sián FKP 37",
        "theme": "Technic",
        "release_year": 2020,
        "retired_year": 2023,
        "piece_count": 3696,
        "minifig_count": 0,
        "rrp_eur": Decimal("379.99"),
        "current_value_eur": None,
        "short_description": "Supercarro Technic à escala 1:8 com caixa de 8 velocidades.",
        "copies": [
            {
                "acquisition_date": dt.date(2022, 12, 25),
                "acquisition_cost_eur": Decimal("0.00"),
                "acquisition_source": "GIFT",
                "storage": ("Casa", "Montado"),
                "build_state": "BUILT",
                "condition": "GOOD",
                "notes": "Prenda de Natal — sem custo, logo sem ROI.",
            }
        ],
    },
    {
        "set_number": "10497",
        "name": "Galaxy Explorer",
        "theme": "Icons",
        "subtheme": "90 Anos",
        "release_year": 2022,
        "retired_year": 2024,
        "piece_count": 1254,
        "minifig_count": 4,
        "rrp_eur": Decimal("99.99"),
        "current_value_eur": Decimal("119.00"),
        "value_age_days": 400,
        "short_description": "Reinterpretação do clássico Classic Space de 1979.",
        "copies": [
            {
                "acquisition_date": dt.date(2022, 8, 1),
                "acquisition_cost_eur": Decimal("94.99"),
                "acquisition_source": "RETAIL",
                "storage": ("Garagem", "Caixa TV"),
                "build_state": "SEALED",
                "condition": "NEW",
            },
            {
                "acquisition_date": dt.date(2022, 8, 1),
                "acquisition_cost_eur": Decimal("94.99"),
                "acquisition_source": "RETAIL",
                "ownership_status": "SOLD",
                "sale_price_eur": Decimal("140.00"),
                "sale_date": dt.date(2024, 5, 12),
                "build_state": "SEALED",
                "condition": "NEW",
                "notes": "Vendido no OLX — fora de todos os KPIs de valor.",
            },
        ],
    },
    {
        "set_number": None,
        "is_custom": True,
        "name": "Farol de Leça (MOC)",
        "theme": "MOC",
        "piece_count": 820,
        "current_value_eur": None,
        "short_description": "Construção original do farol da Boa Nova, feita à mão pela Clara.",
        "copies": [
            {
                "acquisition_date": dt.date(2024, 2, 10),
                "acquisition_cost_eur": Decimal("45.00"),
                "acquisition_source": "OTHER",
                "storage": ("Casa", "A uso"),
                "build_state": "BUILT",
                "condition": "GOOD",
                "has_box": False,
                "has_instructions": False,
            }
        ],
    },
]


def seed_lego(db: DbSession, entities: dict[str, Entity]) -> None:
    owner_entity = entities["Ana & Bruno"]
    child_entity = entities["Clara"]

    locations: dict[tuple[str, str], StorageLocation] = {}
    for area, container, description, capacity in STORAGE:
        location = db.scalar(
            select(StorageLocation).where(
                StorageLocation.entity_id == owner_entity.id,
                StorageLocation.area == area,
                StorageLocation.container == container,
            )
        )
        if location is None:
            location = StorageLocation(
                entity_id=owner_entity.id,
                area=area,
                container=container,
                description=description,
                capacity_pct=capacity,
            )
            db.add(location)
            db.flush()
        locations[(area, container)] = location

    today = dt.date.today()
    for spec in SETS:
        entity = child_entity if spec.get("is_custom") else owner_entity
        existing = db.scalar(
            select(LegoSetModel).where(
                LegoSetModel.entity_id == entity.id, LegoSetModel.name == spec["name"]
            )
        )
        if existing is not None:
            continue

        value_age = spec.get("value_age_days")
        cover = documents.store_bytes(
            db,
            cover_for(spec.get("theme")),
            original_filename=f"{spec.get('set_number') or slugify(spec['name'])}.png",
        )
        model = LegoSetModel(
            entity_id=entity.id,
            set_number=spec.get("set_number"),
            is_custom=bool(spec.get("is_custom")),
            name=spec["name"],
            theme=spec.get("theme"),
            subtheme=spec.get("subtheme"),
            release_year=spec.get("release_year"),
            retired_year=spec.get("retired_year"),
            piece_count=spec.get("piece_count"),
            minifig_count=spec.get("minifig_count"),
            rrp_eur=spec.get("rrp_eur"),
            current_value_eur=spec.get("current_value_eur"),
            value_updated_at=(
                today - dt.timedelta(days=value_age) if value_age is not None else None
            ),
            short_description=spec.get("short_description"),
            image_document_id=cover.id,
        )
        db.add(model)
        db.flush()

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


def main() -> None:
    with session_scope() as db:
        household, _users, entities = seed_household(db)
        seed_settings(db)
        seed_categories(db)
        seed_merchants(db)
        seed_tags(db, household)
        seed_lego(db, entities)

    print("Seed concluído.")
    print(f"  Login: {settings.bootstrap_owner_email} / {settings.bootstrap_owner_password}")


if __name__ == "__main__":
    main()
