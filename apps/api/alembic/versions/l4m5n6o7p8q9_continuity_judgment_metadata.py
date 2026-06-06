"""Add continuity judgment metadata to validation_issues."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l4m5n6o7p8q9"
down_revision: Union[str, None] = "k3l4m5n6o7p8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("validation_issues")}

    if "judge_source" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column(
                "judge_source",
                sa.String(length=20),
                nullable=False,
                server_default="rules",
            ),
        )
    if "judge_classification" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column(
                "judge_classification",
                sa.String(length=32),
                nullable=False,
                server_default="hard_contradiction",
            ),
        )
    if "judge_confidence" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column(
                "judge_confidence",
                sa.Float(),
                nullable=False,
                server_default="1.0",
            ),
        )
    if "judge_reason" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("judge_reason", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("validation_issues", "judge_reason")
    op.drop_column("validation_issues", "judge_confidence")
    op.drop_column("validation_issues", "judge_classification")
    op.drop_column("validation_issues", "judge_source")
