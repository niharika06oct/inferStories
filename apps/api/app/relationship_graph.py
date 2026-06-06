"""Build story relationship graph from entity-linked canon claims."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.entity_classification import (
    classify_entity_surface,
    should_render_relationship_edge,
)
from app.entity_registry import (
    _CLAIM_TYPE_SLUGS,
    get_or_create_entity,
    infer_predicate_from_claim,
)
from app.models import Claim, Entity, Scene

CANON_STATUSES = ("approved", "canonized")
PREVIEW_STATUSES = ("suggested", "needs_review")

RELATIONSHIP_PREDICATES = frozenset(
    {
        "loves",
        "loved",
        "trusts",
        "trusted",
        "distrusts",
        "distrusted",
        "hates",
        "hated",
        "fears",
        "feared",
        "protects",
        "protected",
        "betrays",
        "betrayed",
        "desires",
        "desired",
        "mentors",
        "mentored",
        "is_friend_of",
        "is_enemy_of",
        "is_half_brother_of",
        "obsessed_with",
        "longs_for",
        "rivals",
        "speaks_with",
        "looks_at",
        "watches",
        "stares_at",
        "glances_at",
        "relates_to",
        "daughter_of",
        "son_of",
        "mother_of",
        "father_of",
        "partner_of",
        "knows",
        "bought_gift_for",
        "cares_for",
        "awkward_with",
        "detests",
        "detested",
    }
)

RELATIONSHIP_CLAIM_TYPES = frozenset(
    {"relationship_state", "relationship_change"}
)

RELATIONSHIP_GROUPS: dict[str, tuple[str, ...]] = {
    "romantic": ("loves", "loved", "desires", "desired", "obsessed_with", "longs_for"),
    "trust": ("trusts", "trusted", "distrusts", "distrusted"),
    "rivalry": ("hates", "hated", "rivals", "is_enemy_of", "betrays", "betrayed"),
    "family": (
        "is_half_brother_of",
        "daughter_of",
        "son_of",
        "mother_of",
        "father_of",
    ),
    "mentorship": ("mentors", "mentored", "protects", "protected"),
    "social": (
        "is_friend_of",
        "speaks_with",
        "looks_at",
        "watches",
        "stares_at",
        "glances_at",
        "relates_to",
        "knows",
        "partner_of",
        "bought_gift_for",
        "cares_for",
        "awkward_with",
    ),
}

GROUP_DISPLAY_ORDER = (
    "romantic",
    "trust",
    "rivalry",
    "family",
    "mentorship",
    "social",
)

CANON_WEIGHT = {"core": 1.2, "active": 1.0, "soft": 0.75}


def _normalize_predicate(raw: str, claim_type: str | None, claim_text: str | None) -> str:
    p = (raw or "").strip().lower().replace(" ", "_")
    if p in _CLAIM_TYPE_SLUGS:
        p = infer_predicate_from_claim(
            claim_type or "",
            claim_text or "",
            "",
        ).lower().replace(" ", "_")
    return p


def _predicate_group(predicate: str) -> str:
    for group, preds in RELATIONSHIP_GROUPS.items():
        if predicate in preds:
            return group
    return "social"


def _resolve_entity_ids(
    db: Session,
    story_id: int,
    claim: Claim,
    entity_by_id: dict[int, Entity],
) -> tuple[int | None, int | None]:
    """Resolve subject/object entity IDs (including legacy approved rows)."""
    src = claim.subject_entity_id
    tgt = claim.object_entity_id

    ctx = (claim.claim_text or "").strip()

    if src is None and (claim.subject or "").strip():
        subj_type, _ = classify_entity_surface(
            claim.subject.strip(),
            sentence=ctx,
            role="subject",
        )
        ent = get_or_create_entity(
            db,
            story_id,
            claim.subject.strip(),
            subj_type,
            sentence=ctx,
            role="subject",
        )
        src = ent.id
        entity_by_id[src] = ent

    obj_name = (claim.claim_object or "").strip()
    if tgt is None and obj_name:
        obj_type, _ = classify_entity_surface(
            obj_name,
            sentence=ctx,
            role="object",
        )
        ent = get_or_create_entity(
            db,
            story_id,
            obj_name,
            obj_type,
            sentence=ctx,
            role="object",
        )
        tgt = ent.id
        entity_by_id[tgt] = ent

    return src, tgt


def _should_graph_edge(
    claim: Claim,
    *,
    src: int | None,
    tgt: int | None,
    entity_by_id: dict[int, Entity],
) -> bool:
    if src is None or tgt is None or src == tgt:
        return False
    src_ent = entity_by_id.get(src)
    tgt_ent = entity_by_id.get(tgt)
    if not src_ent or not tgt_ent:
        return False
    return should_render_relationship_edge(
        claim.claim_type or "",
        src_ent.entity_type,
        tgt_ent.entity_type,
        subject_graph_eligible=bool(src_ent.graph_eligible),
        object_graph_eligible=bool(tgt_ent.graph_eligible),
    )


@dataclass
class _EdgeBucket:
    source_entity_id: int
    target_entity_id: int
    predicates: set[str] = field(default_factory=set)
    claim_ids: list[int] = field(default_factory=list)
    claim_predicates: list[str] = field(default_factory=list)
    claim_texts: list[str] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    canon_weights: list[float] = field(default_factory=list)
    scene_numbers: list[int] = field(default_factory=list)
    preview: bool = False


def build_relationship_graph(
    db: Session,
    story_id: int,
    *,
    include_preview: bool = False,
) -> dict:
    statuses = list(CANON_STATUSES)
    if include_preview:
        statuses = list(CANON_STATUSES) + list(PREVIEW_STATUSES)

    entities = (
        db.query(Entity)
        .filter(Entity.story_id == story_id, Entity.entity_type == "character")
        .all()
    )
    entity_by_id = {e.id: e for e in entities}

    rows = (
        db.query(Claim, Scene.scene_number)
        .join(Scene, Scene.id == Claim.scene_id)
        .filter(
            Claim.story_id == story_id,
            Claim.status.in_(statuses),
        )
        .all()
    )

    canon_rows = [r for r in rows if r[0].status in CANON_STATUSES]
    preview_rows = [r for r in rows if r[0].status in PREVIEW_STATUSES]

    mention_counts: dict[int, int] = defaultdict(int)
    degree: dict[int, int] = defaultdict(int)

    for claim, _scene_num in canon_rows:
        src, tgt = _resolve_entity_ids(db, story_id, claim, entity_by_id)
        if src:
            mention_counts[src] += 1
        if tgt:
            mention_counts[tgt] += 1

    buckets: dict[tuple[int, int], _EdgeBucket] = {}

    max_scene = 0
    pending_canon = 0

    def _ingest(claim: Claim, scene_number: int, *, preview: bool) -> None:
        nonlocal max_scene, pending_canon
        if claim.status in PREVIEW_STATUSES:
            pending_canon += 1
        src, tgt = _resolve_entity_ids(db, story_id, claim, entity_by_id)
        if not _should_graph_edge(claim, src=src, tgt=tgt, entity_by_id=entity_by_id):
            return
        assert src is not None and tgt is not None
        if src not in entity_by_id or tgt not in entity_by_id:
            return

        max_scene = max(max_scene, scene_number)
        key = (src, tgt)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = _EdgeBucket(
                source_entity_id=src,
                target_entity_id=tgt,
                preview=preview,
            )
            buckets[key] = bucket
        elif preview and not bucket.preview:
            pass
        elif not preview:
            bucket.preview = False

        pred = _normalize_predicate(
            claim.predicate, claim.claim_type, claim.claim_text
        )
        bucket.predicates.add(pred)
        bucket.claim_ids.append(claim.id)
        bucket.claim_predicates.append(pred)
        bucket.claim_texts.append((claim.claim_text or "").strip())
        bucket.confidences.append(float(claim.confidence or 0))
        bucket.canon_weights.append(
            CANON_WEIGHT.get((claim.canon_level or "active").lower(), 1.0)
        )
        bucket.scene_numbers.append(scene_number)
        if not preview:
            degree[src] += 1
            degree[tgt] += 1

    for claim, scene_number in canon_rows:
        _ingest(claim, scene_number, preview=False)

    if include_preview:
        for claim, scene_number in preview_rows:
            key_src, key_tgt = _resolve_entity_ids(db, story_id, claim, entity_by_id)
            if not _should_graph_edge(
                claim, src=key_src, tgt=key_tgt, entity_by_id=entity_by_id
            ):
                continue
            assert key_src is not None and key_tgt is not None
            if buckets.get((key_src, key_tgt)) is not None:
                continue
            _ingest(claim, scene_number, preview=True)

    edges_out: list[dict] = []
    for (src, tgt), bucket in buckets.items():
        preds = sorted(bucket.predicates)
        groups_present = {_predicate_group(p) for p in preds}
        primary = next(
            (g for g in GROUP_DISPLAY_ORDER if g in groups_present),
            "social",
        )
        claim_count = len(bucket.claim_ids)
        avg_conf = sum(bucket.confidences) / claim_count if claim_count else 0
        avg_canon = sum(bucket.canon_weights) / claim_count if claim_count else 1
        recency = 0.0
        if max_scene > 0 and bucket.scene_numbers:
            recency = sum(bucket.scene_numbers) / (max_scene * claim_count)

        strength = round(
            claim_count * 0.4 * avg_canon
            + avg_conf * 10
            + recency * 0.3,
            2,
        )

        supporting = [
            {
                "claim_id": cid,
                "predicate": pred,
                "claim_text": text or None,
                "confidence": conf,
                "scene_number": scene_num,
            }
            for cid, pred, text, conf, scene_num in zip(
                bucket.claim_ids,
                bucket.claim_predicates,
                bucket.claim_texts,
                bucket.confidences,
                bucket.scene_numbers,
            )
        ]

        edges_out.append(
            {
                "id": f"edge_{src}_{tgt}",
                "source": f"entity_{src}",
                "target": f"entity_{tgt}",
                "source_entity_id": src,
                "target_entity_id": tgt,
                "predicate": preds[0] if len(preds) == 1 else primary,
                "primary_relationship": primary,
                "sub_relationships": preds,
                "strength": strength,
                "confidence": round(avg_conf, 3),
                "claim_count": claim_count,
                "status": "preview" if bucket.preview else "active",
                "supporting_claims": supporting,
            }
        )

    participant_ids = set()
    for e in edges_out:
        participant_ids.add(e["source_entity_id"])
        participant_ids.add(e["target_entity_id"])

    nodes_out: list[dict] = []
    for ent in entity_by_id.values():
        if ent.entity_type != "character":
            continue
        if ent.id not in participant_ids and mention_counts.get(ent.id, 0) == 0:
            continue
        mentions = mention_counts.get(ent.id, 0)
        deg = degree.get(ent.id, 0)
        importance = round(mentions + deg * 5, 1)
        nodes_out.append(
            {
                "id": f"entity_{ent.id}",
                "entity_id": ent.id,
                "label": ent.canonical_name,
                "type": ent.entity_type,
                "importance_score": min(100, importance),
                "mention_count": mentions,
                "relationship_degree": deg,
            }
        )

    nodes_out.sort(key=lambda n: (-n["importance_score"], n["label"].lower()))

    approved_relationship_count = sum(
        1
        for c, _ in canon_rows
        if _should_graph_edge(
            c,
            src=_resolve_entity_ids(db, story_id, c, entity_by_id)[0],
            tgt=_resolve_entity_ids(db, story_id, c, entity_by_id)[1],
            entity_by_id=entity_by_id,
        )
    )

    return {
        "story_id": story_id,
        "nodes": nodes_out,
        "edges": edges_out,
        "meta": {
            "canon_statuses": list(CANON_STATUSES),
            "relationship_predicate_count": len(RELATIONSHIP_PREDICATES),
            "approved_relationship_claim_count": approved_relationship_count,
            "pending_preview_claim_count": pending_canon,
            "include_preview": include_preview,
        },
    }
