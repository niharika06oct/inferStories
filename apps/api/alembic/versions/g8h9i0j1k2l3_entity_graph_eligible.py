"""Add entity type_confidence and graph_eligible."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("entities")}

    if "type_confidence" not in col_names:
        op.add_column(
            "entities",
            sa.Column(
                "type_confidence", sa.Float(), nullable=False, server_default="0"
            ),
        )
    if "graph_eligible" not in col_names:
        op.add_column(
            "entities",
            sa.Column(
                "graph_eligible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    op.execute(
        sa.text(
            """
            UPDATE entities
            SET graph_eligible = true,
                type_confidence = 0.85
            WHERE entity_type = 'character'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("entities", "graph_eligible")
    op.drop_column("entities", "type_confidence")
