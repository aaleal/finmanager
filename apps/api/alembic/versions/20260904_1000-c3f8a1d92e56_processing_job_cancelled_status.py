"""processing job cancelled status

Revision ID: c3f8a1d92e56
Revises: b2d4e8f61a37
Create Date: 2026-09-04 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3f8a1d92e56"
down_revision: str | None = "b2d4e8f61a37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_STATUSES = "'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'RETRYING'"
NEW_STATUSES = "'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'RETRYING', 'CANCELLED'"

# `op.f()` marks this as an already fully-rendered name — the "ck" naming
# convention (see app/models/base.py) includes %(constraint_name)s, so passing
# the plain string without op.f() gets the convention applied a second time
# on top of it (`ck_processing_jobs_ck_processing_jobs_status`).
CONSTRAINT = op.f("ck_processing_jobs_status")


def upgrade() -> None:
    # The LEGO Brickset asset jobs (ADR-0049) are the first background jobs a
    # user can call off mid-flight — every prior job type only ever ran to
    # completion or failure on its own.
    op.drop_constraint(CONSTRAINT, "processing_jobs", type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "processing_jobs",
        f"status IN ({NEW_STATUSES})",
    )


def downgrade() -> None:
    op.execute("DELETE FROM processing_jobs WHERE status = 'CANCELLED'")
    op.drop_constraint(CONSTRAINT, "processing_jobs", type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "processing_jobs",
        f"status IN ({OLD_STATUSES})",
    )
