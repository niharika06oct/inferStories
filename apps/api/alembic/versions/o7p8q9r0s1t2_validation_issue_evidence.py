"""FASTUS Stage 9: evidence + explanation + suggested fix on validation issues."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o7p8q9r0s1t2"
down_revision: Union[str, None] = "n6o7p8q9r0s1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("validation_issues")}

    if "conflict_kind" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("conflict_kind", sa.String(length=32), nullable=True),
        )
    if "conflicting_evidence_text" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("conflicting_evidence_text", sa.Text(), nullable=True),
        )
    if "current_evidence_text" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("current_evidence_text", sa.Text(), nullable=True),
        )
    if "evidence_comparison" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("evidence_comparison", sa.Text(), nullable=True),
        )
    if "explanation" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("explanation", sa.Text(), nullable=True),
        )
    if "suggested_fix" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("suggested_fix", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    for col in (
        "suggested_fix",
        "explanation",
        "evidence_comparison",
        "current_evidence_text",
        "conflicting_evidence_text",
        "conflict_kind",
    ):
        op.drop_column("validation_issues", col)
