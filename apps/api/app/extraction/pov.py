"""Map first-person narrator references to the chapter POV character."""

from __future__ import annotations

import re

from app.extraction.schema import ExtractedClaim

_SUBJECT_FILLERS = frozenset(
    {
        "way",
        "that",
        "how",
        "in",
        "a",
        "an",
        "the",
        "and",
        "but",
        "so",
        "as",
        "if",
        "when",
        "while",
        "after",
        "before",
        "then",
        "just",
        "even",
        "still",
        "also",
        "only",
        "not",
    }
)

_FIRST_PERSON = frozenset({"i", "me", "myself"})


def _strip_leading_fillers(text: str) -> str:
    words = text.strip().split()
    while words and words[0].lower() in _SUBJECT_FILLERS:
        words = words[1:]
    return " ".join(words)


def resolve_narrator_subject(raw: str, pov_character: str | None) -> str | None:
    """
    Resolve regex-captured subject to a character name.

    When pov_character is set, bare or trailing "I" (not inside quotes) maps to POV.
    Without POV, lone "I" / filler+"I" subjects are dropped (not a proper name).
    """
    s = raw.strip()
    if not s:
        return None

    pov = pov_character.strip() if pov_character else ""
    words = s.split()
    if pov and words and words[-1].lower() == "i" and len(words) <= 2:
        return pov

    cleaned = _strip_leading_fillers(s)
    if not cleaned:
        return None

    lower = cleaned.lower()
    if lower in _FIRST_PERSON:
        return pov if pov else None

    if len(cleaned) < 2:
        return None

    return cleaned


def normalize_claims_for_pov(
    claims: list[ExtractedClaim], pov_character: str | None
) -> list[ExtractedClaim]:
    """Apply POV resolution to extracted claim subjects (and claim text when needed)."""
    pov = pov_character.strip() if pov_character else ""
    if not pov:
        return claims

    out: list[ExtractedClaim] = []
    for claim in claims:
        subj = resolve_narrator_subject(claim.subject, pov)
        if not subj:
            continue
        claim_text = claim.claim
        if claim.subject.strip().lower() in _FIRST_PERSON or re.search(
            r"\bI\b", claim.subject
        ):
            claim_text = re.sub(
                r"\bI\b",
                pov,
                claim_text,
                count=1,
            )
        elif claim.subject in claim_text:
            claim_text = claim_text.replace(claim.subject, subj, 1)
        out.append(claim.model_copy(update={"subject": subj, "claim": claim_text}))
    return out
