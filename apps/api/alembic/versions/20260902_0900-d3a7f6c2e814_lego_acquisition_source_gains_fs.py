"""lego acquisition source gains fs

Revision ID: d3a7f6c2e814
Revises: c959ddb96cc3
Create Date: 2026-09-02 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d3a7f6c2e814"
down_revision: str | None = "c959ddb96cc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SOURCES = "'RETAIL', 'SECONDHAND', 'GIFT', 'OTHER'"
NEW_SOURCES = "'RETAIL', 'SECONDHAND', 'GIFT', 'FS', 'OTHER'"


def upgrade() -> None:
    op.drop_constraint(
        "ck_lego_set_instances_acquisition_source", "lego_set_instances", type_="check"
    )
    op.create_check_constraint(
        "ck_lego_set_instances_acquisition_source",
        "lego_set_instances",
        f"acquisition_source IS NULL OR acquisition_source IN ({NEW_SOURCES})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_lego_set_instances_acquisition_source", "lego_set_instances", type_="check"
    )
    op.create_check_constraint(
        "ck_lego_set_instances_acquisition_source",
        "lego_set_instances",
        f"acquisition_source IS NULL OR acquisition_source IN ({OLD_SOURCES})",
    )
