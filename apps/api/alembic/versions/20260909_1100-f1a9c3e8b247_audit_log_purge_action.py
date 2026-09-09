"""audit log purge action

Revision ID: f1a9c3e8b247
Revises: d8e4b2a7f631
Create Date: 2026-09-09 11:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a9c3e8b247"
down_revision: str | None = "d8e4b2a7f631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ACTIONS = "'CREATE', 'UPDATE', 'DELETE', 'STATUS_CHANGE'"
NEW_ACTIONS = "'CREATE', 'UPDATE', 'DELETE', 'STATUS_CHANGE', 'PURGE'"

CONSTRAINT = op.f("ck_audit_logs_action")


def upgrade() -> None:
    # Collection and storage purges (ADR-0053, ADR-0054) write one summary row
    # per run instead of one per record — a distinct action keeps it out of the
    # per-record CREATE/UPDATE/DELETE/STATUS_CHANGE history.
    op.drop_constraint(CONSTRAINT, "audit_logs", type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "audit_logs",
        f"action IN ({NEW_ACTIONS})",
    )


def downgrade() -> None:
    op.execute("DELETE FROM audit_logs WHERE action = 'PURGE'")
    op.drop_constraint(CONSTRAINT, "audit_logs", type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "audit_logs",
        f"action IN ({OLD_ACTIONS})",
    )
