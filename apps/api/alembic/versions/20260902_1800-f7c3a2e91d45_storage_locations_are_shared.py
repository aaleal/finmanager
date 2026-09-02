"""storage locations are shared

Revision ID: f7c3a2e91d45
Revises: a1c4e9f27b60
Create Date: 2026-09-02 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7c3a2e91d45"
down_revision: str | None = "a1c4e9f27b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_lego_storage_locations_entity_area_container",
        "lego_storage_locations",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_lego_storage_locations_entity_id_entities"),
        "lego_storage_locations",
        type_="foreignkey",
    )
    op.drop_column("lego_storage_locations", "entity_id")
    op.create_unique_constraint(
        "uq_lego_storage_locations_area_container",
        "lego_storage_locations",
        ["area", "container"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_lego_storage_locations_area_container",
        "lego_storage_locations",
        type_="unique",
    )
    # The entity a location used to belong to cannot be recovered; every row
    # downgrades onto NULL until an operator reassigns it by hand.
    op.add_column(
        "lego_storage_locations",
        sa.Column("entity_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_lego_storage_locations_entity_id_entities"),
        "lego_storage_locations",
        "entities",
        ["entity_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_lego_storage_locations_entity_area_container",
        "lego_storage_locations",
        ["entity_id", "area", "container"],
    )
