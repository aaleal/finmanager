"""lego instance display image

Revision ID: a1c4e9f27b60
Revises: e5b1c73f9a20
Create Date: 2026-09-02 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e9f27b60"
down_revision: str | None = "e5b1c73f9a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lego_set_instances",
        sa.Column("display_image_document_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_lego_set_instances_display_image_document_id_documents"),
        "lego_set_instances",
        "documents",
        ["display_image_document_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_lego_set_instances_display_image_document_id_documents"),
        "lego_set_instances",
        type_="foreignkey",
    )
    op.drop_column("lego_set_instances", "display_image_document_id")
