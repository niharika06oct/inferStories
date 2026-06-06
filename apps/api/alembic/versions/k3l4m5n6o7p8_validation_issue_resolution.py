"""Add resolution_status to validation_issues (open / fixed / rejected)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "j2k3l4m5n6o7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    col_names = {c["name"] for c in insp.get_columns("validation_issues")}

    if "resolution_status" not in col_names:
        op.add_column(
            "validation_issues",
            sa.Column(
                "resolution_status",
                sa.String(length=20),
                nullable=False,
                server_default="open",
            ),
        )


def downgrade() -> None:
    op.drop_column("validation_issues", "resolution_status")
