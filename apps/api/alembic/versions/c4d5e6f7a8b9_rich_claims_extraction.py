"""Rich claims: extraction metadata, confidence, lifecycle status."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("claim_type", sa.String(length=64), nullable=True))
    op.add_column("claims", sa.Column("claim_text", sa.Text(), nullable=True))
    op.add_column("claims", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("claims", sa.Column("canon_level", sa.String(length=20), nullable=True))
    op.add_column("claims", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("claims", sa.Column("evidence_text", sa.Text(), nullable=True))
    op.add_column("claims", sa.Column("chunk_index", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("source", sa.String(length=20), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE claims SET
              claim_type = COALESCE(claim_type, predicate),
              claim_text = COALESCE(claim_text, subject || ' ' || predicate || ' ' || "object"),
              confidence = COALESCE(confidence, 1.0),
              canon_level = COALESCE(canon_level, 'active'),
              status = COALESCE(status, 'approved'),
              source = COALESCE(source, 'manual')
            """
        )
    )

    op.alter_column("claims", "confidence", nullable=False, server_default="1.0")
    op.alter_column("claims", "canon_level", nullable=False, server_default="active")
    op.alter_column("claims", "status", nullable=False, server_default="approved")
    op.alter_column("claims", "source", nullable=False, server_default="manual")


def downgrade() -> None:
    op.drop_column("claims", "source")
    op.drop_column("claims", "chunk_index")
    op.drop_column("claims", "evidence_text")
    op.drop_column("claims", "status")
    op.drop_column("claims", "canon_level")
    op.drop_column("claims", "confidence")
    op.drop_column("claims", "claim_text")
    op.drop_column("claims", "claim_type")
