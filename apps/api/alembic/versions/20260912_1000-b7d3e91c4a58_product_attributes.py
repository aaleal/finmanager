"""product attributes: own brand, conservation, presentation

Revision ID: b7d3e91c4a58
Revises: f1a9c3e8b247
Create Date: 2026-09-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3e91c4a58"
down_revision: str | None = "f1a9c3e8b247"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSERVATION_KINDS = "'AMBIENTE', 'REFRIGERADO', 'CONGELADO'"


def upgrade() -> None:
    op.add_column(
        "master_products",
        sa.Column("is_own_brand", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("master_products", sa.Column("conservation", sa.String(16), nullable=True))
    op.add_column("master_products", sa.Column("presentation", sa.String(60), nullable=True))

    # Closed set: a fourth conservation state would be a new physical fact.
    op.create_check_constraint(
        op.f("ck_master_products_conservation"),
        "master_products",
        f"conservation IS NULL OR conservation IN ({CONSERVATION_KINDS})",
    )
    # `presentation` gets no CHECK on purpose — its vocabulary grows with the
    # shopping and is enforced in the service layer, so a new cut is a JSON edit
    # rather than a migration.

    # Dietary tags become a filter and a group-by dimension in this same change;
    # JSONB containment without GIN scans the whole catalogue.
    op.create_index(
        "ix_master_products_dietary_attributes",
        "master_products",
        ["dietary_attributes"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_master_products_dietary_attributes", table_name="master_products")
    op.drop_constraint(op.f("ck_master_products_conservation"), "master_products", type_="check")
    op.drop_column("master_products", "presentation")
    op.drop_column("master_products", "conservation")
    op.drop_column("master_products", "is_own_brand")
