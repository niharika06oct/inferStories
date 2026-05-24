"""Story-scoped canonical entities (characters, places, …) with alias resolution."""

from __future__ import annotations

import json
import re
from typing import Literal

from sqlalchemy.orm import Session

from app.models import Entity

EntityType = Literal["character", "place", "object", "group"]
ENTITY_TYPES: tuple[str, ...] = ("character", "place", "object", "group")

_PRONOUN_ALIASES = frozenset({"i", "me", "myself", "he", "him", "she", "her", "they", "them"})


def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


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


def find_entity_by_name(db: Session, story_id: int, name: str) -> Entity | None:
    """Match canonical name, alias, or first-token overlap (Jon → Jon Snow)."""
    key = normalize_name(name)
    if not key:
        return None

    rows = db.query(Entity).filter(Entity.story_id == story_id).all()
    for row in rows:
        if normalize_name(row.canonical_name) == key:
            return row
        for alias in aliases_list(row):
            if normalize_name(alias) == key:
                return row

    key_parts = key.split()
    if len(key_parts) == 1:
        for row in rows:
            canon = normalize_name(row.canonical_name)
            if canon == key or canon.startswith(key + " "):
                return row
            if canon.split() and canon.split()[0] == key:
                return row
            for alias in aliases_list(row):
                alias_key = normalize_name(alias)
                if alias_key == key or alias_key.startswith(key + " "):
                    return row
    return None


def get_or_create_entity(
    db: Session,
    story_id: int,
    name: str,
    entity_type: EntityType = "character",
    *,
    extra_aliases: list[str] | None = None,
) -> Entity:
    """Resolve a surface form to a story entity, creating one if needed."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Entity name is required")

    existing = find_entity_by_name(db, story_id, cleaned)
    if existing is not None:
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
        return existing

    ent = Entity(
        story_id=story_id,
        canonical_name=cleaned,
        entity_type=entity_type,
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
    "event": "interacts_with",
    "world_rule": "governed_by",
    "power_rule": "has_power",
    "timeline_fact": "occurred",
    "plotline_fact": "involves",
}


def guess_entity_type(name: str, claim_type: str) -> EntityType:
    if claim_type in ("world_rule", "power_rule", "timeline_fact"):
        return "place" if re.search(r"\b(city|kingdom|land|hall|castle)\b", name, re.I) else "object"
    if claim_type == "plotline_fact":
        return "group"
    return "character"
