"""FASTUS Stage 7: temporal validity + confidence history on claims."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n6o7p8q9r0s1"
down_revision: Union[str, None] = "m5n6o7p8q9r0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("claims")}

    if "valid_from_scene" not in col_names:
        op.add_column(
            "claims",
            sa.Column(
                "valid_from_scene",
                sa.Integer(),
                sa.ForeignKey("scenes.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if "valid_until_scene" not in col_names:
        op.add_column(
            "claims",
            sa.Column(
                "valid_until_scene",
                sa.Integer(),
                sa.ForeignKey("scenes.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if "confidence_history" not in col_names:
        op.add_column(
            "claims",
            sa.Column("confidence_history", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("claims", "confidence_history")
    op.drop_column("claims", "valid_until_scene")
    op.drop_column("claims", "valid_from_scene")
