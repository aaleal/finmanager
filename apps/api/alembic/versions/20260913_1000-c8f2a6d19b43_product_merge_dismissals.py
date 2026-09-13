"""product merge dismissals: a look-alike group a human declared distinct

Revision ID: c8f2a6d19b43
Revises: b7d3e91c4a58
Create Date: 2026-09-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8f2a6d19b43"
down_revision: str | None = "b7d3e91c4a58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_merge_dismissals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # No FK: the set is the key, and a member that later disappears leaves a
        # row that can simply never match again.
        sa.Column("product_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_merge_dismissals")),
        sa.UniqueConstraint("product_ids", name="uq_product_merge_dismissals_product_ids"),
    )


def downgrade() -> None:
    op.drop_table("product_merge_dismissals")
