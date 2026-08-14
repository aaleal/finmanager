"""lego set years become exact dates

Revision ID: 8f2a1c4d7b91
Revises: 6548ac11343f
Create Date: 2026-08-14 09:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f2a1c4d7b91"
down_revision: str | None = "6548ac11343f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lego_set_models", sa.Column("release_date", sa.Date(), nullable=True))
    op.add_column("lego_set_models", sa.Column("retirement_date", sa.Date(), nullable=True))

    # A release year is only known to the year, so it anchors to 1 January; a
    # retirement year anchors to 31 December, which is the whole point of the change:
    # a set retiring in December stayed on sale for that entire year.
    op.execute(
        """
        UPDATE lego_set_models
           SET release_date = make_date(release_year, 1, 1)
         WHERE release_year IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE lego_set_models
           SET retirement_date = make_date(retired_year, 12, 31)
         WHERE retired_year IS NOT NULL
        """
    )

    op.drop_column("lego_set_models", "release_year")
    op.drop_column("lego_set_models", "retired_year")


def downgrade() -> None:
    op.add_column("lego_set_models", sa.Column("release_year", sa.Integer(), nullable=True))
    op.add_column("lego_set_models", sa.Column("retired_year", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE lego_set_models
           SET release_year = EXTRACT(YEAR FROM release_date)::int,
               retired_year = EXTRACT(YEAR FROM retirement_date)::int
        """
    )
    op.drop_column("lego_set_models", "release_date")
    op.drop_column("lego_set_models", "retirement_date")
