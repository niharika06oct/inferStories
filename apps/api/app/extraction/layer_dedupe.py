"""Drop redundant rule-layer claims when the LLM layer succeeded on the same fact."""

from __future__ import annotations

import re

from app.extraction.schema import ExtractedClaim

_EMOTION_PREDICATES = frozenset(
    {
        "loves",
        "loved",
        "love",
        "detests",
        "detest",
        "detested",
        "hates",
        "hated",
        "hate",
        "trusts",
        "trusted",
        "distrusts",
        "distrusted",
        "fears",
        "feared",
        "misses",
        "missed",
    }
)


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _predicate_family(predicate: str) -> str:
    p = _norm(predicate).replace(" ", "_")
    if p in ("loves", "loved", "love"):
        return "love"
    if p in ("detests", "detest", "detested", "hates", "hated", "hate"):
        return "hate"
    if p in ("trusts", "trusted"):
        return "trust"
    if p in ("distrusts", "distrusted"):
        return "distrust"
    if p in ("fears", "feared", "fear"):
        return "fear"
    if p in ("misses", "missed", "miss"):
        return "miss"
    return p


def _target_tokens(target: str) -> set[str]:
    return {t for t in re.findall(r"[a-z']+", _norm(target)) if len(t) > 2}


def _evidence_overlap(a: str, b: str) -> bool:
    ea, eb = _norm(a), _norm(b)
    if not ea or not eb:
        return False
    if ea in eb or eb in ea:
        return True
    # Shared significant substring (e.g. "detested forks" in both)
    if len(ea) >= 12 and len(eb) >= 12:
        shorter, longer = (ea, eb) if len(ea) <= len(eb) else (eb, ea)
        if shorter in longer:
            return True
    return False


def _structural_redundant_with_llm(structural: ExtractedClaim, llm: ExtractedClaim) -> bool:
    if _norm(structural.subject) != _norm(llm.subject):
        return False

    if _evidence_overlap(structural.evidence, llm.evidence):
        return True

    sf = _predicate_family(structural.predicate)
    lf = _predicate_family(llm.predicate)
    if sf and lf and sf == lf:
        st = _target_tokens(structural.target)
        lt = _target_tokens(llm.target)
        if st and lt and (st & lt):
            return True
        if _norm(structural.target) and _norm(structural.target) in _norm(llm.target):
            return True
        if _norm(llm.target) and _norm(llm.target) in _norm(structural.target):
            return True

    return False


def suppress_redundant_structural_claims(
    claims: list[ExtractedClaim],
    *,
    llm_active: bool,
) -> tuple[list[ExtractedClaim], int]:
    """
    When LLM extraction succeeded, drop structural emotion claims duplicated by LLM.

    Family and LLM claims are always kept. Returns (filtered, suppressed_count).
    """
    if not llm_active:
        return claims, 0

    llm_claims = [c for c in claims if c.generation_origin == "llm"]
    if not llm_claims:
        return claims, 0

    out: list[ExtractedClaim] = []
    suppressed = 0
    for c in claims:
        if c.generation_origin != "structural":
            out.append(c)
            continue
        pred = _predicate_family(c.predicate)
        if pred not in ("love", "hate", "trust", "distrust", "fear", "miss") and (
            _norm(c.predicate) not in _EMOTION_PREDICATES
        ):
            out.append(c)
            continue
        if any(_structural_redundant_with_llm(c, llm) for llm in llm_claims):
            suppressed += 1
            continue
        out.append(c)

    return out, suppressed
