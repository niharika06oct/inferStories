"""Add claim generation_origin and timestamps."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h9i0j1k2l3m4"
down_revision: Union[str, None] = "g8h9i0j1k2l3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("claims")}

    if "generation_origin" not in col_names:
        op.add_column(
            "claims",
            sa.Column(
                "generation_origin",
                sa.String(20),
                nullable=False,
                server_default="unknown",
            ),
        )
    if "created_at" not in col_names:
        op.add_column(
            "claims",
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
    if "updated_at" not in col_names:
        op.add_column(
            "claims",
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
    if "extracted_at" not in col_names:
        op.add_column(
            "claims",
            sa.Column("extracted_at", sa.DateTime(), nullable=True),
        )

    op.execute(
        sa.text(
            """
            UPDATE claims
            SET generation_origin = 'manual'
            WHERE source = 'manual' AND generation_origin = 'unknown'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE claims
            SET extracted_at = created_at
            WHERE source = 'extracted'
              AND extracted_at IS NULL
              AND generation_origin = 'unknown'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("claims", "extracted_at")
    op.drop_column("claims", "updated_at")
    op.drop_column("claims", "created_at")
    op.drop_column("claims", "generation_origin")
