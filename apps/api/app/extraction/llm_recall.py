"""FASTUS Stage 6a — LLM recall extraction (Option B).

Broad recall of major story meaning before FASTUS grounding. Cached by prompt + input hash.

Relevant reading: Jurafsky — Information Extraction; DDIA Ch. 3 — caching derived data.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from app.extraction.errors import ExtractionAPIError
from app.extraction.schema import CLAIM_TYPES, ExtractedClaim

RECALL_PROMPT_VERSION = "fastus-recall-v1"

Importance = Literal["low", "medium", "high"]

_RECALL_SYSTEM = (
    "You extract major story-memory claims from fiction prose. "
    "Focus on plot-shaping facts: relationships, identity, trust, hostility, "
    "locations, timeline, world rules. Skip trivial actions and atmosphere. "
    "Return only valid JSON. Each claim needs a short verbatim evidence quote copied "
    "exactly from the passage — the quote must explicitly support the claim "
    "(mention the subject, object, or key fact). Never use a tangential sentence. "
    "Use polarity false when the text negates the fact. "
    f"claim_type must be one of: {', '.join(CLAIM_TYPES)}."
)

_RECALL_USER_TEMPLATE = """Extract major story claims from this fiction passage.

Return JSON:
{{
  "claims": [
    {{
      "subject": "Character or entity name",
      "predicate": "Semantic relation e.g. father_of, trusts, loves, hostile_toward, lives_in (city/town), lives_at (specific residence)",
      "object": "Other character or entity",
      "claim_type": "relationship_state",
      "claim": "Full sentence describing the fact.",
      "polarity": true,
      "evidence": "Verbatim quote from the passage that directly supports this claim",
      "confidence": 0.0-1.0,
      "importance": "low|medium|high"
    }}
  ]
}}

Passage (chunk {chunk_index} of {chunk_total}):
---
{text}
---
{pov_note}
{entities_note}
"""

_RECALL_CACHE: dict[str, list[dict[str, Any]]] = {}


@dataclass(frozen=True)
class RecallResult:
    claims: list[ExtractedClaim]
    cache_hit: bool = False
    attempted: bool = False
    ok: bool = False
    raw_count: int = 0


def llm_first_enabled() -> bool:
    return os.getenv("FASTUS_LLM_FIRST", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def llm_refine_enabled() -> bool:
    raw = os.getenv("FASTUS_LLM_REFINE", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def clear_recall_cache() -> None:
    _RECALL_CACHE.clear()


def _pov_note(pov_character: str | None) -> str:
    pov = (pov_character or "").strip()
    if not pov:
        return ""
    return (
        f"\nNarrator POV: {pov}. First-person I/me/myself refers to {pov} in subjects."
    )


def _entities_note(known_entities: list[str] | None) -> str:
    if not known_entities:
        return ""
    names = ", ".join(sorted({n.strip() for n in known_entities if n.strip()})[:24])
    if not names:
        return ""
    return f"\nKnown story entities (prefer these names): {names}"


def recall_cache_key(
    *,
    model: str,
    pov_character: str | None,
    text: str,
    entities: list[str] | None,
) -> str:
    payload = {
        "version": RECALL_PROMPT_VERSION,
        "model": model,
        "pov": (pov_character or "").strip(),
        "text": text[:12000],
        "entities": sorted(entities or []),
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
    path = base / f"recall_{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _write_disk_cache(key: str, claims: list[dict[str, Any]]) -> None:
    base = _cache_dir()
    if base is None:
        return
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / f"recall_{key}.json").write_text(
            json.dumps(claims, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError:
        pass


def _get_cached(key: str) -> list[dict[str, Any]] | None:
    if key in _RECALL_CACHE:
        return _RECALL_CACHE[key]
    disk = _read_disk_cache(key)
    if disk is not None:
        _RECALL_CACHE[key] = disk
        return disk
    return None


def _store_cached(key: str, claims: list[dict[str, Any]]) -> None:
    _RECALL_CACHE[key] = claims
    _write_disk_cache(key, claims)


def _normalize_claim_type(raw: str | None) -> str:
    ct = (raw or "").strip()
    if ct == "family_relation":
        return "relationship_state"
    if ct in CLAIM_TYPES:
        return ct
    return "character_state"


def _parse_recall_items(
    raw: list[dict[str, Any]],
    *,
    chunk_index: int,
) -> list[ExtractedClaim]:
    out: list[ExtractedClaim] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        subject = (item.get("subject") or "").strip()
        claim = (item.get("claim") or "").strip()
        evidence = (item.get("evidence") or claim or "").strip()
        if not subject or not claim or not evidence:
            continue
        polarity = item.get("polarity", True)
        if not isinstance(polarity, bool):
            polarity = True
        try:
            confidence = float(item.get("confidence", 0.75))
        except (TypeError, ValueError):
            confidence = 0.75
        confidence = max(0.0, min(1.0, confidence))
        importance = str(item.get("importance", "medium")).strip().lower()
        if importance not in ("low", "medium", "high"):
            importance = "medium"

        out.append(
            ExtractedClaim(
                subject=subject,
                claim_type=_normalize_claim_type(item.get("claim_type")),
                predicate=(item.get("predicate") or "").strip(),
                target=(item.get("object") or item.get("target") or "").strip(),
                claim=claim,
                polarity=polarity,
                confidence=confidence,
                evidence=evidence[:500],
                chunk_index=chunk_index,
                generation_origin="llm_recall",
                importance=importance,  # type: ignore[arg-type]
            )
        )
    return out


def _call_openai_recall(
    *,
    text: str,
    chunk_index: int,
    chunk_total: int,
    pov_character: str | None,
    known_entities: list[str] | None,
) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return []

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _RECALL_USER_TEMPLATE.format(
        text=text[:12000],
        chunk_index=chunk_index,
        chunk_total=chunk_total,
        pov_note=_pov_note(pov_character),
        entities_note=_entities_note(known_entities),
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
                    {"role": "system", "content": _RECALL_SYSTEM},
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
        if not isinstance(raw, list):
            return []
        return [dict(x) for x in raw if isinstance(x, dict)]


def recall_claims_from_chunk(
    text: str,
    chunk_index: int,
    chunk_total: int,
    *,
    pov_character: str | None = None,
    known_entities: list[str] | None = None,
) -> RecallResult:
    """Stage 6a: broad LLM recall for major story claims."""
    if not llm_first_enabled():
        return RecallResult(claims=[])

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return RecallResult(claims=[], attempted=False, ok=False)

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    cache_key = recall_cache_key(
        model=model,
        pov_character=pov_character,
        text=text,
        entities=known_entities,
    )

    cached = _get_cached(cache_key)
    if cached is not None:
        claims = _parse_recall_items(cached, chunk_index=chunk_index)
        return RecallResult(
            claims=claims,
            cache_hit=True,
            attempted=True,
            ok=bool(claims),
            raw_count=len(cached),
        )

    try:
        raw = _call_openai_recall(
            text=text,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            pov_character=pov_character,
            known_entities=known_entities,
        )
        _store_cached(cache_key, raw)
        claims = _parse_recall_items(raw, chunk_index=chunk_index)
        return RecallResult(
            claims=claims,
            attempted=True,
            ok=bool(claims),
            raw_count=len(raw),
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
                msg = "OpenAI quota exceeded for LLM recall."
            elif code == 401:
                msg = "OpenAI API key is invalid for LLM recall."
            else:
                msg = f"OpenAI access denied for LLM recall (HTTP {code})."
            if detail:
                msg = f"{msg} ({detail})"
            raise ExtractionAPIError(msg, status_code=code) from exc
        return RecallResult(claims=[], attempted=True, ok=False)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return RecallResult(claims=[], attempted=True, ok=False)
