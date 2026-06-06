"""Add continuity issue scroll anchors (current claim + text offset)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, None] = "h9i0j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("validation_issues")}

    if "current_claim_id" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("current_claim_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_validation_issues_current_claim_id",
            "validation_issues",
            "claims",
            ["current_claim_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_validation_issues_current_claim_id",
            "validation_issues",
            ["current_claim_id"],
        )

    if "text_offset" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("text_offset", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("validation_issues", "text_offset")
    op.drop_index("ix_validation_issues_current_claim_id", "validation_issues")
    op.drop_constraint(
        "fk_validation_issues_current_claim_id", "validation_issues", type_="foreignkey"
    )
    op.drop_column("validation_issues", "current_claim_id")
