"""lego set age range, box dimensions and instructions

Revision ID: e5b1c73f9a20
Revises: d3a7f6c2e814
Create Date: 2026-09-02 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b1c73f9a20"
down_revision: str | None = "d3a7f6c2e814"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lego_set_models", sa.Column("age_min", sa.Integer(), nullable=True))
    op.add_column("lego_set_models", sa.Column("age_max", sa.Integer(), nullable=True))
    op.add_column("lego_set_models", sa.Column("box_height_cm", sa.Numeric(6, 1), nullable=True))
    op.add_column("lego_set_models", sa.Column("box_width_cm", sa.Numeric(6, 1), nullable=True))
    op.add_column("lego_set_models", sa.Column("box_depth_cm", sa.Numeric(6, 1), nullable=True))
    op.add_column("lego_set_models", sa.Column("box_weight_kg", sa.Numeric(7, 3), nullable=True))
    op.create_check_constraint(
        "ck_lego_set_models_age_range",
        "lego_set_models",
        "age_min IS NULL OR age_max IS NULL OR age_max >= age_min",
    )

    op.create_table(
        "lego_set_instructions",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("lego_set_model_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=250), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_lego_set_instructions_document_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["lego_set_model_id"],
            ["lego_set_models.id"],
            name=op.f("fk_lego_set_instructions_lego_set_model_id_lego_set_models"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lego_set_instructions")),
        sa.UniqueConstraint(
            "lego_set_model_id", "document_id", name="uq_lego_set_instructions_model_document"
        ),
    )
    op.create_index(
        "ix_lego_set_instructions_model_position",
        "lego_set_instructions",
        ["lego_set_model_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lego_set_instructions_model_position", table_name="lego_set_instructions")
    op.drop_table("lego_set_instructions")
    op.drop_constraint("ck_lego_set_models_age_range", "lego_set_models", type_="check")
    for column in (
        "box_weight_kg",
        "box_depth_cm",
        "box_width_cm",
        "box_height_cm",
        "age_max",
        "age_min",
    ):
        op.drop_column("lego_set_models", column)
