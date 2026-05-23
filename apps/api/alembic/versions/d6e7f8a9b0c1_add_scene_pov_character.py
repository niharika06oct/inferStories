"""Add optional POV character name per chapter."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scenes",
        sa.Column("pov_character", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scenes", "pov_character")
