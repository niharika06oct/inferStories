"""Classify noun phrases as character, place, object, concept, animal, or group."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

EntityType = Literal["character", "animal", "place", "object", "concept", "group"]
ENTITY_TYPES: tuple[str, ...] = (
    "character",
    "animal",
    "place",
    "object",
    "concept",
    "group",
)

# Common non-character nouns that regex/LLM often mis-tag as people.
_CONCEPT_OR_OBJECT_TERMS = frozenset(
    {
        "water",
        "rain",
        "darkness",
        "light",
        "love",
        "fear",
        "hope",
        "memory",
        "dream",
        "death",
        "life",
        "time",
        "sun",
        "moon",
        "wind",
        "fire",
        "ice",
        "snow",
        "stone",
        "gold",
        "silver",
        "power",
        "magic",
        "truth",
        "silence",
        "chaos",
        "peace",
        "war",
        "blood",
        "shadow",
        "lightning",
        "thunder",
        "the sea",
        "the ocean",
        "the sky",
        "the night",
        "the day",
        "the world",
        "the land",
        "the forest",
        "the river",
        "the mountain",
        "heat",
        "the heat",
        "clouds",
        "cloud",
        "silence",
        "awkwardness",
        "the rain",
    }
)

_OBJECT_TERMS = frozenset(
    {
        "parka",
        "carry-on",
        "carry on",
        "cruiser",
        "car",
        "truck",
        "chevy",
        "engine",
        "wardrobe",
        "winter wardrobe",
        "airport",
        "plane",
        "lights",
        "red and blue lights",
        "the thing",
        "gift",
        "homecoming gift",
        "mechanic",
        "traffic",
        "ferns",
        "moss",
        "trees",
    }
)

_PLACE_SUFFIXES = (
    " city",
    " kingdom",
    " hall",
    " castle",
    " tower",
    " beach",
    " shack",
    " village",
    " town",
    " land",
    " island",
    " forest",
    " mountains",
    " valley",
)

_ANIMAL_TERMS = frozenset(
    {
        "dog",
        "horse",
        "dragon",
        "wolf",
        "cat",
        "bird",
        "serpent",
        "snake",
        "bear",
        "lion",
        "tiger",
        "raven",
        "eagle",
        "hawk",
        "stag",
        "deer",
        "fox",
        "hound",
    }
)

# Common place names in fiction (proper nouns that are not people).
_KNOWN_PLACE_NAMES = frozenset(
    {
        "phoenix",
        "forks",
        "seattle",
        "port angeles",
        "la push",
        "california",
        "olympic peninsula",
        "washington",
        "washington state",
        "united states",
        "united states of america",
        "america",
        "goa",
        "winterfell",
        "king's landing",
    }
)

_GROUP_MARKERS = frozenset(
    {
        "army",
        "soldiers",
        "guards",
        "villagers",
        "crowd",
        "people",
        "wildlings",
        "knights",
        "men",
        "women",
        "children",
        "elders",
        "priests",
        "rebels",
    }
)

_HUMAN_ROLE_RE = re.compile(
    r"^(?:the\s+)?(?:man|woman|boy|girl|child|king|queen|lord|lady|"
    r"prince|princess|stranger|husband|wife|mother|father|brother|sister|"
    r"son|daughter|uncle|aunt|captain|general|knight|servant|maid|butler|"
    r"merchant|priest|witch|wizard|assassin|guard|soldier|stranger)\b",
    re.I,
)

_FAMILY_ADDRESS_RE = re.compile(
    r"^(?:my\s+)?(?:mom|mother|mum|dad|father|pa)\b",
    re.I,
)

_PROPER_NAME_RE = re.compile(
    r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$|^[A-Z][a-z]+(?:\s+(?:van|de|von|al)\s+[A-Z][a-z]+)?$"
)

_RELATIONAL_PREDICATES = frozenset(
    {
        "loves",
        "loved",
        "love",
        "hates",
        "hated",
        "hate",
        "detests",
        "detested",
        "detest",
        "fears",
        "feared",
        "fear",
        "trusts",
        "trusted",
        "trust",
        "distrusts",
        "distrusted",
        "misses",
        "missed",
        "miss",
        "cares_for",
        "cared_for",
        "worries_about",
        "worried_about",
        "desires",
        "desired",
        "wants",
        "wanted",
        "needs",
        "needed",
        "longs_for",
        "obsessed_with",
        "betrays",
        "betrayed",
        "daughter_of",
        "son_of",
        "mother_of",
        "father_of",
        "partner_of",
        "knows",
        "bought_gift_for",
        "awkward_with",
    }
)

_SENTIENT_NATURE_RE = re.compile(
    r"\b(?:spoke|whispered|said|remembered|watched|listened)\b",
    re.I,
)


@lru_cache(maxsize=1)
def _get_nlp():
    try:
        import spacy  # type: ignore[import-untyped]

        return spacy.load("en_core_web_sm")
    except Exception:
        return None


def _normalize(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


_NOT_A_NAME = frozenset(
    {
        "you",
        "i",
        "we",
        "they",
        "he",
        "she",
        "it",
        "this",
        "that",
        "there",
        "here",
        "when",
        "what",
        "how",
        "of",
        "tell",
        "don",
        "flying",
        "neither",
        "nothing",
        "police",
        "chief",
    }
)


def _looks_like_proper_name(name: str) -> bool:
    cleaned = name.strip()
    if not cleaned:
        return False
    if _PROPER_NAME_RE.match(cleaned):
        return True
    parts = cleaned.split()
    if len(parts) >= 2 and all(p[0].isupper() for p in parts if p):
        return True
    if len(parts) == 1:
        p = parts[0]
        if p[0].isupper() and p.lower() not in _NOT_A_NAME and not p.isupper():
            return True
    return False


def _heuristic_classify(
    name: str,
    *,
    sentence: str = "",
    evidence: str = "",
    role: str = "unknown",
) -> tuple[EntityType, float]:
    key = _normalize(name)
    if not key:
        return "concept", 0.3

    if key in _KNOWN_PLACE_NAMES:
        return "place", 0.9

    if key in _OBJECT_TERMS:
        return "object", 0.88

    if key in _CONCEPT_OR_OBJECT_TERMS or key in _ANIMAL_TERMS:
        if key in _ANIMAL_TERMS:
            return "animal", 0.88
        return "concept", 0.92

    for term in _CONCEPT_OR_OBJECT_TERMS:
        if key == term or key.endswith(term):
            return "concept", 0.85

    if _HUMAN_ROLE_RE.match(key) or _FAMILY_ADDRESS_RE.match(key):
        return "character", 0.78

    if len(key.split()) >= 2 and key.split()[0] in (
        "her",
        "his",
        "their",
        "the",
        "my",
    ):
        if not _FAMILY_ADDRESS_RE.match(key) and key not in _KNOWN_PLACE_NAMES:
            return "concept", 0.82

    if any(key.endswith(s) for s in _PLACE_SUFFIXES) or re.search(
        r"\b(city|kingdom|castle|hall|beach|village|island)\b", key
    ):
        return "place", 0.8

    if key.startswith("the "):
        rest = key[4:].strip()
        if rest in _GROUP_MARKERS or rest.endswith("s") and rest in _GROUP_MARKERS:
            return "group", 0.75
        if rest in _ANIMAL_TERMS:
            return "animal", 0.85
        if rest in {"water", "sea", "ocean", "river", "rain", "sun", "moon", "sky"}:
            return "concept", 0.9
        if rest in {"ring", "sword", "book", "pendant", "knife", "letter", "door"}:
            return "object", 0.82
        if rest in {"beach", "room", "office", "forest", "mountain", "shack"}:
            return "place", 0.8

    if key in _GROUP_MARKERS or (
        key.endswith("s") and key.rstrip("s") in _GROUP_MARKERS
    ):
        return "group", 0.72

    if _looks_like_proper_name(name):
        return "character", 0.85

    # Single lowercase common noun as object — usually not a character.
    if len(key.split()) == 1 and key.islower() and role == "object":
        return "concept", 0.7

    if role == "subject" and _looks_like_proper_name(name):
        return "character", 0.8

    # Fantasy sentient nature: "The Water spoke to her"
    ctx = f"{sentence} {evidence}".strip()
    if key in {"water", "river", "sea", "forest", "wind"} and _SENTIENT_NATURE_RE.search(
        ctx
    ):
        return "character", 0.55

    if len(key.split()) == 1:
        return "object", 0.55

    return "character", 0.45


def _spacy_classify(
    name: str,
    *,
    sentence: str,
    role: str,
) -> tuple[EntityType, float] | None:
    nlp = _get_nlp()
    if nlp is None or not sentence.strip():
        return None

    doc = nlp(sentence[:8000])
    key = _normalize(name)

    for ent in doc.ents:
        if _normalize(ent.text) == key or key in _normalize(ent.text):
            label = ent.label_
            if label == "PERSON":
                return "character", 0.92
            if label in ("GPE", "LOC", "FAC"):
                return "place", 0.9
            if label in ("ORG", "NORP"):
                return "group", 0.85
            if label in ("PRODUCT", "WORK_OF_ART", "EVENT"):
                return "object", 0.8

    # Dependency: object of love/hate → use head noun typing
    for token in doc:
        if token.dep_ not in ("dobj", "attr", "oprd", "pobj"):
            continue
        if _normalize(token.text) != key and key not in _normalize(token.text):
            continue
        head = token.head.lemma_.lower()
        if head in ("love", "hate", "fear", "trust", "distrust", "desire", "want"):
            if token.ent_type_ == "PERSON":
                return "character", 0.9
            if token.ent_type_ in ("GPE", "LOC", "FAC"):
                return "place", 0.88
            if token.text.lower() in _ANIMAL_TERMS:
                return "animal", 0.9
            if token.text.lower() in _CONCEPT_OR_OBJECT_TERMS:
                return "concept", 0.9
            return "object", 0.82

    for token in doc:
        if token.dep_ == "nsubj" and _normalize(token.text) == key:
            if token.ent_type_ == "PERSON":
                return "character", 0.9
            if token.text.lower() in {"she", "he", "they"}:
                return "character", 0.5

    return None


def classify_entity_surface(
    name: str,
    *,
    sentence: str = "",
    evidence: str = "",
    role: str = "unknown",
) -> tuple[EntityType, float]:
    """
    Assign entity type before persisting. Prefer spaCy when installed; else heuristics.
    """
    spacy_result = _spacy_classify(name, sentence=sentence or evidence, role=role)
    if spacy_result is not None:
        spacy_type, spacy_conf = spacy_result
        heur_type, heur_conf = _heuristic_classify(
            name, sentence=sentence, evidence=evidence, role=role
        )
        if heur_type in ("concept", "object", "animal", "place") and heur_conf >= 0.85:
            return heur_type, heur_conf
        # Proper names in fiction are usually characters, not GPE/LOC.
        if (
            heur_type == "character"
            and heur_conf >= 0.8
            and spacy_type in ("place", "object", "concept", "group")
        ):
            return heur_type, heur_conf
        return spacy_type, spacy_conf

    return _heuristic_classify(
        name, sentence=sentence, evidence=evidence, role=role
    )


def refine_claim_type(
    claim_type: str,
    predicate: str,
    subject_type: EntityType,
    object_type: EntityType | None,
) -> str:
    """Route interpersonal vs preference claims using entity types."""
    pred = predicate.strip().lower().replace(" ", "_")
    ct = (claim_type or "").strip()

    if object_type is None:
        return ct

    if pred in _RELATIONAL_PREDICATES or ct in (
        "relationship_state",
        "relationship_change",
    ):
        if subject_type == "character" and object_type == "character":
            return "relationship_state"
        if subject_type == "character" and object_type == "place":
            if pred in ("detests", "detested", "detest", "hates", "hated", "hate"):
                return "place_preference"
            return "place_preference"
        if subject_type == "character" and object_type in (
            "concept",
            "object",
            "animal",
        ):
            return "character_preference"
        if subject_type == "character" and object_type == "group":
            return "character_state"

    return ct


def is_character_to_character_relationship(
    claim_type: str,
    subject_type: str,
    object_type: str | None,
) -> bool:
    if (claim_type or "") != "relationship_state":
        return False
    if subject_type != "character":
        return False
    return object_type == "character"


def should_render_relationship_edge(
    claim_type: str,
    subject_entity_type: str,
    object_entity_type: str | None,
    *,
    subject_graph_eligible: bool = True,
    object_graph_eligible: bool = True,
) -> bool:
    """Only graph-eligible character↔character relationship_state claims on the map."""
    if not is_character_to_character_relationship(
        claim_type, subject_entity_type, object_entity_type
    ):
        return False
    if not subject_graph_eligible:
        return False
    return object_graph_eligible


def compute_graph_eligible(entity_type: str, type_confidence: float) -> bool:
    return entity_type == "character" and type_confidence >= 0.55


def should_create_character_entity(name: str, *, sentence: str = "", evidence: str = "") -> bool:
    """Strong gate: do not register every noun as a character."""
    etype, conf = classify_entity_surface(
        name, sentence=sentence, evidence=evidence, role="subject"
    )
    return etype == "character" and conf >= 0.55
