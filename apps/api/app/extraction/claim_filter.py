"""Reject low-quality structural extractions before persist."""

from __future__ import annotations

import re

from app.extraction.schema import ExtractedClaim

_FIRST_PERSON_PLACEHOLDERS = frozenset({"i", "me", "myself", "my", "mine"})

_PRONOUN_ONLY = frozenset(
    {
        "i",
        "me",
        "you",
        "he",
        "she",
        "they",
        "we",
        "us",
        "him",
        "her",
        "them",
        "my",
        "your",
        "his",
        "their",
        "it",
    }
)

_JUNK_OBJECT_FRAGMENTS = frozenset(
    {
        "wide",
        "blue",
        "cheap",
        "good",
        "great",
        "old",
        "new",
        "the vigorous",
        "her wide",
        "me before",
        "me",
    }
)

_JUNK_SUBJECT_STARTS = re.compile(
    r"^(?:tell|of|you|this|that|when|what|how|flying|neither|nothing|police|chief)\b",
    re.I,
)

# Truncated structural matches: "I love getting full" with no real object.
_INCOMPLETE_GERUND_OBJECT = re.compile(
    r"^(?:getting|being|having|making|taking|going|doing)\s+"
    r"(?:full|ready|better|worse|started|done|back|up|down|out|in|off)\s*$",
    re.I,
)

_WEAK_SPEECH_PREDICATES = frozenset(
    {
        "speaks_with",
        "said_to",
        "tells",
        "asks",
        "whispers_to",
        "looks_at",
        "watches",
        "stares_at",
        "glances_at",
    }
)


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def should_reject_extracted_claim(
    claim: ExtractedClaim,
    *,
    pov_character: str | None = None,
) -> bool:
    """Return True if this extraction should be dropped."""
    subj = _norm(claim.subject)
    tgt = _norm(claim.target)
    pred = _norm(claim.predicate).replace(" ", "_")
    ev = _norm(claim.evidence)

    if not subj:
        return True

    # Never persist the legacy "Narrator" placeholder as a real entity.
    if subj == "narrator" or tgt == "narrator":
        return True

    # Unresolved first-person with no POV character cannot be attributed to anyone.
    if subj in _FIRST_PERSON_PLACEHOLDERS and not (pov_character or "").strip():
        return True

    if _JUNK_SUBJECT_STARTS.match(subj):
        return True

    if " way" in subj or subj.startswith("way "):
        return True

    if subj in _PRONOUN_ONLY or subj in {"my mom", "the vigorous"}:
        if pred not in ("daughter_of", "son_of", "mother_of", "father_of"):
            return True

    if tgt in _PRONOUN_ONLY and pred not in (
        "daughter_of",
        "son_of",
        "mother_of",
        "father_of",
    ):
        return True

    if tgt in _JUNK_OBJECT_FRAGMENTS or tgt in (
        "loved",
        "detested",
        "the vigorous",
        "the sun and",
    ):
        return True

    if _INCOMPLETE_GERUND_OBJECT.match(tgt):
        return True

    if pred in _WEAK_SPEECH_PREDICATES:
        return True

    if "said to me" in ev or "said to you" in ev:
        return True

    if pred in ("stares_at", "looks_at") and any(
        frag in tgt for frag in ("wide", "blue", "cheap", "vigorous")
    ):
        return True

    if subj.startswith("tell "):
        return True

    return False


def filter_extracted_claims(
    claims: list[ExtractedClaim],
    *,
    pov_character: str | None = None,
) -> list[ExtractedClaim]:
    out: list[ExtractedClaim] = []
    for c in claims:
        if should_reject_extracted_claim(c, pov_character=pov_character):
            continue
        if c.predicate == "loves" and (c.target or "").lower() in (
            "loved",
            "the vigorous",
            "the sun and",
        ):
            continue
        out.append(c)
    return out
