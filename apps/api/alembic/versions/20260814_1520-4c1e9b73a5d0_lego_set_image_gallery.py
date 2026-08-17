"""lego set image gallery

Revision ID: 4c1e9b73a5d0
Revises: 8f2a1c4d7b91
Create Date: 2026-08-14 15:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c1e9b73a5d0"
down_revision: str | None = "8f2a1c4d7b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lego_set_images",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("lego_set_model_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("caption", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_lego_set_images_document_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["lego_set_model_id"],
            ["lego_set_models.id"],
            name=op.f("fk_lego_set_images_lego_set_model_id_lego_set_models"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lego_set_images")),
        sa.UniqueConstraint(
            "lego_set_model_id", "document_id", name="uq_lego_set_images_model_document"
        ),
    )
    op.create_index(
        "ix_lego_set_images_model_position",
        "lego_set_images",
        ["lego_set_model_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lego_set_images_model_position", table_name="lego_set_images")
    op.drop_table("lego_set_images")
