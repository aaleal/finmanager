"""lego potential gift flag added

Revision ID: a1c4e8f92b56
Revises: e4b9f27a83d1
Create Date: 2026-09-08 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e8f92b56"
down_revision: str | None = "e4b9f27a83d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Forward-looking ("earmarked to give away"), independent of
    # `acquisition_source == 'GIFT'` (how the copy itself was acquired).
    op.add_column(
        "lego_set_instances",
        sa.Column("is_potential_gift", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("lego_set_instances", "is_potential_gift")
