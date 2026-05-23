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

# (?<![\"\\w]) avoids matching inside words or after an opening quote context
_RELATION_PATTERNS: list[tuple[str, str, str, float]] = [
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+(?:looked at|watched|stared at|glanced at)\s+(\w+(?:\s+\w+)?)",
        r"\1 interacts with \2 in this scene.",
        "relationship_state",
        0.52,
    ),
    (
        r"(?<![\"\w])(I)\s+(?:trusts|trusted|distrusts|distrusted|loves|loved|hates|hated)\s+(\w+(?:\s+\w+)?)",
        r"\1 has a strong emotional stance toward \2.",
        "relationship_state",
        0.62,
    ),
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+(?:trusts|trusted|distrusts|distrusted|loves|loved|hates|hated)\s+(\w+(?:\s+\w+)?)",
        r"\1 has a strong emotional stance toward \2.",
        "relationship_state",
        0.58,
    ),
    (
        r"(?<![\"\w])(\w+(?:\s+\w+)?)\s+(?:said to|told|asked|whispered to)\s+(\w+(?:\s+\w+)?)",
        r"\1 speaks with \2.",
        "event",
        0.5,
    ),
]


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
            tgt = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            if tgt.lower() in _SKIP_NAMES:
                continue
            if subj.lower() in _SKIP_NAMES:
                continue
            claim_sentence = claim_tpl.replace(r"\1", subj).replace(r"\2", tgt)
            found.append(
                ExtractedClaim(
                    subject=subj,
                    claim_type=claim_type,
                    target=tgt,
                    claim=claim_sentence,
                    confidence=conf,
                    canon_level="soft",
                    evidence=m.group(0).strip()[:200],
                    chunk_index=chunk_index,
                )
            )
    return found
