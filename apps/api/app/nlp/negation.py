"""Shared negation helpers for FASTUS layers (avoids extraction import cycles)."""

from __future__ import annotations

import re

_IDENTITY_NEGATION_RE = re.compile(
    r"\b(?:was|were|is|are|am)\s+(?:not|never)\b|\b(?:wasn't|weren't|isn't|aren't|ain't)\b",
    re.I,
)


def has_identity_negation(text: str) -> bool:
    """True if the clause denies an identity/state (e.g. 'was not my father')."""
    return bool(_IDENTITY_NEGATION_RE.search(text or ""))
