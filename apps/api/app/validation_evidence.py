"""Locate claim evidence in chapter text for continuity scroll targets."""

from __future__ import annotations

import re

from app.models import Claim


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _entity_tokens(*fields: str | None) -> set[str]:
    """Salient tokens from claim subject/object for anchoring relevance checks."""
    out: set[str] = set()
    for field in fields:
        for token in re.findall(r"[a-z']{3,}", _norm(field or "")):
            if token in {
                "the",
                "and",
                "was",
                "were",
                "that",
                "this",
                "with",
                "from",
                "they",
                "them",
                "their",
                "have",
                "been",
                "when",
                "what",
                "into",
                "about",
                "after",
                "before",
                "each",
                "several",
                "started",
                "recognize",
                "faces",
                "class",
            }:
                continue
            out.add(token)
    return out


_MIN_EVIDENCE_CHARS = 20


def _sentence_around_index(text: str, idx: int, *, max_len: int = 240) -> tuple[int, int]:
    """Expand a character index to the enclosing sentence."""
    start = max(
        text.rfind(".", 0, idx),
        text.rfind("!", 0, idx),
        text.rfind("?", 0, idx),
        text.rfind("\n", 0, idx),
    )
    start = 0 if start < 0 else start + 1
    end_candidates = [
        text.find(".", idx),
        text.find("!", idx),
        text.find("?", idx),
        text.find("\n", idx),
    ]
    end_candidates = [e for e in end_candidates if e >= 0]
    end = min(end_candidates) + 1 if end_candidates else len(text)
    return _trim_span(text, start, end, max_len=max_len)


def _trim_span(text: str, start: int, end: int, *, max_len: int = 240) -> tuple[int, int]:
    """Clip a span to max_len without cutting mid-word."""
    start = max(0, start)
    end = min(len(text), end)
    if end <= start:
        return start, 1
    if end - start <= max_len:
        return start, end - start
    cut = start + max_len
    while cut > start and text[cut - 1].isalnum() and cut < len(text) and text[cut].isalnum():
        cut -= 1
    if cut <= start:
        cut = min(len(text), start + max_len)
    return start, cut - start


def _flexible_find(text: str, needle: str) -> tuple[int, int] | None:
    """Return (offset, length) for needle in text (exact or whitespace-flexible)."""
    if not needle or not text:
        return None
    lowered = text.lower()
    n = needle.strip()
    idx = lowered.find(n.lower())
    if idx >= 0:
        if len(n.split()) <= 1 and len(n) < _MIN_EVIDENCE_CHARS:
            s, length = _sentence_around_index(text, idx)
            return s, length
        s, e = _trim_span(text, idx, idx + len(n))
        return s, e
    parts = n.split()
    if len(parts) >= 2:
        pattern = r"\s+".join(re.escape(p) for p in parts)
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            s, e = _trim_span(text, match.start(), match.end())
            return s, e
    return None


def _evidence_sentence_candidates(evidence: str) -> list[str]:
    """Prefer shorter verbatim quotes over long multi-sentence LLM evidence blobs."""
    raw = (evidence or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", raw) if p.strip()]
    if len(parts) <= 1:
        return [raw]
    parts.sort(key=len)
    return parts


def _token_overlap_span(
    text: str,
    anchor: str,
    *,
    required_tokens: set[str] | None = None,
) -> tuple[int, int] | None:
    """Find a sentence span when evidence paraphrases the passage (LLM recall)."""
    tokens = [t for t in re.findall(r"[a-z']{4,}", _norm(anchor)) if len(t) >= 4]
    if len(tokens) < 3:
        return None

    best: tuple[int, int, int] | None = None
    for match in re.finditer(r"[^.!?\n]+[.!?]?", text):
        sentence = match.group(0)
        lowered = sentence.lower()
        hits = sum(1 for t in tokens if t in lowered)
        min_hits = max(2, (len(tokens) + 1) // 2)
        if hits < min_hits:
            continue
        if required_tokens and not any(t in lowered for t in required_tokens):
            continue
        trimmed = sentence.strip()
        if not trimmed:
            continue
        lead = sentence.find(trimmed[0])
        start = match.start() + max(0, lead)
        length = min(len(trimmed), 240)
        score = hits + (2 if required_tokens and any(t in lowered for t in required_tokens) else 0)
        if best is None or score > best[2]:
            best = (start, length, score)
    if best is None:
        return None
    return best[0], max(1, best[1])


def locate_claim_evidence_span(
    scene_text: str,
    *,
    evidence_text: str | None = None,
    claim_text: str | None = None,
    claim_object: str | None = None,
    claim_subject: str | None = None,
) -> tuple[int, int, str]:
    """
    Return (offset, length, anchor_text) for editor highlight.

    Never falls back to subject name alone (avoids highlighting chapter opening).
    """
    text = scene_text or ""
    if not text.strip():
        return -1, 0, ""

    entity_tokens = _entity_tokens(claim_subject, claim_object, claim_text)

    def _try_candidate(candidate: str) -> tuple[int, int, str] | None:
        quote = candidate.strip()
        if not quote:
            return None
        hit = _flexible_find(text, quote[:500])
        if hit:
            off, length = hit
            anchor = text[off : off + length]
            return off, length, anchor
        overlap = _token_overlap_span(
            text,
            quote[:500],
            required_tokens=entity_tokens or None,
        )
        if overlap:
            off, length = overlap
            anchor = text[off : off + length].strip()
            return off, min(len(anchor), 240), anchor
        return None

    evidence = (evidence_text or "").strip()
    if evidence:
        for sentence in _evidence_sentence_candidates(evidence):
            found = _try_candidate(sentence)
            if found:
                return found

    claim = (claim_text or "").strip()[:240]
    if claim:
        found = _try_candidate(claim)
        if found:
            return found

    obj = (claim_object or "").strip()
    if len(obj) >= 4:
        hit = _flexible_find(text, obj)
        if hit:
            off, length = hit
            if length < _MIN_EVIDENCE_CHARS:
                off, length = _sentence_around_index(text, off)
            anchor = text[off : off + length]
            return off, length, anchor

    return -1, 0, (evidence_text or claim_text or "")[:500]


def continuity_anchor_in_scene(
    scene_text: str, claim: Claim
) -> tuple[int, str, int]:
    """
    Return (text_offset, anchor_text, anchor_length) for highlighting.

    Prefer the claim's evidence quote; never fall back to subject name alone
    (that often matches the first line of the chapter).
    """
    off, length, anchor = locate_claim_evidence_span(
        scene_text,
        evidence_text=claim.evidence_text,
        claim_text=claim.claim_text,
        claim_object=claim.claim_object,
        claim_subject=claim.subject,
    )
    if off < 0 or length <= 0:
        return 0, anchor, 0
    return off, anchor, length


def evidence_offset_in_scene(scene_text: str, claim: Claim) -> int:
    """Character offset in scene_text; 0 if anchor not found."""
    offset, _, _ = continuity_anchor_in_scene(scene_text, claim)
    return offset


def claim_anchored_in_scene(scene_text: str, claim: Claim) -> bool:
    """
    True when the claim's evidence or claim_text still appears in the chapter.

    Stricter than continuity_anchor_in_scene: does not fall back to object-name
    alone, so a removed sentence does not leave a stale loves/trusts row alive.
    """
    text = (scene_text or "").strip()
    if not text:
        return False
    lowered = text.lower()
    for field in (claim.evidence_text, claim.claim_text):
        quote = (field or "").strip()
        if not quote:
            continue
        anchor = quote[:500]
        if lowered.find(anchor.lower()) >= 0:
            return True
        if len(anchor) > 48:
            short = anchor[:48].strip()
            if lowered.find(short.lower()) >= 0:
                return True
    return False
