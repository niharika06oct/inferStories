"""Claim versioning: source_hash, claim_version, superseded_by_claim_id."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("claim_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "claims",
        sa.Column("superseded_by_claim_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("source_hash", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_claims_superseded_by",
        "claims",
        "claims",
        ["superseded_by_claim_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_claims_source_hash", "claims", ["source_hash"], unique=False)
    op.create_index(
        "ix_claims_scene_source_hash",
        "claims",
        ["scene_id", "source_hash"],
        unique=False,
    )

    # Backfill source_hash for existing rows (Python for consistent normalization).
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            'SELECT id, subject, predicate, "object", claim_type FROM claims WHERE source_hash IS NULL'
        )
    ).fetchall()
    if rows:
        from app.claim_identity import source_hash_for_claim_row

        for row_id, subject, predicate, obj, claim_type in rows:
            h = source_hash_for_claim_row(
                subject or "",
                predicate or "",
                obj or "",
                claim_type,
            )
            conn.execute(
                sa.text("UPDATE claims SET source_hash = :h WHERE id = :id"),
                {"h": h, "id": row_id},
            )

    op.alter_column("claims", "claim_version", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_claims_scene_source_hash", table_name="claims")
    op.drop_index("ix_claims_source_hash", table_name="claims")
    op.drop_constraint("fk_claims_superseded_by", "claims", type_="foreignkey")
    op.drop_column("claims", "source_hash")
    op.drop_column("claims", "superseded_by_claim_id")
    op.drop_column("claims", "claim_version")
