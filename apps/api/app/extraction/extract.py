"""Extract structured claims from chapter text (layered: structural → OpenAI → heuristic)."""

from __future__ import annotations

import json
import os
import re
import time

import httpx

from app.extraction.chunking import chunk_chapter_text, word_count
from app.extraction.errors import ExtractionAPIError
from app.extraction.schema import (
    CLAIM_TYPES,
    ChunkExtractionDebug,
    ExtractedClaim,
    ExtractionResult,
)
from app.extraction.pov import normalize_claims_for_pov
from app.extraction.claim_filter import filter_extracted_claims
from app.extraction.family import discover_cast_from_text, family_extract_chunk
from app.extraction.layer_dedupe import suppress_redundant_structural_claims
from app.extraction.structural import detect_entities, structural_extract_chunk

CONFIDENCE_AUTO_APPROVE = 0.90
CONFIDENCE_NEEDS_REVIEW = 0.65

_SYSTEM = (
    "You extract structured story memory from fiction prose. "
    "Return only valid JSON matching the schema. "
    "Extract concrete, verifiable claims supported by the text. "
    "Include a short evidence quote from the passage for each claim. "
    "Do not invent facts not implied by the text. "
    f"claim_type must be one of: {', '.join(CLAIM_TYPES)}."
)

_USER_TEMPLATE = """Extract story claims from this fiction passage.

Return JSON:
{{
  "claims": [
    {{
      "subject": "Character name",
      "claim_type": "relationship_state",
      "predicate": "Semantic verb e.g. distrusts, trusts, loves (not the claim_type slug)",
      "target": "Other character or entity",
      "claim": "Full sentence describing the fact.",
      "confidence": 0.0-1.0,
      "canon_level": "core|active|soft",
      "evidence": "Short quote from text",
      "chunk_index": {chunk_index}
    }}
  ]
}}

Passage (chunk {chunk_index} of {chunk_total}):
---
{text}
---
{pov_note}
"""


def status_for_confidence(confidence: float) -> str:
    if confidence >= CONFIDENCE_AUTO_APPROVE:
        return "approved"
    if confidence >= CONFIDENCE_NEEDS_REVIEW:
        return "needs_review"
    return "suggested"


def _heuristic_extract_chunk(text: str, chunk_index: int) -> list[ExtractedClaim]:
    """Lightweight pattern extraction when no API key (dev/tests)."""
    found: list[ExtractedClaim] = []
    patterns: list[tuple[str, str, str, str, str, float]] = [
        (
            r"(\w+(?:\s+\w+)?)\s+(?:still\s+)?did not fully trust\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "distrusts",
            "active",
            r"\1 does not fully trust \2.",
            0.88,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+(?:knew|believed)\s+(?:that\s+)?(\w+(?:\s+\w+)?)\s+would never hurt",
            "character_state",
            "believes",
            "active",
            r"\1 believes \2 will not hurt her.",
            0.85,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+trusts\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "trusts",
            "active",
            r"\1 trusts \2.",
            0.9,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+(?:does not trust|distrusts)\s+(\w+(?:\s+\w+)?)",
            "relationship_state",
            "distrusts",
            "active",
            r"\1 distrusts \2.",
            0.88,
        ),
        (
            r"(\w+(?:\s+\w+)?)\s+cannot be killed",
            "world_rule",
            "cannot_be_killed",
            "core",
            r"\1 cannot be killed.",
            0.92,
        ),
    ]
    for pattern, claim_type, predicate, canon, claim_tpl, conf in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            subj = m.group(1).strip()
            tgt = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            claim_sentence = claim_tpl.replace(r"\1", subj).replace(r"\2", tgt)
            evidence = m.group(0).strip()[:200]
            found.append(
                ExtractedClaim(
                    subject=subj,
                    claim_type=claim_type,
                    predicate=predicate,
                    target=tgt,
                    claim=claim_sentence,
                    confidence=conf,
                    canon_level=canon,  # type: ignore[arg-type]
                    evidence=evidence,
                    chunk_index=chunk_index,
                    generation_origin="heuristic",
                )
            )
    return found


def _pov_note(pov_character: str | None) -> str:
    pov = pov_character.strip() if pov_character else ""
    if not pov:
        return ""
    return (
        f"\nNarrator POV: {pov}. "
        "Treat unquoted first-person I/me/myself in this passage as referring to this character "
        f"({pov}) in claim subjects."
    )


def _openai_extract_chunk(
    text: str,
    chunk_index: int,
    chunk_total: int,
    *,
    pov_character: str | None = None,
) -> list[ExtractedClaim]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _heuristic_extract_chunk(text, chunk_index)

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _USER_TEMPLATE.format(
        text=text[:12000],
        chunk_index=chunk_index,
        chunk_total=chunk_total,
        pov_note=_pov_note(pov_character),
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
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 4000,
                "temperature": 0.2,
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
        raw = data.get("claims", data if isinstance(data, list) else [])
        claims: list[ExtractedClaim] = []
        for item in raw:
            item = dict(item)
            item.setdefault("chunk_index", chunk_index)
            if item.get("claim_type") not in CLAIM_TYPES:
                ct = item.get("claim_type", "character_state")
                if ct == "belief":
                    item["claim_type"] = "character_state"
                elif ct not in CLAIM_TYPES:
                    item["claim_type"] = "character_state"
            claims.append(
                ExtractedClaim.model_validate(item).model_copy(
                    update={"generation_origin": "llm"}
                )
            )
        return claims


def _llm_extract_chunk(
    text: str,
    chunk_index: int,
    chunk_total: int,
    *,
    has_key: bool,
    pov_character: str | None = None,
) -> tuple[list[ExtractedClaim], bool, bool, bool]:
    """Returns claims, openai_attempted, openai_ok, fallback_used."""
    if not has_key:
        claims = _heuristic_extract_chunk(text, chunk_index)
        return (
            normalize_claims_for_pov(claims, pov_character),
            False,
            False,
            False,
        )

    try:
        claims = _openai_extract_chunk(
            text, chunk_index, chunk_total, pov_character=pov_character
        )
        return normalize_claims_for_pov(claims, pov_character), True, True, False
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
        claims = _heuristic_extract_chunk(text, chunk_index)
        return normalize_claims_for_pov(claims, pov_character), True, False, True
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
        claims = _heuristic_extract_chunk(text, chunk_index)
        return normalize_claims_for_pov(claims, pov_character), True, False, True


def _dedupe_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[ExtractedClaim] = []
    for c in claims:
        key = (
            c.subject.strip().lower(),
            c.claim_type.strip().lower(),
            (c.predicate or "").strip().lower(),
            (c.target or "").strip().lower(),
            c.claim.strip().lower()[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def extract_claims_from_text(
    text: str, *, pov_character: str | None = None
) -> ExtractionResult:
    started = time.perf_counter()
    chunks, warn = chunk_chapter_text(text)
    all_claims: list[ExtractedClaim] = []
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    total = len(chunks)
    api_error: str | None = None
    any_openai = False
    any_fallback = False
    chunk_debug: list[ChunkExtractionDebug] = []
    all_entities: set[str] = set()

    cast = discover_cast_from_text(text)

    for i, chunk in enumerate(chunks):
        entities = detect_entities(chunk)
        all_entities.update(entities)
        structural = structural_extract_chunk(chunk, i, pov_character=pov_character)
        family = family_extract_chunk(
            chunk, i, pov_character=pov_character, cast=cast
        )
        all_claims.extend(structural)
        all_claims.extend(family)

        llm_claims: list[ExtractedClaim] = []
        openai_attempted = False
        openai_ok = False
        fallback_used = False

        try:
            llm_claims, openai_attempted, openai_ok, fallback_used = _llm_extract_chunk(
                chunk,
                i,
                total,
                has_key=has_key,
                pov_character=pov_character,
            )
        except ExtractionAPIError as exc:
            api_error = str(exc)
            llm_claims = normalize_claims_for_pov(
                _heuristic_extract_chunk(chunk, i), pov_character
            )
            openai_attempted = has_key
            openai_ok = False
            fallback_used = True

        any_openai = any_openai or openai_attempted
        any_fallback = any_fallback or fallback_used
        all_claims.extend(llm_claims)

        chunk_debug.append(
            ChunkExtractionDebug(
                chunk_index=i,
                word_count=len(chunk.split()),
                openai_attempted=openai_attempted,
                openai_ok=openai_ok,
                fallback_used=fallback_used,
                structural_claims=len(structural),
                llm_claims=len(llm_claims),
                entities=entities,
            )
        )

    filtered = filter_extracted_claims(all_claims, pov_character=pov_character)
    any_openai_ok = any(c.openai_ok for c in chunk_debug)
    filtered, suppressed_structural = suppress_redundant_structural_claims(
        filtered, llm_active=any_openai_ok
    )
    deduped = _dedupe_claims(filtered)
    if any_openai and any_fallback:
        source = "hybrid"
    elif any_openai_ok:
        source = "openai"
    else:
        source = "heuristic"

    return ExtractionResult(
        claims=deduped,
        suppressed_structural_count=suppressed_structural,
        source=source,
        chunk_count=total,
        word_count=word_count(text),
        error=api_error,
        duration_ms=int((time.perf_counter() - started) * 1000),
        openai_attempted=any_openai,
        fallback_used=any_fallback,
        large_chapter_warning=warn is not None,
        structural_entity_count=len(all_entities),
        chunks=chunk_debug,
    )
