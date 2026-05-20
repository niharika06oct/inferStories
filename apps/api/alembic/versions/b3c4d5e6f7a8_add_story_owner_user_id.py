"""add story owner_user_id

Revision ID: b3c4d5e6f7a8
Revises: 92a0ae479438
Create Date: 2026-05-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "92a0ae479438"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column("owner_user_id", sa.String(length=255), nullable=True),
    )
    op.execute(
        sa.text("UPDATE stories SET owner_user_id = 'legacy' WHERE owner_user_id IS NULL")
    )
    op.alter_column("stories", "owner_user_id", nullable=False)
    op.create_index("ix_stories_owner_user_id", "stories", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_stories_owner_user_id", table_name="stories")
    op.drop_column("stories", "owner_user_id")
