"""lego sealed moves from build state to condition

Revision ID: b2d4e8f61a37
Revises: f7c3a2e91d45
Create Date: 2026-09-03 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2d4e8f61a37"
down_revision: str | None = "f7c3a2e91d45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_BUILD_STATES = "'SEALED', 'BUILT', 'DISASSEMBLED'"
NEW_BUILD_STATES = "'BUILT', 'DISASSEMBLED'"
OLD_CONDITIONS = "'NEW', 'GOOD', 'WORN', 'DAMAGED'"
NEW_CONDITIONS = "'SEALED', 'NEW', 'GOOD', 'WORN', 'DAMAGED'"


def upgrade() -> None:
    # A sealed box was never "built" — it was a build state standing in for a
    # condition. Every row using it keeps meaning the same thing, just moved
    # onto the axis it actually describes.
    op.execute(
        "UPDATE lego_set_instances SET condition = 'SEALED', build_state = 'DISASSEMBLED' "
        "WHERE build_state = 'SEALED'"
    )
    op.drop_constraint("ck_lego_set_instances_build_state", "lego_set_instances", type_="check")
    op.create_check_constraint(
        "ck_lego_set_instances_build_state",
        "lego_set_instances",
        f"build_state IS NULL OR build_state IN ({NEW_BUILD_STATES})",
    )
    op.drop_constraint("ck_lego_set_instances_condition", "lego_set_instances", type_="check")
    op.create_check_constraint(
        "ck_lego_set_instances_condition",
        "lego_set_instances",
        f"condition IS NULL OR condition IN ({NEW_CONDITIONS})",
    )


def downgrade() -> None:
    # Which rows were originally SEALED-as-build-state cannot be recovered —
    # they downgrade onto a bare NULL condition until an operator re-triages them.
    op.execute("UPDATE lego_set_instances SET condition = NULL WHERE condition = 'SEALED'")
    op.drop_constraint("ck_lego_set_instances_condition", "lego_set_instances", type_="check")
    op.create_check_constraint(
        "ck_lego_set_instances_condition",
        "lego_set_instances",
        f"condition IS NULL OR condition IN ({OLD_CONDITIONS})",
    )
    op.drop_constraint("ck_lego_set_instances_build_state", "lego_set_instances", type_="check")
    op.create_check_constraint(
        "ck_lego_set_instances_build_state",
        "lego_set_instances",
        f"build_state IS NULL OR build_state IN ({OLD_BUILD_STATES})",
    )
