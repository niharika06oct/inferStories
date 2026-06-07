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

# A subject that begins with an auxiliary/verb is a parse fragment, not an actor.
# e.g. "did not trust him at all" -> subject "did".
_AUXILIARY_SUBJECT_STARTS = re.compile(
    r"^(?:did|does|do|was|were|had|have|has|is|are|am|will|would|could|should|can|not|never)\b",
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


def reject_reason_for_claim(
    claim: ExtractedClaim,
    *,
    pov_character: str | None = None,
) -> str | None:
    """Return a rejection reason, or None if the claim should be kept."""
    subj = _norm(claim.subject)
    tgt = _norm(claim.target)
    pred = _norm(claim.predicate).replace(" ", "_")
    ev = _norm(claim.evidence)

    if not subj:
        return "empty subject"

    if subj == "narrator" or tgt == "narrator":
        return "placeholder narrator entity"

    if subj in _FIRST_PERSON_PLACEHOLDERS and not (pov_character or "").strip():
        return "unresolved first-person without POV character"

    if _JUNK_SUBJECT_STARTS.match(subj):
        return "junk subject start"

    if _AUXILIARY_SUBJECT_STARTS.match(subj):
        return "auxiliary/fragment subject (Stage 0)"

    if " way" in subj or subj.startswith("way "):
        return "junk 'way' subject"

    if subj in _PRONOUN_ONLY or subj in {"my mom", "the vigorous"}:
        if pred not in ("daughter_of", "son_of", "mother_of", "father_of"):
            return "unresolved pronoun subject"

    tgt_head = tgt.split()[0] if tgt else ""
    if tgt_head in _PRONOUN_ONLY and pred not in (
        "daughter_of",
        "son_of",
        "mother_of",
        "father_of",
    ):
        return "unresolved pronoun object (Stage 0 — no coref yet)"

    if tgt in _JUNK_OBJECT_FRAGMENTS or tgt in (
        "loved",
        "detested",
        "the vigorous",
        "the sun and",
    ):
        return "junk object fragment"

    if _INCOMPLETE_GERUND_OBJECT.match(tgt):
        return "incomplete gerund object"

    if pred in _WEAK_SPEECH_PREDICATES:
        return "weak speech predicate"

    if "said to me" in ev or "said to you" in ev:
        return "speech-evidence fragment"

    if pred in ("stares_at", "looks_at") and any(
        frag in tgt for frag in ("wide", "blue", "cheap", "vigorous")
    ):
        return "looks/stares junk object"

    if subj.startswith("tell "):
        return "tell-subject fragment"

    return None


def should_reject_extracted_claim(
    claim: ExtractedClaim,
    *,
    pov_character: str | None = None,
) -> bool:
    """Return True if this extraction should be dropped."""
    return reject_reason_for_claim(claim, pov_character=pov_character) is not None


def filter_extracted_claims(
    claims: list[ExtractedClaim],
    *,
    pov_character: str | None = None,
    reject_events: list | None = None,
) -> list[ExtractedClaim]:
    """Filter claims; optionally append Stage 0 reject events for FASTUS debug."""
    from app.nlp.fastus_debug import emit

    out: list[ExtractedClaim] = []
    for c in claims:
        reason = reject_reason_for_claim(c, pov_character=pov_character)
        if reason is None and c.predicate == "loves" and (c.target or "").lower() in (
            "loved",
            "the vigorous",
            "the sun and",
        ):
            reason = "junk loves target"
        if reason is not None:
            if reject_events is not None:
                emit(
                    reject_events,
                    stage="0",
                    event="reject_fragment",
                    message=f"Dropped claim: {reason}",
                    detail={
                        "subject": c.subject,
                        "predicate": c.predicate,
                        "target": c.target or "",
                        "evidence": (c.evidence or "")[:120],
                        "reason": reason,
                    },
                )
            continue
        out.append(c)
    return out
