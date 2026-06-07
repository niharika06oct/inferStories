"""Fast deterministic extraction — emotion verbs, distaste, dialogue (filtered)."""

from __future__ import annotations

import re

from app.extraction.pov import resolve_narrator_subject
from app.extraction.schema import ExtractedClaim
from app.nlp.negation import has_identity_negation

_SKIP_NAMES = frozenset(
    {
        "the",
        "a",
        "an",
        "it",
        "he",
        "she",
        "they",
        "we",
        "i",
        "but",
        "and",
        "or",
        "then",
        "when",
        "while",
        "after",
        "before",
        "there",
        "here",
        "his",
        "her",
        "their",
        "my",
        "your",
        "what",
        "who",
        "how",
        "why",
        "if",
        "as",
        "in",
        "on",
        "at",
        "to",
        "from",
        "with",
        "for",
        "not",
        "no",
        "yes",
        "oh",
        "ah",
        "well",
        "so",
        "just",
        "still",
        "even",
        "all",
        "one",
        "two",
        "three",
        "chapter",
        "part",
        "section",
        "you",
        "me",
    }
)

_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
)

_EMOTION_VERBS = (
    r"love|loves|loved|"
    r"detest|detests|detested|"
    r"hate|hates|hated|"
    r"miss|misses|missed|"
    r"trust|trusts|trusted|"
    r"distrust|distrusts|distrusted|"
    r"fear|fears|feared|"
    r"care for|cared for|"
    r"worry about|worried about"
)

_VERB_TO_PREDICATE: dict[str, str] = {
    "love": "loves",
    "loves": "loves",
    "loved": "loves",
    "detest": "detests",
    "detests": "detests",
    "detested": "detests",
    "hate": "hates",
    "hates": "hates",
    "hated": "hates",
    "miss": "misses",
    "misses": "misses",
    "missed": "misses",
    "trust": "trusts",
    "trusts": "trusts",
    "trusted": "trusts",
    "distrust": "distrusts",
    "distrusts": "distrusts",
    "distrusted": "distrusts",
    "fear": "fears",
    "fears": "fears",
    "feared": "fears",
    "care for": "cares_for",
    "cared for": "cares_for",
    "worry about": "worries_about",
    "worried about": "worries_about",
    "half-brother": "is_half_brother_of",
}


# Optional auxiliary + negation between subject and verb: "did not", "was never",
# "had never", "do not", "n't". Captured so polarity can be set to False.
_NEG_PREFIX_RE = (
    r"(?:(?:did|do|does|could|would|should|had|have|has|was|were|am|are|is|will|can)\s+)?"
    r"(?:not|never|no\s+longer)\s+"
)

# Words that start a new clause — stop object capture before these.
_CLAUSE_BREAK_RE = (
    r"when|because|since|though|if|as|while|where|who|that|but|and|or|and\s+then"
)

# Object after emotion verb: up to 8 words (e.g. "getting full access to her").
_EMOTION_OBJECT_RE = (
    r"(?P<tgt>(?!you\b)"
    r"(?:the\s+|a\s+|an\s+)?[\w'-]+"
    rf"(?:\s+(?!{_CLAUSE_BREAK_RE}\b)[\w'-]+){{0,7}})"
)

_TAIL_STOPWORDS = frozenset(
    {
        "in",
        "on",
        "at",
        "to",
        "from",
        "with",
        "for",
        "and",
        "or",
        "the",
        "a",
        "an",
        "deeply",
        "truly",
        "really",
        "still",
        "even",
        "also",
        "just",
        "very",
        "all",
        "either",
        "anymore",
        "too",
        "yet",
    }
)


def _clean_phrase(phrase: str) -> str:
    parts = phrase.strip().rstrip(".,;:!?").split()
    while len(parts) > 1 and parts[-1].lower() in _TAIL_STOPWORDS:
        parts.pop()
    return " ".join(parts)


def _predicate_from_verb(raw: str) -> str:
    key = raw.strip().lower()
    if key in _VERB_TO_PREDICATE:
        return _VERB_TO_PREDICATE[key]
    token = key.split()[0]
    return _VERB_TO_PREDICATE.get(token, key.replace(" ", "_"))


def detect_entities(text: str, *, limit: int = 24) -> list[str]:
    from app.extraction.claim_filter import _JUNK_SUBJECT_STARTS

    seen: set[str] = set()
    out: list[str] = []
    for m in _NAME_RE.finditer(text):
        name = m.group(1).strip()
        key = name.lower()
        if key in _SKIP_NAMES or len(name) < 2:
            continue
        if _JUNK_SUBJECT_STARTS.match(key):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def structural_extract_chunk(
    text: str,
    chunk_index: int,
    *,
    pov_character: str | None = None,
) -> list[ExtractedClaim]:
    """Emotion and stance patterns; claim_type refined after entity resolution."""
    found: list[ExtractedClaim] = []

    def append_claim(
        subj: str,
        tgt: str,
        verb_raw: str,
        evidence: str,
        confidence: float,
        *,
        polarity: bool = True,
    ) -> None:
        if not subj or not tgt:
            return
        subj = _clean_phrase(subj)
        tgt = _clean_phrase(tgt)
        if not subj or not tgt:
            return
        if subj.lower() in _SKIP_NAMES or tgt.lower() in _SKIP_NAMES:
            return
        if " way" in subj.lower() or subj.lower().startswith("way "):
            return
        pred = _predicate_from_verb(verb_raw)
        neg = "" if polarity else "not "
        found.append(
            ExtractedClaim(
                subject=subj,
                claim_type="relationship_state",
                predicate=pred,
                target=tgt,
                claim=f"{subj} {neg}{pred.replace('_', ' ')} {tgt}.",
                polarity=polarity,
                confidence=confidence,
                canon_level="soft",
                evidence=evidence[:200],
                chunk_index=chunk_index,
                generation_origin="structural",
            )
        )

    # I loved Phoenix / I love getting full access to her / I did not trust him
    for m in re.finditer(
        rf"(?<![\"\w])(I)\s+(?P<neg>{_NEG_PREFIX_RE})?(?P<verb>{_EMOTION_VERBS})\s+{_EMOTION_OBJECT_RE}",
        text,
        re.I,
    ):
        subj = resolve_narrator_subject("I", pov_character)
        if not subj:
            continue
        tgt = _clean_phrase(m.group("tgt"))
        if tgt.lower() in ("the", "and", "or", "it") or not tgt:
            continue
        polarity = m.group("neg") is None
        append_claim(subj, tgt, m.group("verb"), m.group(0), 0.64, polarity=polarity)

    # I love you, Mom
    for m in re.finditer(
        r"(?<![\"\w])(I)\s+love\s+you,?\s*(Mom|Mother|Mum)\b",
        text,
        re.I,
    ):
        subj = resolve_narrator_subject("I", pov_character)
        if not subj:
            continue
        tgt = m.group(2).strip()
        append_claim(subj, tgt, "love", m.group(0), 0.72)

    # distaste for Forks / my distaste for Forks
    for m in re.finditer(
        r"(?:(?:I|my)\s+)?distaste\s+for\s+(?:the\s+)?([A-Za-z][\w\s'-]{0,40}?)(?=[\s.,;!?]|$)",
        text,
        re.I,
    ):
        subj = resolve_narrator_subject("I", pov_character)
        if not subj:
            continue
        tgt = m.group(1).strip().rstrip(".,;:!?")
        append_claim(subj, tgt, "detest", m.group(0), 0.7)

    # Named subject: Nahira loved Ashan / Edward did not trust Bella
    for m in re.finditer(
        rf"(?<![\"\w])([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)\s+"
        rf"(?P<neg>{_NEG_PREFIX_RE})?(?P<verb>{_EMOTION_VERBS})\s+{_EMOTION_OBJECT_RE}",
        text,
        re.I,
    ):
        g1 = m.group(1).strip().lower()
        if g1 in _SKIP_NAMES or g1 in ("i", "in a", "a way", "way"):
            continue
        if g1.endswith(" way") or g1.startswith("in ") or " way" in g1:
            continue
        subj = m.group(1).strip()
        tgt = _clean_phrase(m.group("tgt"))
        if not tgt or tgt.lower() in ("the", "and", "or"):
            continue
        polarity = m.group("neg") is None
        append_claim(subj, tgt, m.group("verb"), m.group(0), 0.58, polarity=polarity)

    # half-brother
    for m in re.finditer(
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+is\s+the\s+half-brother\s+of\s+(\w+(?:\s+\w+)?)",
        text,
        re.I,
    ):
        subj = m.group(1).strip()
        tgt = m.group(2).strip()
        found.append(
            ExtractedClaim(
                subject=subj,
                claim_type="relationship_state",
                predicate="is_half_brother_of",
                target=tgt,
                claim=f"{subj} is the half-brother of {tgt}.",
                confidence=0.72,
                canon_level="soft",
                evidence=m.group(0)[:200],
                chunk_index=chunk_index,
                generation_origin="structural",
            )
        )

    return found
