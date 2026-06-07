"""FASTUS Stage 6 — LLM candidate refinement.

Refine Stage 5 ClaimDrafts instead of extracting claims from scratch.
Results are cached by prompt version + model + passage + candidate payload hash.

Relevant reading: Jurafsky — Information Extraction; DDIA Ch. 3 — caching.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.extraction.errors import ExtractionAPIError
from app.extraction.schema import CLAIM_TYPES, ExtractedClaim
from app.extraction.semantic_patterns import ClaimDraft, claim_draft_to_extracted

REFINE_PROMPT_VERSION = "fastus-refine-v1"

_REFINE_SYSTEM = (
    "You refine pre-extracted story-memory candidates from fiction prose. "
    "Return only valid JSON matching the schema. "
    "For each candidate: classify valid true/false, correct fields if needed, "
    "or reject invalid extractions. Do not invent new candidates. "
    "Keep polarity separate from predicate (use father_of + polarity false, "
    "not not_father_of). "
    f"claim_type must be one of: {', '.join(CLAIM_TYPES)}."
)

_REFINE_USER_TEMPLATE = """Refine these deterministic claim candidates from a fiction passage.

For each candidate, return whether it is a valid story fact supported by the evidence.
Correct claim_type, predicate, polarity, subject, target, or claim text when needed.
Reject fragments, unresolved pronouns, or unsupported inferences.

Return JSON:
{{
  "refinements": [
    {{
      "candidate_id": "c0",
      "valid": true,
      "claim_type": "relationship_state",
      "predicate": "father_of",
      "polarity": false,
      "subject": "Charlie",
      "target": "Isabella Swan",
      "claim": "Charlie is not the father of Isabella Swan.",
      "confidence": 0.0-1.0,
      "explanation": "Brief reason"
    }}
  ]
}}

Passage (chunk {chunk_index} of {chunk_total}):
---
{text}
---
{pov_note}

Candidates:
{candidates_json}
"""

# In-process cache; optional disk mirror under FASTUS_LLM_CACHE_DIR.
_REFINE_CACHE: dict[str, list[dict[str, Any]]] = {}


@dataclass(frozen=True)
class RefineResult:
    claims: list[ExtractedClaim]
    cache_hit: bool = False
    attempted: bool = False
    ok: bool = False
    fallback_used: bool = False
    rejected_count: int = 0
    candidate_count: int = 0


def clear_refine_cache() -> None:
    """Clear in-memory refinement cache (for tests)."""
    _REFINE_CACHE.clear()


def _pov_note(pov_character: str | None) -> str:
    pov = (pov_character or "").strip()
    if not pov:
        return ""
    return (
        f"Narrator POV: {pov}. First-person I/me/myself refers to {pov}."
    )


def build_candidate_payloads(drafts: list[ClaimDraft]) -> list[dict[str, Any]]:
    """Serialize claim drafts for the refinement prompt."""
    out: list[dict[str, Any]] = []
    for i, draft in enumerate(drafts):
        out.append(
            {
                "candidate_id": f"c{i}",
                "evidence": draft.evidence_text,
                "subject": draft.subject,
                "predicate": draft.predicate,
                "object": draft.target,
                "polarity": draft.polarity,
                "claim_type": draft.claim_type,
                "claim": draft.claim,
                "confidence": round(draft.confidence, 3),
                "question": "Is this a valid story fact supported by the evidence?",
            }
        )
    return out


def refine_cache_key(
    *,
    model: str,
    pov_character: str | None,
    text: str,
    candidates: list[dict[str, Any]],
) -> str:
    payload = {
        "version": REFINE_PROMPT_VERSION,
        "model": model,
        "pov": (pov_character or "").strip(),
        "text": text[:12000],
        "candidates": candidates,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_dir() -> Path | None:
    raw = os.getenv("FASTUS_LLM_CACHE_DIR", "").strip()
    if not raw:
        return None
    return Path(raw)


def _read_disk_cache(key: str) -> list[dict[str, Any]] | None:
    base = _cache_dir()
    if base is None:
        return None
    path = base / f"{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _write_disk_cache(key: str, refinements: list[dict[str, Any]]) -> None:
    base = _cache_dir()
    if base is None:
        return
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / f"{key}.json").write_text(
            json.dumps(refinements, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def _get_cached_refinements(key: str) -> list[dict[str, Any]] | None:
    if key in _REFINE_CACHE:
        return _REFINE_CACHE[key]
    disk = _read_disk_cache(key)
    if disk is not None:
        _REFINE_CACHE[key] = disk
        return disk
    return None


def _store_cached_refinements(key: str, refinements: list[dict[str, Any]]) -> None:
    _REFINE_CACHE[key] = refinements
    _write_disk_cache(key, refinements)


def _normalize_claim_type(raw: str | None) -> str:
    ct = (raw or "").strip()
    if ct == "family_relation":
        return "relationship_state"
    if ct in CLAIM_TYPES:
        return ct
    return "character_state"


def apply_refinements(
    drafts: list[ClaimDraft],
    refinements: list[dict[str, Any]],
) -> tuple[list[ExtractedClaim], int]:
    """Merge LLM refinements into ExtractedClaims; return claims and reject count."""
    by_id = {f"c{i}": d for i, d in enumerate(drafts)}
    out: list[ExtractedClaim] = []
    rejected = 0

    for item in refinements:
        cid = str(item.get("candidate_id", ""))
        draft = by_id.get(cid)
        if draft is None:
            continue
        if not item.get("valid", False):
            rejected += 1
            continue

        base = claim_draft_to_extracted(draft)
        claim_type = _normalize_claim_type(item.get("claim_type") or base.claim_type)
        predicate = (item.get("predicate") or base.predicate or "").strip()
        subject = (item.get("subject") or base.subject).strip()
        target = (item.get("target") or item.get("object") or base.target or "").strip()
        claim = (item.get("claim") or base.claim).strip()
        polarity = item.get("polarity", base.polarity)
        if not isinstance(polarity, bool):
            polarity = base.polarity
        confidence = item.get("confidence", base.confidence)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = base.confidence
        confidence = max(0.0, min(1.0, confidence))

        evidence = (draft.evidence_text or base.evidence).strip()
        if not subject or not claim:
            rejected += 1
            continue

        out.append(
            ExtractedClaim(
                subject=subject,
                claim_type=claim_type,
                predicate=predicate,
                target=target,
                claim=claim,
                polarity=polarity,
                confidence=confidence,
                canon_level=base.canon_level,
                evidence=evidence[:500],
                chunk_index=base.chunk_index,
                generation_origin="llm",
            )
        )

    return out, rejected


def drafts_to_extracted_passthrough(drafts: list[ClaimDraft]) -> list[ExtractedClaim]:
    """Use deterministic drafts as LLM-layer claims when refinement is unavailable."""
    return [
        claim_draft_to_extracted(d).model_copy(update={"generation_origin": "llm"})
        for d in drafts
    ]


def _call_openai_refine(
    *,
    text: str,
    chunk_index: int,
    chunk_total: int,
    pov_character: str | None,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return []

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _REFINE_USER_TEMPLATE.format(
        text=text[:12000],
        chunk_index=chunk_index,
        chunk_total=chunk_total,
        pov_note=_pov_note(pov_character),
        candidates_json=json.dumps(candidates, indent=2, ensure_ascii=True),
    )

    with httpx.Client(timeout=90.0) as client:
        r = client.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _REFINE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 2000,
                "temperature": 0.1,
            },
        )
        r.raise_for_status()
        content = (
            r.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        data = json.loads(content)
        raw = data.get("refinements", data if isinstance(data, list) else [])
        if not isinstance(raw, list):
            return []
        return [dict(x) for x in raw if isinstance(x, dict)]


def _legacy_extract_enabled() -> bool:
    return os.getenv("FASTUS_LLM_LEGACY", "").strip().lower() in ("1", "true", "yes")


def refine_claim_drafts(
    drafts: list[ClaimDraft],
    text: str,
    chunk_index: int,
    chunk_total: int,
    *,
    pov_character: str | None = None,
    legacy_extract_fn=None,
) -> RefineResult:
    """
    Refine claim drafts via LLM (or passthrough/cache).

    When drafts are empty, returns empty unless FASTUS_LLM_LEGACY enables
    the old full-chunk extractor.
    """
    candidate_count = len(drafts)
    if not drafts:
        if _legacy_extract_enabled() and legacy_extract_fn is not None:
            claims = legacy_extract_fn()
            return RefineResult(
                claims=claims,
                attempted=bool(os.getenv("OPENAI_API_KEY", "").strip()),
                ok=bool(claims),
                candidate_count=0,
            )
        return RefineResult(claims=[], candidate_count=0)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        claims = drafts_to_extracted_passthrough(drafts)
        return RefineResult(
            claims=claims,
            attempted=False,
            ok=True,
            candidate_count=candidate_count,
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    candidates = build_candidate_payloads(drafts)
    cache_key = refine_cache_key(
        model=model,
        pov_character=pov_character,
        text=text,
        candidates=candidates,
    )

    cached = _get_cached_refinements(cache_key)
    if cached is not None:
        claims, rejected = apply_refinements(drafts, cached)
        return RefineResult(
            claims=claims,
            cache_hit=True,
            attempted=True,
            ok=True,
            rejected_count=rejected,
            candidate_count=candidate_count,
        )

    try:
        refinements = _call_openai_refine(
            text=text,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            pov_character=pov_character,
            candidates=candidates,
        )
        _store_cached_refinements(cache_key, refinements)
        claims, rejected = apply_refinements(drafts, refinements)
        if not claims:
            claims = drafts_to_extracted_passthrough(drafts)
            return RefineResult(
                claims=claims,
                attempted=True,
                ok=False,
                fallback_used=True,
                rejected_count=rejected or candidate_count,
                candidate_count=candidate_count,
            )
        return RefineResult(
            claims=claims,
            attempted=True,
            ok=True,
            rejected_count=rejected,
            candidate_count=candidate_count,
        )
    except ExtractionAPIError:
        raise
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403, 429):
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except (json.JSONDecodeError, AttributeError, TypeError):
                detail = exc.response.text[:200]
            if code == 429:
                msg = (
                    "OpenAI quota exceeded — add billing or credits at "
                    "https://platform.openai.com/account/billing"
                )
            elif code == 401:
                msg = "OpenAI API key is invalid or expired."
            else:
                msg = f"OpenAI access denied (HTTP {code})."
            if detail:
                msg = f"{msg} ({detail})"
            raise ExtractionAPIError(msg, status_code=code) from exc
        claims = drafts_to_extracted_passthrough(drafts)
        return RefineResult(
            claims=claims,
            attempted=True,
            ok=False,
            fallback_used=True,
            candidate_count=candidate_count,
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        claims = drafts_to_extracted_passthrough(drafts)
        return RefineResult(
            claims=claims,
            attempted=True,
            ok=False,
            fallback_used=True,
            candidate_count=candidate_count,
        )
