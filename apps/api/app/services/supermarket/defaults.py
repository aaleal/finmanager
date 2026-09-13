"""On-demand defaults for the household's own supermarket data.

Mirrors the grocery taxonomy's "load on demand" contract (ADR-0057): nothing
here runs at boot. A household presses a button once a screen is empty, and
every loader here is safe to press again — it either recognises what it already
loaded, or genuinely has nothing new to add.

``make seed`` / ``./fm demo`` call the very same functions the UI's empty-state
buttons call, so a demo install and a household pressing "carregar" by hand are
never two different code paths (ADR-0060).
"""

from __future__ import annotations

import contextlib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from app.core.errors import ValidationError

#: The household's own product catalogue. Optional and never committed
#: (ADR-0060) — dropped in by hand, read only if present. Absent is not an
#: error: a fresh install or a public demo simply has nothing to load yet.
PRODUCTS_FILE = Path(__file__).resolve().parents[2] / "data" / "supermarket-products.pt-PT.xlsx"
#: The eleven real *talões* shipped with the release (ADR-0027).
INVOICES_DIR = Path(__file__).resolve().parents[2] / "seed" / "data" / "invoices"


def load_default_products(db: DbSession, *, actor_user_id: uuid.UUID | None) -> int:
    """Load ``PRODUCTS_FILE`` through the very same bulk import the UI uses.

    Not a private writer: a row the importer would reject here is a row the
    dialog would reject too, so the file can be trusted the moment this accepts
    it. A row already in the catalogue (same name + brand) is skipped, not
    duplicated, which is what makes this safe to press twice.

    Ensures the taxonomy first: a category path the importer cannot resolve is
    an *error* on that row (`"Categoria não encontrada."`), not a shrug, so
    pressing "carregar produtos" before ever pressing "carregar categorias"
    would otherwise fail almost every row instead of leaving it uncategorised.
    """
    if not PRODUCTS_FILE.exists():
        return 0
    from app.services import reference_data
    from app.services.supermarket import products_service

    reference_data.ensure_categories(db)
    rows = products_service.preview_product_import(db, PRODUCTS_FILE.read_bytes())
    usable = [row for row in rows if not row["errors"] and row["canonical_name"]]
    results = products_service.commit_product_import(db, usable, actor_user_id=actor_user_id)
    return sum(1 for result in results if result["ok"] and not result["skipped"])


def load_default_invoices(
    db: DbSession, *, entity_id: uuid.UUID, actor_user_id: uuid.UUID | None
) -> int:
    """Ingest the shipped *talões* the way an upload would (ADR-0027).

    Deduplicated by content hash per entity (``create_from_upload``): pressing
    this twice for the same entity ingests nothing twice, while two different
    entities each get their own copy of the same eleven invoices.
    """
    if not INVOICES_DIR.is_dir():
        return 0
    from app.services.supermarket import service as supermarket

    ingested = 0
    for path in sorted(INVOICES_DIR.iterdir()):
        if path.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
            continue
        receipt, _job, created = supermarket.create_from_upload(
            db,
            data=path.read_bytes(),
            filename=path.name,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            idempotency_key=f"defaults:invoices:{entity_id}:{path.name}",
        )
        if not created:
            continue
        # A parse failure is a FAILED job row the queue can retry, never a
        # loader that refuses to finish.
        with contextlib.suppress(ValidationError):
            supermarket.parse_receipt(db, receipt, actor_user_id=actor_user_id)
        ingested += 1
    db.flush()
    return ingested


__all__ = ["INVOICES_DIR", "PRODUCTS_FILE", "load_default_invoices", "load_default_products"]
