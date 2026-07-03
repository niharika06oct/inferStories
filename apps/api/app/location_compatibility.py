"""Location fact compatibility for continuity validation (city vs residence hierarchy).

Residence within a municipality is compatible (Charlie's house + Forks).
Two different cities at the same granularity are not (Phoenix vs Forks).

Relevant reading: AIMA — part-of / located-in relations; Jurafsky — typed IE.
"""

from __future__ import annotations

import re
from typing import Literal

from sqlalchemy.orm import Session

from app.entity_classification import _KNOWN_PLACE_NAMES
from app.models import Entity

PlaceGranularity = Literal[
    "city", "region", "residence", "room", "institution", "unknown"
]

_LOCATION_PREDICATE_KEYS = frozenset(
    {
        "lives in",
        "lives at",
        "resides in",
        "resides at",
        "located in",
        "located at",
        "moving to",
        "is from",
        "born in",
    }
)

_INSTITUTION_MARKERS = re.compile(
    r"\b(?:school|high school|college|university|hospital|church|office|"
    r"station|library|gym|cafeteria|classroom)\b",
    re.I,
)

_RESIDENCE_MARKERS = re.compile(
    r"\b(?:house|home|apartment|flat|condo|mansion|cottage|hotel|motel|"
    r"residence|dwelling|cabin|trailer|room|bedroom|kitchen|porch|"
    r"chief'?s)\b",
    re.I,
)

_POSSESSIVE_RESIDENCE_RE = re.compile(
    r"\b\w+(?:'s|’s)\s+(?:house|home|place|apartment|cottage)\b",
    re.I,
)

_REGION_MARKERS = re.compile(
    r"\b(?:state|country|nation|peninsula|county|province|territory)\b",
    re.I,
)


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def is_location_predicate(predicate: str) -> bool:
    key = _norm(predicate).replace("_", " ")
    return key in _LOCATION_PREDICATE_KEYS or key.endswith(" in") or key.endswith(" at")


def classify_place_granularity(
    surface: str,
    *,
    evidence: str = "",
    entity: Entity | None = None,
) -> PlaceGranularity:
    """Classify a place object as city, region, residence, room, or unknown."""
    if entity is not None:
        stored = getattr(entity, "place_granularity", None)
        if stored in ("city", "region", "residence", "room", "institution"):
            return stored  # type: ignore[return-value]

    combined = f"{surface} {evidence}".strip()
    key = _norm(surface)

    if _INSTITUTION_MARKERS.search(combined):
        return "institution"

    if _POSSESSIVE_RESIDENCE_RE.search(combined) or _RESIDENCE_MARKERS.search(combined):
        if re.search(r"\b(?:room|bedroom|kitchen)\b", combined, re.I):
            return "room"
        return "residence"

    if key in _KNOWN_PLACE_NAMES:
        return "city"

    if _REGION_MARKERS.search(combined):
        return "region"

    # Short proper noun without residence markers → likely municipality in fiction.
    tokens = key.split()
    if len(tokens) <= 2 and key and not _RESIDENCE_MARKERS.search(key):
        if any(t in _KNOWN_PLACE_NAMES for t in tokens):
            return "city"
        if len(tokens) == 1 and len(key) >= 3:
            return "city"

    return "unknown"


def _granularity_rank(g: PlaceGranularity) -> int:
    return {
        "room": 1,
        "residence": 2,
        "institution": 2,
        "city": 3,
        "region": 4,
        "unknown": 0,
    }.get(g, 0)


def is_dwelling_place(surface: str, *, evidence: str = "") -> bool:
    """True for homes/hotels — not schools, offices, or other institutions."""
    combined = f"{surface} {evidence}".strip()
    if _INSTITUTION_MARKERS.search(combined):
        return False
    return bool(
        _POSSESSIVE_RESIDENCE_RE.search(combined) or _RESIDENCE_MARKERS.search(combined)
    )


def _evidence_mentions(text: str, place: str) -> bool:
    if not text or not place:
        return False
    return _norm(place) in _norm(text)


def locations_are_compatible(
    old_object: str,
    new_object: str,
    *,
    old_evidence: str = "",
    new_evidence: str = "",
    old_entity: Entity | None = None,
    new_entity: Entity | None = None,
) -> bool:
    """
    True when two location objects can coexist (house inside city, etc.).

    False when both are same-granularity incompatible places (two cities).
    """
    old_g = classify_place_granularity(
        old_object, evidence=old_evidence, entity=old_entity
    )
    new_g = classify_place_granularity(
        new_object, evidence=new_evidence, entity=new_entity
    )

    if old_g == "unknown" and new_g == "unknown":
        # Same string would not reach here; different unknowns stay strict.
        return False

    old_rank = _granularity_rank(old_g)
    new_rank = _granularity_rank(new_g)

    # Nested granularity: finer inside coarser (residence + city, room + residence).
    if old_rank > 0 and new_rank > 0 and old_rank != new_rank:
        return True

    # Co-mention in evidence (e.g. "Charlie's in Forks").
    combined_old = f"{old_evidence} {new_evidence}"
    combined_new = f"{new_evidence} {old_evidence}"
    if _evidence_mentions(combined_old, new_object) or _evidence_mentions(
        combined_new, old_object
    ):
        return True

    # Same granularity, different names → incompatible (Phoenix vs Forks).
    if old_g == new_g and old_g in ("city", "region") and _norm(old_object) != _norm(
        new_object
    ):
        return False

    if old_g == "city" and new_g in ("residence", "institution"):
        return True
    if new_g == "city" and old_g in ("residence", "institution"):
        return True
    if old_g == "room" and new_g in ("residence", "city", "institution"):
        return True
    if new_g == "room" and old_g in ("residence", "city", "institution"):
        return True
    # Home + school (or other institution) are compatible facts.
    if {old_g, new_g} == {"residence", "institution"}:
        return True
    if old_g == "institution" and new_g == "institution":
        return True

    return False


def load_entity(db: Session, entity_id: int | None) -> Entity | None:
    if entity_id is None:
        return None
    return db.get(Entity, entity_id)


def location_facts_compatible(
    db: Session,
    *,
    old_object: str,
    new_object: str,
    old_object_entity_id: int | None = None,
    new_object_entity_id: int | None = None,
    old_evidence: str = "",
    new_evidence: str = "",
) -> bool:
    """DB-aware wrapper for continuity validation."""
    return locations_are_compatible(
        old_object,
        new_object,
        old_evidence=old_evidence,
        new_evidence=new_evidence,
        old_entity=load_entity(db, old_object_entity_id),
        new_entity=load_entity(db, new_object_entity_id),
    )


def refine_location_predicate(
    predicate: str,
    object_surface: str,
    *,
    evidence: str = "",
    entity: Entity | None = None,
) -> str:
    """
    Phase 3: distinguish municipality (lives_in) from specific residence (lives_at).
    """
    key = _norm(predicate).replace(" ", "_")
    locationish = is_location_predicate(predicate) or key in {
        "in",
        "at",
        "lives",
        "resides",
        "located_in",
        "located_at",
        "lives_in",
        "lives_at",
    }
    if not locationish:
        return predicate

    gran = classify_place_granularity(object_surface, evidence=evidence, entity=entity)
    if gran == "institution":
        return predicate
    if gran in ("residence", "room"):
        return "lives_at"
    if gran in ("city", "region"):
        return "lives_in"
    if _RESIDENCE_MARKERS.search(f"{object_surface} {evidence}"):
        return "lives_at"
    return "lives_in"


def refine_extracted_location_claim(claim) -> object:
    """Normalize location predicates on an ExtractedClaim before persist."""
    from app.extraction.schema import ExtractedClaim

    if not isinstance(claim, ExtractedClaim):
        return claim
    target = (claim.target or "").strip()
    if not target:
        return claim
    refined = refine_location_predicate(
        claim.predicate,
        target,
        evidence=claim.evidence or claim.claim,
    )
    if refined == claim.predicate:
        return claim
    return claim.model_copy(update={"predicate": refined})
