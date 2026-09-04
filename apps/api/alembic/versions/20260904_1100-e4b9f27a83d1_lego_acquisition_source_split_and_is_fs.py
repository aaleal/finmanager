"""lego acquisition source split into stores, is_fs flag added

Revision ID: e4b9f27a83d1
Revises: c3f8a1d92e56
Create Date: 2026-09-04 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4b9f27a83d1"
down_revision: str | None = "c3f8a1d92e56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SOURCES = "'RETAIL', 'SECONDHAND', 'GIFT', 'FS', 'OTHER'"
NEW_SOURCES = "'CONTINENTE', 'AMAZON', 'OTHER_STORE', 'SECONDHAND', 'GIFT', 'OTHER'"


def upgrade() -> None:
    # The single "Loja" bucket becomes three (Continente/Amazon/Outra loja) and
    # "Fs" is dropped as an *origin* — it becomes its own `is_fs` flag below,
    # independent of where the set came from. Which specific store an existing
    # `RETAIL` row meant can't be recovered, so it lands on the generic
    # `OTHER_STORE` bucket rather than guessing; an existing `FS` row (none seen
    # in this codebase's own data) falls back to `OTHER` for the same reason.
    op.execute("UPDATE lego_set_instances SET acquisition_source = 'OTHER_STORE' WHERE acquisition_source = 'RETAIL'")
    op.execute("UPDATE lego_set_instances SET acquisition_source = 'OTHER' WHERE acquisition_source = 'FS'")
    op.drop_constraint(
        "ck_lego_set_instances_acquisition_source", "lego_set_instances", type_="check"
    )
    op.create_check_constraint(
        "ck_lego_set_instances_acquisition_source",
        "lego_set_instances",
        f"acquisition_source IS NULL OR acquisition_source IN ({NEW_SOURCES})",
    )
    op.add_column(
        "lego_set_instances",
        sa.Column("is_fs", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("lego_set_instances", "is_fs")
    # Which store a CONTINENTE/AMAZON/OTHER_STORE row meant can't be told apart
    # again — all three collapse back onto the old single `RETAIL` bucket.
    op.execute(
        "UPDATE lego_set_instances SET acquisition_source = 'RETAIL' "
        "WHERE acquisition_source IN ('CONTINENTE', 'AMAZON', 'OTHER_STORE')"
    )
    op.drop_constraint(
        "ck_lego_set_instances_acquisition_source", "lego_set_instances", type_="check"
    )
    op.create_check_constraint(
        "ck_lego_set_instances_acquisition_source",
        "lego_set_instances",
        f"acquisition_source IS NULL OR acquisition_source IN ({OLD_SOURCES})",
    )
