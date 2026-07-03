"""Story-scoped canonical entities (characters, places, …) with alias resolution."""

from __future__ import annotations

import json
import re
from typing import Literal

from sqlalchemy.orm import Session

from app.entity_classification import (
    ENTITY_TYPES,
    EntityType,
    classify_entity_surface,
    compute_graph_eligible,
)
from app.location_compatibility import classify_place_granularity
from app.models import Entity

# Re-export for callers
__all__ = [
    "ENTITY_TYPES",
    "EntityType",
    "classify_entity_surface",
    "find_entity_by_name",
    "get_or_create_entity",
    "ensure_pov_entity",
    "is_placeholder_entity_name",
    "infer_predicate_from_claim",
    "guess_entity_type",
]


def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


# First-person / placeholder surface forms that must never become canonical
# entities. "I/me/myself" should be resolved to the POV character upstream;
# "narrator" is a legacy fallback we no longer create.
_PLACEHOLDER_ENTITY_NAMES = frozenset(
    {"narrator", "i", "me", "myself", "my", "mine"}
)


def is_placeholder_entity_name(name: str) -> bool:
    return normalize_name(name) in _PLACEHOLDER_ENTITY_NAMES


def aliases_list(entity: Entity) -> list[str]:
    if not entity.aliases:
        return []
    try:
        parsed = json.loads(entity.aliases)
        if isinstance(parsed, list):
            return [str(a).strip() for a in parsed if str(a).strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def set_aliases(entity: Entity, aliases: list[str]) -> None:
    seen: set[str] = set()
    out: list[str] = []
    for a in aliases:
        key = normalize_name(a)
        if not key or key == normalize_name(entity.canonical_name):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(a.strip())
    entity.aliases = json.dumps(out) if out else None


# Tokens too generic to anchor a name match (avoid false merges).
_NAME_STOPWORD_TOKENS = frozenset(
    {"the", "of", "a", "an", "my", "her", "his", "their", "mr", "mrs", "ms", "dr"}
)


def _significant_tokens(key: str) -> list[str]:
    """Name tokens usable for matching: drop possessives, stopwords, short tokens."""
    out: list[str] = []
    for tok in key.split():
        if "'" in tok:  # possessive like "isabella's" — not a clean name token
            continue
        if tok in _NAME_STOPWORD_TOKENS or len(tok) < 3:
            continue
        out.append(tok)
    return out


def _is_nickname(short: str, full_token: str) -> bool:
    """Conservative nickname match: Bella↔Isabella (suffix), len-gated."""
    if short == full_token:
        return True
    if len(short) >= 4 and len(full_token) > len(short) and full_token.endswith(short):
        return True
    return False


def _surface_keys(row: Entity) -> list[str]:
    keys = [normalize_name(row.canonical_name)]
    keys.extend(normalize_name(a) for a in aliases_list(row))
    return [k for k in keys if k]


def find_entity_by_name(db: Session, story_id: int, name: str) -> Entity | None:
    """
    Resolve a surface form to an existing story entity.

    Order (most → least certain):
      1. Exact canonical or alias match.
      2. Single-token query: matches a canonical/alias token, or a nickname
         (Bella → Isabella Swan; Edward → Edward Cullen).
      3. Multi-token query: matches a shorter single-token entity that is the
         first or last name token of the query (Isabella → Isabella Swan), so
         duplicates collapse and the canonical name upgrades to the fuller form.
    """
    key = normalize_name(name)
    if not key:
        return None

    rows = db.query(Entity).filter(Entity.story_id == story_id).all()

    for row in rows:
        if key in _surface_keys(row):
            return row

    key_parts = _significant_tokens(key)

    # Single-token query → first-name / nickname match (not surname, to avoid
    # merging family members who share a last name, e.g. Isabella vs Charlie Swan).
    if len(key.split()) == 1 and key_parts:
        token = key_parts[0]
        for row in rows:
            for surface in _surface_keys(row):
                surface_tokens = _significant_tokens(surface)
                if not surface_tokens:
                    continue
                if _is_nickname(token, surface_tokens[0]):
                    return row
        return None

    # Multi-token query → upgrade an existing single-token entity whose name is
    # the GIVEN name (first token) of the query (Isabella → Isabella Swan).
    if len(key_parts) >= 2:
        for row in rows:
            canon_tokens = _significant_tokens(normalize_name(row.canonical_name))
            if len(canon_tokens) != 1:
                continue
            if canon_tokens[0] == key_parts[0]:
                return row

    return None


def get_or_create_entity(
    db: Session,
    story_id: int,
    name: str,
    entity_type: EntityType | None = None,
    *,
    extra_aliases: list[str] | None = None,
    sentence: str = "",
    evidence: str = "",
    role: str = "unknown",
) -> Entity:
    """Resolve a surface form to a story entity, creating one if needed."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Entity name is required")
    if is_placeholder_entity_name(cleaned):
        # Never persist a first-person placeholder ("I", "Narrator", …) as an entity.
        raise ValueError(
            f"Refusing to create placeholder entity {cleaned!r}; "
            "resolve first-person references to the POV character first."
        )

    if entity_type is None:
        entity_type, type_conf = classify_entity_surface(
            cleaned,
            sentence=sentence,
            evidence=evidence,
            role=role,
        )
    else:
        _, type_conf = classify_entity_surface(
            cleaned,
            sentence=sentence,
            evidence=evidence,
            role=role,
        )

    graph_eligible = compute_graph_eligible(entity_type, type_conf)
    place_granularity = None
    if entity_type == "place":
        place_granularity = classify_place_granularity(
            cleaned, evidence=evidence or sentence
        )

    existing = find_entity_by_name(db, story_id, cleaned)
    if existing is not None:
        if type_conf > (existing.type_confidence or 0):
            existing.type_confidence = type_conf
        if existing.entity_type == "character" and entity_type != "character":
            pass
        elif existing.entity_type != "character" and entity_type == "character":
            existing.entity_type = entity_type
            existing.graph_eligible = graph_eligible
        elif entity_type == "character":
            existing.graph_eligible = graph_eligible
        if len(cleaned) > len(existing.canonical_name):
            old_canon = existing.canonical_name
            existing.canonical_name = cleaned
            merged = aliases_list(existing) + [old_canon]
            if extra_aliases:
                merged.extend(extra_aliases)
            set_aliases(existing, merged)
        elif normalize_name(cleaned) != normalize_name(existing.canonical_name):
            merged = aliases_list(existing) + [cleaned]
            if extra_aliases:
                merged.extend(extra_aliases)
            set_aliases(existing, merged)
        elif extra_aliases:
            set_aliases(existing, aliases_list(existing) + extra_aliases)
        if entity_type == "place" and place_granularity:
            if not getattr(existing, "place_granularity", None):
                existing.place_granularity = place_granularity
            elif place_granularity in ("city", "residence", "institution") and existing.place_granularity == "unknown":
                existing.place_granularity = place_granularity
        return existing

    ent = Entity(
        story_id=story_id,
        canonical_name=cleaned,
        entity_type=entity_type,
        place_granularity=place_granularity if entity_type == "place" else None,
        type_confidence=type_conf,
        graph_eligible=graph_eligible,
        aliases=None,
    )
    if extra_aliases:
        set_aliases(ent, extra_aliases)
    db.add(ent)
    db.flush()
    return ent


def ensure_pov_entity(db: Session, story_id: int, pov_character: str | None) -> Entity | None:
    """Register POV character and common first-person aliases for extraction."""
    if not (pov_character or "").strip():
        return None
    pov = pov_character.strip()
    extras = [a for a in ("I", "me", "myself") if normalize_name(a) != normalize_name(pov)]
    ent = get_or_create_entity(
        db,
        story_id,
        pov,
        "character",
        extra_aliases=extras,
    )
    return ent


def infer_predicate_from_claim(claim_type: str, claim_sentence: str, explicit: str = "") -> str:
    """Semantic relation verb — not the claim_type category slug."""
    if explicit.strip():
        p = explicit.strip().lower()
        if p not in ENTITY_TYPES and p not in _CLAIM_TYPE_SLUGS:
            return p
    lower = claim_sentence.lower()
    for verb in (
        "distrusted",
        "distrusts",
        "distrust",
        "trusted",
        "trusts",
        "trust",
        "loved",
        "loves",
        "hated",
        "hates",
        "cannot be killed",
        "interacts with",
        "speaks with",
    ):
        if verb in lower:
            if verb == "cannot be killed":
                return "cannot_be_killed"
            return verb
    if "did not fully trust" in lower:
        return "distrusts"
    if "does not trust" in lower:
        return "distrusts"
    return _CLAIM_TYPE_DEFAULT_PREDICATE.get(claim_type, claim_type.replace("_", " "))


_CLAIM_TYPE_SLUGS = frozenset(
    {
        "character_trait",
        "character_goal",
        "character_state",
        "character_preference",
        "place_preference",
        "relationship_state",
        "relationship_change",
        "event",
        "world_rule",
        "power_rule",
        "timeline_fact",
        "plotline_fact",
    }
)

_CLAIM_TYPE_DEFAULT_PREDICATE: dict[str, str] = {
    "relationship_state": "relates_to",
    "relationship_change": "relates_to",
    "character_state": "is",
    "character_trait": "has_trait",
    "character_goal": "seeks",
    "character_preference": "prefers",
    "place_preference": "feels_about_place",
    "event": "interacts_with",
    "world_rule": "governed_by",
    "power_rule": "has_power",
    "timeline_fact": "occurred",
    "plotline_fact": "involves",
}


def guess_entity_type(name: str, claim_type: str) -> EntityType:
    """Backward-compatible wrapper — prefer classify_entity_surface with context."""
    etype, _ = classify_entity_surface(name, role="unknown")
    if claim_type in ("world_rule", "power_rule", "timeline_fact"):
        if etype == "character" and re.search(
            r"\b(city|kingdom|land|hall|castle)\b", name, re.I
        ):
            return "place"
        if etype == "character":
            return "object"
    if claim_type == "plotline_fact" and etype == "character":
        return "group"
    return etype
