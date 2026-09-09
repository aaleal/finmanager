"""supermarket receipt rename

Revision ID: d8e4b2a7f631
Revises: a1c4e8f92b56
Create Date: 2026-09-09 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d8e4b2a7f631"
down_revision: str | None = "a1c4e8f92b56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: (old_index_name, new_index_name)
INDEX_RENAMES = [
    ("uq_receipts_entity_atcud", "uq_supermarket_receipts_entity_atcud"),
    ("uq_receipts_entity_document", "uq_supermarket_receipts_entity_document"),
    ("ix_receipts_entity_purchase_date_id", "ix_supermarket_receipts_entity_purchase_date_id"),
    ("ix_receipts_merchant_id", "ix_supermarket_receipts_merchant_id"),
    ("ix_receipts_status", "ix_supermarket_receipts_status"),
    ("ix_receipt_items_entity_id", "ix_supermarket_receipt_items_entity_id"),
    ("ix_receipt_items_master_product_id", "ix_supermarket_receipt_items_master_product_id"),
    ("ix_receipt_items_receipt_id_line_no", "ix_supermarket_receipt_items_receipt_id_line_no"),
]

#: (table_name, old_constraint_name, new_constraint_name)
CONSTRAINT_RENAMES = [
    ("supermarket_receipts", "ck_receipts_void_needs_reason", "ck_supermarket_receipts_void_needs_reason"),
    ("supermarket_receipts", "ck_receipts_status", "ck_supermarket_receipts_status"),
    ("supermarket_receipts", "ck_receipts_confidence_range", "ck_supermarket_receipts_confidence_range"),
    (
        "supermarket_receipts",
        "fk_receipts_document_id_documents",
        "fk_supermarket_receipts_document_id_documents",
    ),
    (
        "supermarket_receipts",
        "fk_receipts_entity_id_entities",
        "fk_supermarket_receipts_entity_id_entities",
    ),
    (
        "supermarket_receipts",
        "fk_receipts_import_batch_id_import_batches",
        "fk_supermarket_receipts_import_batch_id_import_batches",
    ),
    (
        "supermarket_receipts",
        "fk_receipts_merchant_id_merchants",
        "fk_supermarket_receipts_merchant_id_merchants",
    ),
    (
        "supermarket_receipts",
        "fk_receipts_parser_profile_id_merchant_parser_profiles",
        "fk_supermarket_receipts_parser_profile_id_merchant_parser_profiles",
    ),
    (
        "supermarket_receipts",
        "fk_receipts_processing_job_id_processing_jobs",
        "fk_supermarket_receipts_processing_job_id_processing_jobs",
    ),
    ("supermarket_receipts", "pk_receipts", "pk_supermarket_receipts"),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_notional_value_source",
        "ck_supermarket_receipt_items_notional_value_source",
    ),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_product_flag",
        "ck_supermarket_receipt_items_product_flag",
    ),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_promo_type",
        "ck_supermarket_receipt_items_promo_type",
    ),
    ("supermarket_receipt_items", "ck_receipt_items_unit", "ck_supermarket_receipt_items_unit"),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_unit_canonical",
        "ck_supermarket_receipt_items_unit_canonical",
    ),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_fs_has_no_document_fields",
        "ck_supermarket_receipt_items_fs_has_no_document_fields",
    ),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_fs_pays_nothing",
        "ck_supermarket_receipt_items_fs_pays_nothing",
    ),
    (
        "supermarket_receipt_items",
        "ck_receipt_items_fs_needs_notional_value",
        "ck_supermarket_receipt_items_fs_needs_notional_value",
    ),
    (
        "supermarket_receipt_items",
        "fk_receipt_items_entity_id_entities",
        "fk_supermarket_receipt_items_entity_id_entities",
    ),
    (
        "supermarket_receipt_items",
        "fk_receipt_items_receipt_id_receipts",
        "fk_supermarket_receipt_items_receipt_id_supermarket_receipts",
    ),
    ("supermarket_receipt_items", "pk_receipt_items", "pk_supermarket_receipt_items"),
    (
        "product_price_history",
        "fk_product_price_history_source_receipt_item_id_receipt_items",
        "fk_product_price_history_source_receipt_item_id_supermarket_receipt_items",
    ),
]

#: (table, column, old_value, new_value) — data that spelled out the old module/
#: class/table name and would otherwise go stale the moment the code stops
#: writing or matching it.
DATA_RENAMES = [
    ("review_tasks", "module", "receipts", "supermarket"),
    ("review_tasks", "subject_type", "Receipt", "SupermarketReceipt"),
    ("links", "from_type", "Receipt", "SupermarketReceipt"),
    ("audit_logs", "table_name", "receipts", "supermarket_receipts"),
    ("audit_logs", "table_name", "receipt_items", "supermarket_receipt_items"),
    ("import_batches", "module", "receipts", "supermarket"),
    ("settings", "key", "receipts.arithmetic_tolerance_eur", "supermarket.arithmetic_tolerance_eur"),
]

#: job_type is a prefix (``receipts.parse``), not a bare value.
JOB_TYPE_RENAMES = [
    ("receipts.parse", "supermarket.parse"),
]


def upgrade() -> None:
    op.rename_table("receipts", "supermarket_receipts")
    op.rename_table("receipt_items", "supermarket_receipt_items")

    for old, new in INDEX_RENAMES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")

    for table, old, new in CONSTRAINT_RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")

    for table, column, old, new in DATA_RENAMES:
        op.execute(f"UPDATE {table} SET {column} = '{new}' WHERE {column} = '{old}'")

    for old, new in JOB_TYPE_RENAMES:
        op.execute(f"UPDATE processing_jobs SET job_type = '{new}' WHERE job_type = '{old}'")


def downgrade() -> None:
    for old, new in JOB_TYPE_RENAMES:
        op.execute(f"UPDATE processing_jobs SET job_type = '{old}' WHERE job_type = '{new}'")

    for table, column, old, new in DATA_RENAMES:
        op.execute(f"UPDATE {table} SET {column} = '{old}' WHERE {column} = '{new}'")

    for table, old, new in CONSTRAINT_RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")

    for old, new in INDEX_RENAMES:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")

    op.rename_table("supermarket_receipt_items", "receipt_items")
    op.rename_table("supermarket_receipts", "receipts")
