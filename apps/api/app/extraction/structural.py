"""Fast deterministic extraction — no LLM (entities + simple relationship hints)."""

from __future__ import annotations

import re

from app.extraction.pov import resolve_narrator_subject
from app.extraction.schema import ExtractedClaim

# Sentence-start words often capitalized but not character names
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
    }
)

_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
)

_VERB_TO_PREDICATE: dict[str, str] = {
    "trusts": "trusts",
    "trusted": "trusts",
    "distrusts": "distrusts",
    "distrusted": "distrusts",
    "loves": "loves",
    "loved": "loves",
    "hates": "hates",
    "hated": "hates",
    "looked": "looks_at",
    "watched": "watches",
    "stared": "stares_at",
    "glanced": "glances_at",
    "said": "speaks_with",
    "told": "tells",
    "asked": "asks",
    "whispered": "whispers_to",
    "half-brother": "is_half_brother_of",
}

# pattern, claim_tpl, claim_type, confidence
_RELATION_PATTERNS: list[tuple[str, str, str, float]] = [
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+(?P<verb>looked at|watched|stared at|glanced at)\s+(\w+(?:\s+\w+)?)",
        r"\1 interacts with \2 in this scene.",
        "relationship_state",
        0.52,
    ),
    (
        r"(?<![\"\w])(I)\s+(?P<verb>trusts|trusted|distrusts|distrusted|loves|loved|hates|hated)\s+(\w+(?:\s+\w+)?)",
        r"\1 has a strong emotional stance toward \2.",
        "relationship_state",
        0.62,
    ),
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+(?P<verb>trusts|trusted|distrusts|distrusted|loves|loved|hates|hated)\s+(\w+(?:\s+\w+)?)",
        r"\1 has a strong emotional stance toward \2.",
        "relationship_state",
        0.58,
    ),
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+(?P<verb>said to|told|asked|whispered to)\s+(\w+(?:\s+\w+)?)",
        r"\1 speaks with \2.",
        "event",
        0.5,
    ),
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+is\s+the\s+half-brother\s+of\s+(\w+(?:\s+\w+)?)",
        r"\1 is the half-brother of \2.",
        "relationship_state",
        0.72,
    ),
]


def _predicate_from_match(m: re.Match[str]) -> str:
    full = m.group(0).lower()
    if "half-brother" in full or "half brother" in full:
        return "is_half_brother_of"
    raw = (m.groupdict().get("verb") or "").strip().lower()
    if not raw:
        return "relates_to"
    token = raw.split()[0]
    if raw in _VERB_TO_PREDICATE:
        return _VERB_TO_PREDICATE[raw]
    if token in _VERB_TO_PREDICATE:
        return _VERB_TO_PREDICATE[token]
    return raw.replace(" ", "_")


def detect_entities(text: str, *, limit: int = 24) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _NAME_RE.finditer(text):
        name = m.group(1).strip()
        key = name.lower()
        if key in _SKIP_NAMES or len(name) < 2:
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
    """Low-confidence claims from patterns + entity co-occurrence hints."""
    found: list[ExtractedClaim] = []
    for pattern, claim_tpl, claim_type, conf in _RELATION_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            subj = resolve_narrator_subject(m.group(1).strip(), pov_character)
            if not subj:
                continue
            tgt = ""
            if m.lastindex and m.lastindex >= 2:
                tgt = m.group(m.lastindex).strip()
            if tgt.lower() in _SKIP_NAMES:
                continue
            if subj.lower() in _SKIP_NAMES:
                continue
            claim_sentence = claim_tpl.replace(r"\1", subj).replace(r"\2", tgt)
            found.append(
                ExtractedClaim(
                    subject=subj,
                    claim_type=claim_type,
                    predicate=_predicate_from_match(m),
                    target=tgt,
                    claim=claim_sentence,
                    confidence=conf,
                    canon_level="soft",
                    evidence=m.group(0).strip()[:200],
                    chunk_index=chunk_index,
                )
            )
    return found
