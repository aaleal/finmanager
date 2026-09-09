"""Reference data every installation needs, ensured at boot.

The grocery taxonomy and the merchant parser profiles are not demonstration
data: an empty installation cannot read a *talão* without a parser profile, nor
file a product without a category. They ship with the application and are
ensured on every API start (ADR-0029), so a clean database is usable before
anything is seeded and a taxonomy that grows in a release reaches installations
that were created before it.

Every ``ensure_*`` function is row-level idempotent: it fills what is missing
and never overwrites — or resurrects — what the household has since edited.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

from app.models.core import Category, Merchant
from app.models.supermarket import MerchantParserProfile

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TAXONOMY_FILE = DATA_DIR / "supermarket-categories.pt-PT.json"

#: L2 categories where the brand *is* the axis people shop by (FR-1.19).
BRAND_AXIS_L2 = {"Gelados", "Pastilhas"}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")


# --- Grocery taxonomy ---------------------------------------------------------
def ensure_categories(db: DbSession) -> int:
    """Create the grocery nodes this release ships that the database lacks.

    Matching is by ``code_en``, soft-deleted rows included: a retired category
    was retired on purpose, and its code still owns the unique index.
    """
    if not TAXONOMY_FILE.exists():  # pragma: no cover - packaging accident
        return 0

    payload = json.loads(TAXONOMY_FILE.read_text(encoding="utf-8"))
    known: dict[str, uuid.UUID] = {
        row.code_en: row.id
        for row in db.execute(
            select(Category.code_en, Category.id).where(Category.domain == "GROCERY")
        ).all()
    }

    created = 0

    def ensure(code: str, name: str, level: int, parent_id: uuid.UUID | None) -> uuid.UUID:
        nonlocal created
        existing = known.get(code)
        if existing is not None:
            return existing
        row = Category(
            code_en=code,
            display_name_pt=name,
            domain="GROCERY",
            level=level,
            parent_id=parent_id,
            brand_axis=level == 2 and name in BRAND_AXIS_L2,
        )
        db.add(row)
        db.flush()
        known[code] = row.id
        created += 1
        return row.id

    for l1_name, l2_map in payload["categories"].items():
        l1_code = slugify(l1_name)
        l1_id = ensure(l1_code, l1_name, 1, None)
        for l2_name, l3_names in l2_map.items():
            l2_code = f"{l1_code}__{slugify(l2_name)}"
            l2_id = ensure(l2_code, l2_name, 2, l1_id)
            for l3_name in l3_names:
                ensure(f"{l2_code}__{slugify(l3_name)}", l3_name, 3, l2_id)

    db.flush()
    return created


# --- Merchants ----------------------------------------------------------------
PORTUGUESE_MERCHANTS = [
    ("Continente", "RETAIL", "https://www.continente.pt"),
    ("Pingo Doce", "RETAIL", "https://www.pingodoce.pt"),
    ("Auchan", "RETAIL", "https://www.auchan.pt"),
    ("Lidl", "RETAIL", "https://www.lidl.pt"),
    ("Aldi", "RETAIL", "https://www.aldi.pt"),
    ("El Corte Inglés", "RETAIL", None),
    ("Piquete da Fruta", "RETAIL", None),
    ("Galp", "SERVICE_PROVIDER", "https://www.galp.pt"),
    ("BP", "SERVICE_PROVIDER", None),
    ("EDP Comercial", "UTILITY_PROVIDER", "https://www.edp.pt"),
    ("Águas de Gaia", "UTILITY_PROVIDER", None),
    ("Millennium bcp", "BANK", None),
    ("Caixa Geral de Depósitos", "BANK", None),
    ("Médis", "INSURER", None),
    ("Farmácia Central", "RETAIL", None),
]

#: NIFs and spellings read off the eleven real *talões* under
#: ``00.prompts/seed/supermarket/invoices/``. The NIF is what resolves a merchant
#: exactly during parsing; the aliases are what the fuzzy fallback matches on.
MERCHANT_FISCAL_DETAILS: dict[str, tuple[str | None, list[str]]] = {
    "Continente": (
        "501591109",
        ["Continente Loures", "MCH Cascais", "CONTINENTE HIPERMERCADOS S.A.", "Modelo Continente"],
    ),
    "Pingo Doce": ("500829993", ["PD Ramada", "Pingo Doce - Distribuição Alimentar"]),
    "Lidl": ("503340855", ["LIDL & Cia", "Lidl Alcobaça", "Lidl Loures-Frielas"]),
    "Piquete da Fruta": (None, ["Frutastico", "Piquete da Fruta", "Frutastico Unipessoal"]),
}


def ensure_merchants(db: DbSession) -> int:
    created = 0
    for name, kind, website in PORTUGUESE_MERCHANTS:
        merchant = db.scalar(select(Merchant).where(Merchant.name == name))
        if merchant is None:
            merchant = Merchant(name=name, kind=kind, website=website, aliases=[])
            db.add(merchant)
            created += 1
        nif, aliases = MERCHANT_FISCAL_DETAILS.get(name, (None, []))
        if nif and not merchant.nif:
            merchant.nif = nif
        if aliases and not merchant.aliases:
            merchant.aliases = aliases
    db.flush()
    return created


# --- Parser profiles ----------------------------------------------------------
#: One profile per merchant plus **one generic fallback**, so a brand-new
#: merchant is never a dead end (FR-1.15).
PARSER_PROFILES: list[dict[str, Any]] = [
    {
        "merchant": "Continente",
        "name": "Continente PDF",
        "parser_key": "continente_v1",
        "document_kinds": ["PDF_DIGITAL", "IMAGE_SCAN"],
        "detection_patterns": [r"CONTINENTE\s+HIPERMERCADOS", r"Cartao cliente", r"MCH\s+\w+"],
        # Continente's printed line value is already net of POUPANCA; Pingo
        # Doce's is gross. One flag, two opposite worlds (Decision #28).
        "field_hints": {
            "line_value_is_net": True,
            "section_heading": r"^[A-Za-zÀ-ÿ0-9&./ -]+:$",
            "savings_line": "POUPANCA",
            "decimal_separator": ",",
            "date_format": "%d/%m/%Y",
        },
        "priority": 100,
    },
    {
        "merchant": "Pingo Doce",
        "name": "Pingo Doce PDF",
        "parser_key": "pingodoce_v1",
        "document_kinds": ["PDF_DIGITAL", "IMAGE_SCAN"],
        "detection_patterns": [r"Pingo\s+Doce", r"500829993"],
        "field_hints": {
            "line_value_is_net": False,
            "savings_line": "Poupança Imediata",
            "decimal_separator": ",",
            "date_format": "%d/%m/%Y",
        },
        "priority": 100,
    },
    {
        "merchant": "Lidl",
        "name": "Lidl PDF",
        "parser_key": "lidl_v1",
        "document_kinds": ["PDF_DIGITAL", "IMAGE_SCAN"],
        "detection_patterns": [r"LIDL", r"503340855"],
        "field_hints": {
            "line_value_is_net": True,
            "iva_class_position": "end",
            "decimal_separator": ",",
            "date_format": "%Y-%m-%d",
        },
        "priority": 100,
    },
    {
        "merchant": "Piquete da Fruta",
        "name": "Piquete da Fruta (fotografia)",
        "parser_key": "piquete_v1",
        "document_kinds": ["IMAGE_SCAN", "PDF_DIGITAL"],
        "detection_patterns": [r"piquetedafruta", r"Frutastico", r"QTD\s+UNI\s+DESCRICAO"],
        "field_hints": {
            "line_value_is_net": True,
            "quantity_first": True,
            "iva_is_percentage": True,
            "decimal_separator": ",",
        },
        "priority": 90,
    },
    {
        "merchant": None,
        "name": "Perfil genérico",
        "parser_key": "generic_v1",
        "document_kinds": ["PDF_DIGITAL", "IMAGE_SCAN"],
        "detection_patterns": [],
        "field_hints": {"line_value_is_net": True, "decimal_separator": ","},
        "priority": 0,
    },
]


def ensure_parser_profiles(db: DbSession) -> int:
    """Install the profiles this release ships that the database lacks.

    A profile the household deleted stays deleted, and one it edited stays
    edited: existence is decided on ``parser_key`` alone.
    """
    known = set(db.scalars(select(MerchantParserProfile.parser_key)).all())
    created = 0
    for spec in PARSER_PROFILES:
        if spec["parser_key"] in known:
            continue
        merchant_id = None
        if spec["merchant"]:
            merchant = db.scalar(select(Merchant).where(Merchant.name == spec["merchant"]))
            if merchant is None:
                continue
            merchant_id = merchant.id
        db.add(
            MerchantParserProfile(
                merchant_id=merchant_id,
                name=spec["name"],
                parser_key=spec["parser_key"],
                document_kinds=spec["document_kinds"],
                detection_patterns=spec["detection_patterns"],
                field_hints=spec["field_hints"],
                priority=spec["priority"],
            )
        )
        created += 1
    db.flush()
    return created


#: Any 64-bit constant will do; it only has to be the same in every process.
_BOOTSTRAP_LOCK_KEY = 4_919_202_601


def ensure_all(db: DbSession) -> dict[str, int]:
    """Everything a fresh database needs before it can accept a *talão*.

    Serialised on an advisory lock because the API and the worker boot at the
    same time and would otherwise take the same rows in different orders, which
    Postgres resolves by killing one of them with a deadlock. The lock is held
    for the transaction and costs nothing once the data is already there.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK_KEY})
    merchants = ensure_merchants(db)
    return {
        "merchants": merchants,
        "categories": ensure_categories(db),
        "parser_profiles": ensure_parser_profiles(db),
    }
