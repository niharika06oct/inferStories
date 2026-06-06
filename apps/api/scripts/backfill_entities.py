"""Backfill entity resolution for existing stories (Phase 4).

Fixes legacy data created before stronger entity resolution:

  1. Re-point claims attached to the fabricated "Narrator" entity to the
     scene's POV character (when known); flag the rest as needs_review.
  2. Merge duplicate character entities (Isabella / Isabella Swan / Bella),
     moving claim references and aliases onto the canonical row.
  3. Recompute source_hash on touched claims and de-duplicate identical
     claims within a scene.
  4. Optionally re-run continuity validation per scene.

Approved / canonized / rejected claims are RE-POINTED, never destroyed
(except exact duplicates produced by the merge, which collapse into one).

Usage (from apps/api, with venv active):

    python -m scripts.backfill_entities            # dry-run, all stories
    python -m scripts.backfill_entities --apply     # write changes
    python -m scripts.backfill_entities --apply --revalidate
    python -m scripts.backfill_entities --story 10  # limit to one story
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy.orm import Session

from app.claim_identity import source_hash_for_claim_row
from app.database import SessionLocal
from app.entity_registry import (
    _is_nickname,
    _significant_tokens,
    aliases_list,
    ensure_pov_entity,
    is_placeholder_entity_name,
    normalize_name,
    set_aliases,
)
from app.models import Claim, Entity, Scene, Story, ValidationIssue
from app.validation import validate_scene_claims


class Stats:
    def __init__(self) -> None:
        self.narrator_repointed = 0
        self.narrator_flagged = 0
        self.narrator_entities_removed = 0
        self.entities_merged = 0
        self.claims_repointed = 0
        self.claims_deduped = 0
        self.hashes_recomputed = 0

    def render(self) -> str:
        return (
            f"  narrator claims re-pointed:   {self.narrator_repointed}\n"
            f"  narrator claims flagged:      {self.narrator_flagged}\n"
            f"  narrator entities removed:    {self.narrator_entities_removed}\n"
            f"  duplicate entities merged:    {self.entities_merged}\n"
            f"  claims re-pointed (merge):    {self.claims_repointed}\n"
            f"  duplicate claims collapsed:   {self.claims_deduped}\n"
            f"  source hashes recomputed:     {self.hashes_recomputed}"
        )


def _scene_for_claim(db: Session, claim: Claim, cache: dict[int, Scene]) -> Scene | None:
    if claim.scene_id in cache:
        return cache[claim.scene_id]
    scene = db.query(Scene).filter(Scene.id == claim.scene_id).first()
    if scene is not None:
        cache[claim.scene_id] = scene
    return scene


def _recompute_hash(claim: Claim, stats: Stats) -> None:
    claim.source_hash = source_hash_for_claim_row(
        claim.subject,
        claim.predicate,
        claim.claim_object,
        claim.claim_type,
        subject_entity_id=claim.subject_entity_id,
        object_entity_id=claim.object_entity_id,
    )
    stats.hashes_recomputed += 1


def repoint_narrator_claims(
    db: Session, story: Story, stats: Stats, scene_cache: dict[int, Scene]
) -> None:
    narrator_entities = [
        e
        for e in db.query(Entity).filter(Entity.story_id == story.id).all()
        if is_placeholder_entity_name(e.canonical_name)
    ]
    if not narrator_entities:
        return

    narrator_ids = {e.id for e in narrator_entities}
    claims = (
        db.query(Claim)
        .filter(Claim.story_id == story.id)
        .filter(
            (Claim.subject_entity_id.in_(narrator_ids))
            | (Claim.object_entity_id.in_(narrator_ids))
        )
        .all()
    )

    for claim in claims:
        scene = _scene_for_claim(db, claim, scene_cache)
        pov = (scene.pov_character or "").strip() if scene else ""
        if not pov:
            if claim.status in ("suggested",):
                claim.status = "needs_review"
            stats.narrator_flagged += 1
            continue

        pov_entity = ensure_pov_entity(db, story.id, pov)
        if pov_entity is None:
            stats.narrator_flagged += 1
            continue
        db.flush()

        if claim.subject_entity_id in narrator_ids:
            claim.subject_entity_id = pov_entity.id
            claim.subject = pov_entity.canonical_name
        if claim.object_entity_id in narrator_ids:
            claim.object_entity_id = pov_entity.id
            claim.claim_object = pov_entity.canonical_name
        _recompute_hash(claim, stats)
        stats.narrator_repointed += 1

    # Drop now-orphaned narrator entities.
    for ent in narrator_entities:
        still_used = (
            db.query(Claim)
            .filter(
                (Claim.subject_entity_id == ent.id)
                | (Claim.object_entity_id == ent.id)
            )
            .count()
        )
        if still_used == 0:
            db.delete(ent)
            stats.narrator_entities_removed += 1


def _should_merge(a: Entity, b: Entity) -> bool:
    """Conservative character-merge: nickname or given-name subset only."""
    if a.entity_type != "character" or b.entity_type != "character":
        return False
    ka, kb = normalize_name(a.canonical_name), normalize_name(b.canonical_name)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    ta, tb = _significant_tokens(ka), _significant_tokens(kb)
    if not ta or not tb:
        return False
    # Given-name subset: one single-token, other multi-token, same first token.
    if ta[0] == tb[0] and (len(ta) == 1 or len(tb) == 1):
        return True
    # Single-token nickname of the other's given name (Bella ↔ Isabella).
    if len(ta) == 1 and _is_nickname(ta[0], tb[0]):
        return True
    if len(tb) == 1 and _is_nickname(tb[0], ta[0]):
        return True
    return False


def _canonical_winner(a: Entity, b: Entity) -> tuple[Entity, Entity]:
    """Winner keeps the fuller proper name (more tokens, then longer)."""
    ta = len(_significant_tokens(normalize_name(a.canonical_name)))
    tb = len(_significant_tokens(normalize_name(b.canonical_name)))
    if (ta, len(a.canonical_name)) >= (tb, len(b.canonical_name)):
        return a, b
    return b, a


def merge_duplicate_entities(db: Session, story: Story, stats: Stats) -> None:
    entities = [
        e
        for e in db.query(Entity).filter(Entity.story_id == story.id).all()
        if e.entity_type == "character"
        and not is_placeholder_entity_name(e.canonical_name)
    ]
    # Greedy union: fold each entity into an existing winner when they merge.
    winners: list[Entity] = []
    for ent in sorted(
        entities,
        key=lambda e: (
            -len(_significant_tokens(normalize_name(e.canonical_name))),
            -len(e.canonical_name),
        ),
    ):
        target = next((w for w in winners if _should_merge(w, ent)), None)
        if target is None:
            winners.append(ent)
            continue
        winner, loser = _canonical_winner(target, ent)
        _fold_entity(db, winner, loser, stats)
        if winner is ent:
            # Swap: the just-added winner replaced an earlier row.
            winners = [w for w in winners if w.id != target.id]
            winners.append(winner)


def _fold_entity(db: Session, winner: Entity, loser: Entity, stats: Stats) -> None:
    if winner.id == loser.id:
        return
    claims = (
        db.query(Claim)
        .filter(
            (Claim.subject_entity_id == loser.id)
            | (Claim.object_entity_id == loser.id)
        )
        .all()
    )
    for claim in claims:
        if claim.subject_entity_id == loser.id:
            claim.subject_entity_id = winner.id
            claim.subject = winner.canonical_name
        if claim.object_entity_id == loser.id:
            claim.object_entity_id = winner.id
            claim.claim_object = winner.canonical_name
        _recompute_hash(claim, stats)
        stats.claims_repointed += 1

    merged_aliases = aliases_list(winner) + aliases_list(loser) + [loser.canonical_name]
    set_aliases(winner, merged_aliases)
    if loser.graph_eligible:
        winner.graph_eligible = winner.graph_eligible or loser.graph_eligible
    db.delete(loser)
    stats.entities_merged += 1


def dedupe_scene_claims(db: Session, story: Story, stats: Stats) -> None:
    """Collapse claims that became identical (same hash) within a scene."""
    rank = {"canonized": 4, "approved": 3, "needs_review": 2, "suggested": 1}
    claims = db.query(Claim).filter(Claim.story_id == story.id).all()
    by_key: dict[tuple[int, str], list[Claim]] = defaultdict(list)
    for claim in claims:
        if not claim.source_hash:
            continue
        by_key[(claim.scene_id, claim.source_hash)].append(claim)

    for group in by_key.values():
        if len(group) < 2:
            continue
        # Keep the strongest status; on tie keep the lowest id (oldest).
        keeper = sorted(
            group,
            key=lambda c: (-rank.get(c.status, 0), c.id),
        )[0]
        for claim in group:
            if claim.id == keeper.id:
                continue
            # Never silently drop a rejected decision into a kept row.
            if claim.status == "rejected" and keeper.status != "rejected":
                continue
            db.delete(claim)
            stats.claims_deduped += 1


def revalidate_story(db: Session, story: Story) -> None:
    scenes = (
        db.query(Scene)
        .filter(Scene.story_id == story.id)
        .order_by(Scene.scene_number)
        .all()
    )
    for scene in scenes:
        db.query(ValidationIssue).filter(
            ValidationIssue.scene_id == scene.id
        ).delete(synchronize_session=False)
        rows = db.query(Claim).filter(Claim.scene_id == scene.id).all()
        validate_scene_claims(db, scene, rows)


def run(*, apply: bool, story_id: int | None, revalidate: bool) -> None:
    db = SessionLocal()
    stats = Stats()
    try:
        stories = db.query(Story)
        if story_id is not None:
            stories = stories.filter(Story.id == story_id)
        story_list = stories.all()
        scene_cache: dict[int, Scene] = {}

        for story in story_list:
            # Continuity issues are derived data and reference claims we may
            # re-point or collapse; clear them first (regenerated below or on
            # the next Save & analyze).
            scene_ids = [
                s.id
                for s in db.query(Scene).filter(Scene.story_id == story.id).all()
            ]
            if scene_ids:
                db.query(ValidationIssue).filter(
                    ValidationIssue.scene_id.in_(scene_ids)
                ).delete(synchronize_session=False)
                db.flush()

            repoint_narrator_claims(db, story, stats, scene_cache)
            merge_duplicate_entities(db, story, stats)
            db.flush()
            dedupe_scene_claims(db, story, stats)
            db.flush()
            if revalidate:
                revalidate_story(db, story)

        print(f"Stories processed: {len(story_list)}")
        print(stats.render())

        if apply:
            db.commit()
            print("\nChanges committed.")
        else:
            db.rollback()
            print("\nDry run — no changes written. Re-run with --apply to persist.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Persist changes (default: dry-run)."
    )
    parser.add_argument(
        "--story", type=int, default=None, help="Limit to a single story id."
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="Re-run continuity validation after backfill.",
    )
    args = parser.parse_args()
    run(apply=args.apply, story_id=args.story, revalidate=args.revalidate)


if __name__ == "__main__":
    main()
