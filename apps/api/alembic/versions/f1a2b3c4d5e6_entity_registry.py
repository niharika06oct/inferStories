"""Entity registry and claim entity foreign keys."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("aliases", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_id", "entities", ["id"], unique=False)
    op.create_index("ix_entities_story_id", "entities", ["story_id"], unique=False)

    op.add_column(
        "claims",
        sa.Column("subject_entity_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("object_entity_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_claims_subject_entity",
        "claims",
        "entities",
        ["subject_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_claims_object_entity",
        "claims",
        "entities",
        ["object_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_claims_subject_entity_id", "claims", ["subject_entity_id"], unique=False
    )
    op.create_index(
        "ix_claims_object_entity_id", "claims", ["object_entity_id"], unique=False
    )

    conn = op.get_bind()
    claim_rows = conn.execute(
        sa.text(
            'SELECT id, story_id, subject, predicate, "object", claim_type, claim_text '
            "FROM claims"
        )
    ).fetchall()

    if claim_rows:
        from sqlalchemy.orm import sessionmaker

        from app.claim_entities import resolve_manual
        from app.entity_registry import infer_predicate_from_claim

        # Use the migration connection so backfill sees uncommitted DDL.
        db = sessionmaker(bind=conn, autoflush=False, autocommit=False)()
        try:
            entity_cache: dict[tuple[int, str], int] = {}

            def entity_id(story_id: int, name: str) -> int | None:
                n = (name or "").strip()
                if not n:
                    return None
                key = (story_id, n.lower())
                if key in entity_cache:
                    return entity_cache[key]
                from app.entity_registry import get_or_create_entity, guess_entity_type

                ent = get_or_create_entity(
                    db, story_id, n, guess_entity_type(n, "relationship_state")
                )
                entity_cache[key] = ent.id
                return ent.id

            for row_id, story_id, subject, predicate, obj, claim_type, claim_text in (
                claim_rows
            ):
                ct = claim_type or "relationship_state"
                pred = predicate or ""
                if pred.lower() in {
                    "character_trait",
                    "character_goal",
                    "character_state",
                    "relationship_state",
                    "relationship_change",
                    "event",
                    "world_rule",
                    "power_rule",
                    "timeline_fact",
                    "plotline_fact",
                }:
                    pred = infer_predicate_from_claim(
                        ct, claim_text or f"{subject} {predicate} {obj}"
                    )

                resolved = resolve_manual(
                    db,
                    story_id,
                    subject=subject or "",
                    predicate=pred,
                    claim_object=obj or "",
                    claim_type=ct,
                    claim_text=claim_text,
                )
                conn.execute(
                    sa.text(
                        "UPDATE claims SET subject_entity_id = :sid, object_entity_id = :oid, "
                        "predicate = :pred, source_hash = :h WHERE id = :id"
                    ),
                    {
                        "sid": resolved.subject_entity_id,
                        "oid": resolved.object_entity_id,
                        "pred": resolved.predicate,
                        "h": resolved.source_hash,
                        "id": row_id,
                    },
                )
            db.flush()
        finally:
            db.close()


def downgrade() -> None:
    op.drop_index("ix_claims_object_entity_id", table_name="claims")
    op.drop_index("ix_claims_subject_entity_id", table_name="claims")
    op.drop_constraint("fk_claims_object_entity", "claims", type_="foreignkey")
    op.drop_constraint("fk_claims_subject_entity", "claims", type_="foreignkey")
    op.drop_column("claims", "object_entity_id")
    op.drop_column("claims", "subject_entity_id")
    op.drop_index("ix_entities_story_id", table_name="entities")
    op.drop_index("ix_entities_id", table_name="entities")
    op.drop_table("entities")
