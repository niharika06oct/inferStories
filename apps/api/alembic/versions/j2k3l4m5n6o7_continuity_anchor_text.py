"""Add anchor_text and anchor_length to validation_issues."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j2k3l4m5n6o7"
down_revision: Union[str, None] = "i0j1k2l3m4n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("validation_issues")}

    if "anchor_text" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column("anchor_text", sa.Text(), nullable=True),
        )
    if "anchor_length" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column(
                "anchor_length",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    op.drop_column("validation_issues", "anchor_length")
    op.drop_column("validation_issues", "anchor_text")
